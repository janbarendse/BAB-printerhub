"""
Printer Memory Reader Module
Reads fiscal printer memory using CTS310II Memory Audit commands (0xA0-0xA7)
Returns structured data from Z reports and transactions
"""

from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger_module import logger
from src.printers.cts310ii.protocol import STX, ETX, FS, NAK
from src.printers.cts310ii.cts310ii_driver import string_to_hex, hex_to_string


class PrinterMemoryReader:
    """Read printer memory digitally using serial commands"""

    def __init__(self, printer_driver):
        """Initialize printer memory reader

        Args:
            printer_driver: The printer driver instance (e.g., CTS310IIDriver)
        """
        self.printer = printer_driver
        logger.info("PrinterMemoryReader initialized")

    def _send_command(self, cmd):
        """Send command to printer using the printer driver

        Args:
            cmd: Hex command string

        Returns:
            Response from printer
        """
        return self.printer.send_command(cmd)

    def _is_success_response(self, response):
        """Check if response indicates success

        Args:
            response: Hex response string

        Returns:
            bool: True if successful response
        """
        if response is None:
            return False
        ACK = "06"
        if response.startswith(STX) and response.endswith(ETX + ACK):
            return True
        if response.endswith(ACK):
            return True
        return False

    def read_z_reports_by_date(self, start_date, end_date):
        """
        Read Z reports for date range from printer memory

        Args:
            start_date: DDMMYYYY format (e.g., "01122024" for Dec 1, 2024)
            end_date: DDMMYYYY format (e.g., "31122024" for Dec 31, 2024)

        Returns:
            List of dicts, each containing 59 fields from command 0xA2

        Example:
            reader = PrinterMemoryReader(printer_driver)
            reports = reader.read_z_reports_by_date("01122024", "31122024")
        """
        logger.info(f"Reading Z reports from {start_date} to {end_date}")

        # Step 0: Clear any previous read operation state
        self._end_read_operation()

        # Step 1: Initialize fiscal memory read by date range (command 0xA1)
        if not self._initialize_fiscal_memory_read(start_date, end_date):
            logger.error("Failed to initialize fiscal memory read")
            return []

        # Step 2: Loop to read each Z report (command 0xA2)
        z_reports = []
        report_count = 0

        while True:
            z_report_data = self._read_next_z_report()

            if z_report_data is None:
                # Error reading report
                logger.error("Error reading Z report, stopping")
                break

            if z_report_data.get('error_code') == '237':
                # No more reports (normal exit)
                logger.info(f"No more Z reports. Total read: {report_count}")
                break

            if z_report_data.get('error_code') != '0':
                # Other error code
                error_code = z_report_data.get('error_code', 'unknown')
                logger.warning(f"Z report read returned error code: {error_code}")
                break

            z_reports.append(z_report_data)
            report_count += 1
            logger.debug(f"Read Z report #{report_count}: Z{z_report_data.get('z_number', 'N/A')}")

        # Step 3: End read operation (command 0xA7)
        self._end_read_operation()

        logger.info(f"Successfully read {len(z_reports)} Z reports")
        return z_reports

    def _initialize_fiscal_memory_read(self, start_date, end_date):
        """
        Initialize fiscal memory read by date range (Command 0xA1)

        Args:
            start_date: DDMMYYYY format (8 digits)
            end_date: DDMMYYYY format (8 digits)

        Returns:
            True if successful, False otherwise
        """
        # Command 0xA1 (161 decimal = A1 hex)
        # Format: STX + 0xA1 + FS + StartDate + FS + EndDate + ETX
        start_hex = string_to_hex(start_date)
        end_hex = string_to_hex(end_date)

        if not start_hex or not end_hex:
            logger.error("Failed to encode dates to hex")
            return False

        # Build command: STX (0x02) + A1 (uppercase hex) + FS (0x1C) + start_date + FS + end_date + ETX (0x03)
        cmd = f"{STX}A1{FS}{start_hex}{FS}{end_hex}{ETX}"

        logger.debug(f"Initializing fiscal memory read: {cmd}")
        response = self._send_command(cmd)

        # Success indicator: Response is ACK or ETX+ACK (not NAK)
        if response and self._is_success_response(response) and not response.endswith(NAK):
            logger.info("Fiscal memory read initialized successfully")
            return True

        logger.error(f"Failed to initialize fiscal memory read. Response: {response}")
        return False

    def _read_next_z_report(self):
        """
        Read next Z report in range (Command 0xA2)

        Returns:
            Dict with 59 fields, or None on error

        Response format (59 fields separated by FS):
            Field 1: Error Code (0 = success, 237 = no more reports)
            Field 2: Z Report Number
            Field 3: Z Report Date (DDMMYY)
            Field 4: Start NKF
            Field 5: End NKF
            Field 6-9: Document counts (Sales, Refunds, Voids, Training)
            Field 10-25: Tax totals by rate
            Field 26-30: Discount/surcharge totals
            Field 31-35: Payment method totals
            Field 36-40: Accumulated grand totals
            Field 41-59: Additional fiscal data
        """
        # Command 0xA2 (162 decimal = A2 hex)
        # Format: STX + 0xA2 + ETX
        cmd = f"{STX}A2{ETX}"

        logger.debug("Reading next Z report...")
        response = self._send_command(cmd)

        if not response:
            logger.error("No response from printer")
            return None

        # Parse response fields
        # Response format: STX + Field1 + FS + Field2 + FS + ... + FieldN + ETX + ACK
        try:
            # Remove STX (first 2 chars) and ETX+ACK (last 4 chars)
            if len(response) < 6:
                logger.error(f"Response too short: {response}")
                return None

            data = response[2:-4]

            # Split by field separator (FS = 1C)
            # Note: Response hex is lowercase, FS constant is uppercase
            if FS.lower() not in data.lower():
                # Single field response (likely error code)
                error_code = hex_to_string(data) if data else "unknown"
                logger.debug(f"Single field response, error code: {error_code}")
                return {"error_code": error_code}

            fields_hex = data.split(FS.lower() if FS.lower() in data else FS)
            fields = [hex_to_string(field) for field in fields_hex]

            logger.debug(f"Parsed {len(fields)} fields from Z report response")

            if len(fields) < 5:
                logger.warning(f"Expected 59 fields, got {len(fields)}")
                return {"error_code": fields[0] if fields else "unknown"}

            # Map fields to dict (based on PDF manual Section 6)
            # NOTE: STAR printer returns report type in field 0 (e.g., "20" for sales),
            # not an error code. Error code 0 means success for initialization only.
            z_report = {
                "error_code": "0",  # Set to 0 since we got data
                "report_type": fields[0] if len(fields) > 0 else "",
                "z_number": fields[1] if len(fields) > 1 else "",
                "date": fields[2] if len(fields) > 2 else "",
                "time": fields[3] if len(fields) > 3 else "",
                "period_end_date": fields[4] if len(fields) > 4 else "",
                "start_nkf": fields[5] if len(fields) > 5 else "",
                "end_nkf": fields[6] if len(fields) > 6 else "",

                # Document counts
                "sales_count": fields[7] if len(fields) > 7 else "0",
                "refund_count": fields[8] if len(fields) > 8 else "0",
                "void_count": fields[9] if len(fields) > 9 else "0",
                "training_count": fields[10] if len(fields) > 10 else "0",

                # Tax totals - Tax rates A through F
                "tax_a_taxable": fields[11] if len(fields) > 11 else "0",
                "tax_a_total": fields[12] if len(fields) > 12 else "0",
                "tax_b_taxable": fields[13] if len(fields) > 13 else "0",
                "tax_b_total": fields[14] if len(fields) > 14 else "0",
                "tax_c_taxable": fields[15] if len(fields) > 15 else "0",
                "tax_c_total": fields[16] if len(fields) > 16 else "0",
                "tax_d_taxable": fields[17] if len(fields) > 17 else "0",
                "tax_d_total": fields[18] if len(fields) > 18 else "0",
                "tax_e_taxable": fields[19] if len(fields) > 19 else "0",
                "tax_e_total": fields[20] if len(fields) > 20 else "0",
                "tax_f_taxable": fields[21] if len(fields) > 21 else "0",
                "tax_f_total": fields[22] if len(fields) > 22 else "0",
                "exempt_amount": fields[23] if len(fields) > 23 else "0",

                # Discounts/surcharges
                "discount_total": fields[24] if len(fields) > 24 else "0",
                "surcharge_total": fields[25] if len(fields) > 25 else "0",

                # Payment methods
                "cash_total": fields[26] if len(fields) > 26 else "0",
                "card_total": fields[27] if len(fields) > 27 else "0",
                "other_payment_total": fields[28] if len(fields) > 28 else "0",

                # Grand totals
                "total_sales": fields[29] if len(fields) > 29 else "0",
                "total_refunds": fields[30] if len(fields) > 30 else "0",
                "net_total": fields[31] if len(fields) > 31 else "0",

                # Store all raw fields for reference
                "all_fields": fields,
                "field_count": len(fields),
                "raw_data": data  # Keep hex data for fallback parsing
            }

            return z_report

        except Exception as e:
            logger.error(f"Error parsing Z report response: {e}")
            logger.error(f"Response was: {response}")
            return None

    def _end_read_operation(self):
        """
        End read operation (Command 0xA7)

        Returns:
            True if successful, False otherwise
        """
        # Command 0xA7 (167 decimal = A7 hex)
        # Format: STX + 0xA7 + ETX
        cmd = f"{STX}A7{ETX}"

        logger.debug("Ending read operation...")
        response = self._send_command(cmd)

        if response and self._is_success_response(response):
            logger.info("Read operation ended successfully")
            return True

        logger.warning(f"End read operation response: {response}")
        return False

    # Transaction Memory Reading Methods (Commands 0xA4/0xA5/0xA7)

    def read_transactions_by_date(self, start_date, end_date):
        """
        Read individual transactions for date range

        Args:
            start_date: DDMMYYYY format (e.g., "20122025" for Dec 20, 2025)
            end_date: DDMMYYYY format (e.g., "20122025" for Dec 20, 2025)

        Returns:
            List of dicts, each containing transaction data

        Uses commands:
            0xA4: Initialize transaction memory read by date
            0xA5: Read next transaction (60 fields per transaction)
            0xA7: End read operation

        Example:
            reader = PrinterMemoryReader(printer_driver)
            transactions = reader.read_transactions_by_date("20122025", "20122025")
        """
        logger.info(f"Reading transactions from {start_date} to {end_date}")

        # Step 0: Clear any previous read operation state
        self._end_read_operation()

        # Step 1: Initialize transaction memory read (command 0xA4)
        if not self._initialize_transaction_memory_read(start_date, end_date):
            logger.error("Failed to initialize transaction memory read")
            return []

        # Step 2: Loop to read each transaction (command 0xA5)
        transactions = []
        transaction_count = 0
        max_transactions = 10000  # Safety limit

        for i in range(max_transactions):
            transaction_data = self._read_next_transaction()

            if transaction_data is None:
                logger.error("Error reading transaction, stopping")
                break

            if transaction_data.get('error_code') == '237':
                logger.info(f"No more transactions. Total read: {transaction_count}")
                break

            if transaction_data.get('error_code') != '0':
                error_code = transaction_data.get('error_code', 'unknown')
                logger.warning(f"Transaction read returned error code: {error_code}")
                break

            transactions.append(transaction_data)
            transaction_count += 1

            if transaction_count % 100 == 0:
                logger.debug(f"Read {transaction_count} transactions...")

        # Step 3: End read operation (command 0xA7)
        self._end_read_operation()

        logger.info(f"Successfully read {len(transactions)} transactions")
        return transactions

    def _initialize_transaction_memory_read(self, start_date, end_date):
        """
        Initialize transaction memory read by date range (Command 0xA4)

        Args:
            start_date: DDMMYYYY format
            end_date: DDMMYYYY format

        Returns:
            True if successful, False otherwise
        """
        start_hex = string_to_hex(start_date)
        end_hex = string_to_hex(end_date)

        if not start_hex or not end_hex:
            logger.error("Failed to encode dates to hex")
            return False

        # Build command: STX + A4 + FS + start_date + FS + end_date + ETX
        cmd = f"{STX}A4{FS}{start_hex}{FS}{end_hex}{ETX}"

        logger.debug(f"Initializing transaction memory read: {cmd}")
        response = self._send_command(cmd)

        # Success indicator: Response is ACK or ETX+ACK (not NAK)
        if response and self._is_success_response(response) and not response.endswith(NAK):
            logger.info("Transaction memory read initialized successfully")
            return True

        logger.error(f"Failed to initialize transaction memory read. Response: {response}")
        return False

    def _read_next_transaction(self):
        """
        Read next transaction in range (Command 0xA5)

        Returns:
            Dict with transaction data (60 fields), or None on error

        Response format (60 fields - fixed-width concatenated string):
            Similar to Z report format but with individual transaction details
            including NKF, customer info, items, amounts, payments
        """
        # Command 0xA5 (165 decimal = A5 hex)
        cmd = f"{STX}A5{ETX}"

        response = self._send_command(cmd)

        if not response:
            logger.error("No response from printer")
            return None

        # Check for NAK (no more transactions)
        if response.endswith(NAK):
            logger.debug("NAK received - no more transactions")
            return {"error_code": "237"}  # Use same code as Z reports

        # Parse response
        try:
            if len(response) < 6:
                logger.error(f"Response too short: {response}")
                return None

            # Remove STX (first 2 chars) and ETX+ACK (last 4 chars)
            data = response[2:-4]

            # Check if it has field separators (like Z reports)
            if FS.lower() in data.lower():
                # Split by field separator and decode each field
                fields_hex = data.split(FS.lower() if FS.lower() in data else FS)
                fields = [hex_to_string(field) for field in fields_hex]

                # Parse transaction fields
                transaction = {
                    "error_code": "0",
                    "doc_type": fields[0] if len(fields) > 0 else "",
                    "nkf": fields[1] if len(fields) > 1 else "",
                    "date": fields[2] if len(fields) > 2 else "",
                    "time": fields[3] if len(fields) > 3 else "",
                    "customer_crib": fields[4] if len(fields) > 4 else "",
                    "operator": fields[5] if len(fields) > 5 else "",
                    "client_field": fields[6] if len(fields) > 6 else "",
                    "customer_name": fields[7] if len(fields) > 7 else "",
                    "customer_address": fields[8] if len(fields) > 8 else "",
                    "subtotal": fields[9] if len(fields) > 9 else "0",
                    "discount": fields[10] if len(fields) > 10 else "0",
                    "surcharge": fields[11] if len(fields) > 11 else "0",
                    "service_charge": fields[12] if len(fields) > 12 else "0",
                    "tip": fields[13] if len(fields) > 13 else "0",
                    "tax_a_base": fields[14] if len(fields) > 14 else "0",
                    "tax_a_amount": fields[15] if len(fields) > 15 else "0",
                    "tax_b_base": fields[16] if len(fields) > 16 else "0",
                    "tax_b_amount": fields[17] if len(fields) > 17 else "0",
                    "payment_method": fields[18] if len(fields) > 18 else "Cash",
                    "total": fields[19] if len(fields) > 19 else "0",
                    "all_fields": fields,
                    "field_count": len(fields)
                }
            else:
                # Decode as single string (fallback)
                decoded = hex_to_string(data) if data else ""
                transaction = {
                    "error_code": "0",
                    "raw_data": decoded,
                    "data_length": len(decoded),
                    "raw_response": response
                }

            return transaction

        except Exception as e:
            logger.error(f"Error parsing transaction response: {e}")
            logger.error(f"Response was: {response}")
            return None

    # Date conversion utilities
    @staticmethod
    def wordpress_to_printer_date(wp_date):
        """
        Convert WordPress date format to printer format

        Args:
            wp_date: YYYY-MM-DD format (e.g., "2024-12-01")

        Returns:
            DDMMYYYY format (e.g., "01122024")
        """
        try:
            date_obj = datetime.strptime(wp_date, "%Y-%m-%d")
            return date_obj.strftime("%d%m%Y")
        except Exception as e:
            logger.error(f"Error converting WordPress date: {e}")
            return None

    @staticmethod
    def printer_to_csv_date(printer_date):
        """
        Convert printer date format to CSV format

        Args:
            printer_date: DDMMYYYY format (e.g., "01122024") or DDMMYY format (e.g., "011224")

        Returns:
            DD-MM-YYYY format (e.g., "01-12-2024")
        """
        try:
            # Try DDMMYYYY format first (8 digits)
            if len(printer_date) == 8:
                date_obj = datetime.strptime(printer_date, "%d%m%Y")
                return date_obj.strftime("%d-%m-%Y")
            # Fallback to DDMMYY format (6 digits)
            elif len(printer_date) == 6:
                date_obj = datetime.strptime(printer_date, "%d%m%y")
                return date_obj.strftime("%d-%m-%Y")
            else:
                logger.warning(f"Unknown date format: {printer_date}")
                return printer_date
        except Exception as e:
            logger.error(f"Error converting printer date: {e}")
            return printer_date  # Return original if conversion fails

    @staticmethod
    def get_date_range_for_month(year, month):
        """
        Get start and end dates for a month in printer format

        Args:
            year: 4-digit year (e.g., 2024)
            month: 1-12

        Returns:
            Tuple of (start_date, end_date) in DDMMYYYY format
        """
        try:
            from calendar import monthrange

            # First day of month
            start_date = datetime(year, month, 1)

            # Last day of month
            last_day = monthrange(year, month)[1]
            end_date = datetime(year, month, last_day)

            return (
                start_date.strftime("%d%m%Y"),
                end_date.strftime("%d%m%Y")
            )
        except Exception as e:
            logger.error(f"Error calculating month range: {e}")
            return None, None
