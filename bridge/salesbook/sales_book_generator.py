"""
Sales Book CSV Generator Module
Generates CSV files formatted per Curaçao government Sales Book specifications
"""

import os
import json
import hashlib
from datetime import datetime
from calendar import monthrange
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger_module import logger
from salesbook.printer_memory_reader import PrinterMemoryReader


class SalesBookGenerator:
    """Generate Sales Book CSV files from printer memory"""

    # Month names in English
    MONTH_NAMES = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }

    def __init__(self, printer_driver, config_path=None):
        """Initialize sales book generator

        Args:
            printer_driver: The printer driver instance (e.g., CTS310IIDriver)
            config_path: Path to config.json file (defaults to bridge/config.json)
        """
        self.printer = printer_driver
        self.memory_reader = PrinterMemoryReader(printer_driver)

        # Load configuration from bridge/config.json
        if config_path is None:
            # Default to bridge/config.json
            bridge_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(bridge_dir, "config.json")

        self.config = self._load_config(config_path)

        # Set configuration attributes from config.json
        self.BUSINESS_NAME = self.config.get('business', {}).get('name', 'BAB Restaurant')
        self.TAX_NUMBER = self.config.get('business', {}).get('tax_number', '123456789')
        self.SOFTWARE_NAME = self.config.get('software', {}).get('name', 'BAB PrintHub')
        self.SOFTWARE_VERSION = self.config.get('software', {}).get('version', '2.0')
        self.CERTIFICATION_NUMBER = self.config.get('software', {}).get('certification_number', 'CERT2025')
        self.DEVICE_SERIAL = self.config.get('printer', {}).get('device_serial', '33554431')
        self.FISCAL_MEMORY_SERIAL = self.config.get('printer', {}).get('fiscal_memory_serial', 'FM000000')

        # Get salesbook-specific config
        salesbook_config = self.config.get('salesbook', {})
        self.BASE_DIRECTORY = salesbook_config.get('csv_export_path', 'C:\\FBOOK')
        self.INCLUDE_SHA1 = salesbook_config.get('include_sha1_hash', True)
        self.INCLUDE_TRANSACTION_DETAILS = salesbook_config.get('include_transaction_details', True)

        logger.info("SalesBookGenerator initialized")
        logger.info(f"  Business: {self.BUSINESS_NAME}")
        logger.info(f"  Tax Number: {self.TAX_NUMBER}")
        logger.info(f"  CSV Export Path: {self.BASE_DIRECTORY}")

    def _load_config(self, config_path):
        """Load configuration from JSON file

        Args:
            config_path: Path to config.json file

        Returns:
            dict: Configuration data
        """
        # Default configuration
        default_config = {
            "business": {
                "name": "BAB Restaurant",
                "tax_number": "123456789"
            },
            "software": {
                "name": "BAB PrintHub",
                "version": "2.0",
                "certification_number": "CERT2025"
            },
            "printer": {
                "device_serial": "33554431",
                "fiscal_memory_serial": "FM000000"
            },
            "salesbook": {
                "csv_export_path": "C:\\FBOOK",
                "include_sha1_hash": True,
                "include_transaction_details": True
            }
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"Configuration loaded from {config_path}")
                return config
            else:
                logger.warning(f"Configuration file not found: {config_path}")
                logger.info("Using default configuration")
                return default_config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Using default configuration")
            return default_config

    def generate_daily_csv(self, date_str):
        """
        Generate daily sales book CSV

        Args:
            date_str: Date in YYYY-MM-DD format (e.g., "2025-12-20")

        Returns:
            Full file path of generated CSV, or None on error

        Process:
            1. Convert date to printer format (DDMMYYYY)
            2. Read Z reports for the date
            3. Read individual transactions for the date
            4. Build Line Type 1 (daily header from Z report)
            5. Build Line Type 2 records (from transactions)
            6. Calculate SHA-1 hash from Line Type 2
            7. Create directory structure
            8. Write CSV file
        """
        logger.info(f"Generating daily sales book for {date_str}")

        try:
            # Parse date
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            year = date_obj.year
            month = date_obj.month
            day = date_obj.day

            # Convert to printer format
            printer_date = date_obj.strftime("%d%m%Y")

            # Read Z reports for this date
            z_reports = self.memory_reader.read_z_reports_by_date(printer_date, printer_date)

            if not z_reports:
                logger.warning(f"No Z reports found for {date_str}")
                return None

            # Filter out system events, keep only sales reports (type 20)
            sales_z_reports = [z for z in z_reports if z.get('report_type', '') == '20']

            if not sales_z_reports:
                logger.warning(f"No sales Z reports found for {date_str} (only system events)")
                # Fall back to using any Z report
                if z_reports:
                    logger.info("Using non-sales Z report as fallback")
                    z_report = z_reports[0]
                else:
                    return None
            else:
                # Use the first sales Z report for the day
                z_report = sales_z_reports[0]

            # Read individual transactions for this date (if enabled)
            transactions = []
            if self.INCLUDE_TRANSACTION_DETAILS:
                transactions = self.memory_reader.read_transactions_by_date(printer_date, printer_date)
                if not transactions:
                    logger.warning(f"No transactions found for {date_str}")

            # Build CSV lines
            line_type_1 = self._build_line_type_1(z_report, date_str)
            line_type_2_records = self._build_line_type_2_records(transactions, z_report)

            # Calculate SHA-1 hash
            sha1_hash = self._calculate_sha1_hash(line_type_2_records) if self.INCLUDE_SHA1 else ""

            # Create directory structure
            file_path = self._ensure_directory_structure(year, month, day)

            if not file_path:
                logger.error("Failed to create directory structure")
                return None

            # Build filename
            date_filename = date_obj.strftime("%Y%m%d")
            csv_filename = f"daily_salesbook_{date_filename}.csv"
            full_path = os.path.join(file_path, csv_filename)

            # Write CSV file
            with open(full_path, 'w', encoding='utf-8') as f:
                # Write Line Type 1 (daily header)
                f.write(line_type_1 + "\r\n")

                # Write Line Type 2 records (transactions)
                for line in line_type_2_records:
                    f.write(line + "\r\n")

            logger.info(f"Daily sales book generated: {full_path}")
            logger.info(f"  Lines written: 1 header + {len(line_type_2_records)} transactions")
            if self.INCLUDE_SHA1:
                logger.info(f"  SHA-1 hash: {sha1_hash}")

            return full_path

        except Exception as e:
            logger.error(f"Error generating daily sales book: {e}")
            return None

    def generate_monthly_csv(self, year, month):
        """
        Generate monthly sales book CSV

        Args:
            year: 4-digit year (e.g., 2025)
            month: 1-12

        Returns:
            Full file path of generated CSV, or None on error

        Process:
            1. Calculate month date range
            2. Read ALL Z reports for the month
            3. Read ALL transactions for the month
            4. Build Line Type 3 (monthly header)
            5. For each day with Z reports:
                a. Build Line Type 1 (daily header)
                b. Build Line Type 2 records (transactions for that day)
            6. Calculate SHA-1 hash from all Line Type 2
            7. Update Line Type 3 with hash
            8. Create directory structure
            9. Write CSV file
        """
        logger.info(f"Generating monthly sales book for {month}/{year}")

        try:
            # Get month date range
            first_day = datetime(year, month, 1)
            last_day_num = monthrange(year, month)[1]
            last_day = datetime(year, month, last_day_num)

            start_date = first_day.strftime("%d%m%Y")
            end_date = last_day.strftime("%d%m%Y")

            # Read Z reports for entire month
            z_reports = self.memory_reader.read_z_reports_by_date(start_date, end_date)

            if not z_reports:
                logger.warning(f"No Z reports found for {month}/{year}")
                return None

            # Read transactions for entire month (if enabled)
            transactions = []
            if self.INCLUDE_TRANSACTION_DETAILS:
                transactions = self.memory_reader.read_transactions_by_date(start_date, end_date)

            # Group Z reports by date
            z_reports_by_date = {}
            for z_report in z_reports:
                raw_data = z_report.get('raw_data', '')
                if raw_data.startswith('20'):  # Sales reports only
                    # Extract date from position 3-10
                    if len(raw_data) >= 11:
                        z_date = raw_data[3:11]
                        if z_date not in z_reports_by_date:
                            z_reports_by_date[z_date] = z_report

            # Group transactions by date
            transactions_by_date = {}
            for txn in transactions:
                raw_data = txn.get('raw_data', '')
                # Parse date from transaction (need to determine exact position)
                # For now, extract all transactions
                if raw_data not in transactions_by_date:
                    transactions_by_date[raw_data] = []
                transactions_by_date[raw_data].append(txn)

            # Build all CSV lines
            all_line_type_2 = []
            all_line_type_1 = []

            for z_date in sorted(z_reports_by_date.keys()):
                z_report = z_reports_by_date[z_date]
                date_str = self._printer_date_to_csv_date(z_date)

                # Build Line Type 1 for this day
                line_type_1 = self._build_line_type_1(z_report, date_str)
                all_line_type_1.append(line_type_1)

                # Build Line Type 2 for this day's transactions
                # (TODO: Filter transactions by date)
                day_transactions = transactions  # For now, use all
                line_type_2_records = self._build_line_type_2_records(day_transactions, z_report)
                all_line_type_2.extend(line_type_2_records)

            # Calculate SHA-1 hash from all Line Type 2
            sha1_hash = self._calculate_sha1_hash(all_line_type_2) if self.INCLUDE_SHA1 else ""

            # Build Line Type 3 (monthly header)
            line_type_3 = self._build_line_type_3(year, month, sha1_hash)

            # Create directory structure
            file_path = self._ensure_directory_structure(year, month)

            if not file_path:
                logger.error("Failed to create directory structure")
                return None

            # Build filename
            csv_filename = f"monthly_salesbook_{year}{month:02d}.csv"
            full_path = os.path.join(file_path, csv_filename)

            # Write CSV file
            with open(full_path, 'w', encoding='utf-8') as f:
                # Line Type 3 (monthly header)
                f.write(line_type_3 + "\r\n")

                # Interleave Line Type 1 and Line Type 2 by date
                line2_index = 0
                for line1 in all_line_type_1:
                    f.write(line1 + "\r\n")

                    # Write corresponding transactions
                    # (TODO: Properly associate transactions with days)
                    # For now, write all after first day
                    if line2_index == 0:
                        for line2 in all_line_type_2:
                            f.write(line2 + "\r\n")
                        line2_index = len(all_line_type_2)

            logger.info(f"Monthly sales book generated: {full_path}")
            logger.info(f"  Z reports: {len(all_line_type_1)}")
            logger.info(f"  Transactions: {len(all_line_type_2)}")
            if self.INCLUDE_SHA1:
                logger.info(f"  SHA-1 hash: {sha1_hash}")

            return full_path

        except Exception as e:
            logger.error(f"Error generating monthly sales book: {e}")
            return None

    def _build_line_type_1(self, z_report, date_str):
        """
        Build CSV Line Type 1 (Daily Sales Book Header)

        Args:
            z_report: Dict with Z report data from printer
            date_str: Date in YYYY-MM-DD or DD-MM-YYYY format

        Returns:
            String with 28 fields separated by ||

        Format:
            1||Daily sales book||BusinessName||TaxNumber||ReportDate||FirstNKF||LastNKF||
            ZReportNumber||SalesCount||RefundCount||TrainingCount||CancelledCount||
            TaxATaxable||TaxATotal||TaxBTaxable||TaxBTotal||TaxCTaxable||TaxCTotal||
            TaxDTaxable||TaxDTotal||TaxETaxable||TaxETotal||TaxFTaxable||TaxFTotal||
            ExemptAmount||TotalSales||TotalRefunds||TotalNet||
            CashTotal||CardTotal||OtherPaymentTotal
        """
        try:
            # Use parsed fields from Z report
            z_number = z_report.get('z_number', '0')
            start_nkf = z_report.get('start_nkf', '000000')
            end_nkf = z_report.get('end_nkf', '000000')
            sales_count = z_report.get('sales_count', '0')
            refund_count = z_report.get('refund_count', '0')
            void_count = z_report.get('void_count', '0')
            training_count = z_report.get('training_count', '0')

            # Tax totals
            tax_a_taxable = z_report.get('tax_a_taxable', '0')
            tax_a_total = z_report.get('tax_a_total', '0')
            cash_total = z_report.get('cash_total', '0')
            card_total = z_report.get('card_total', '0')
            total_sales = z_report.get('total_sales', '0')
            total_refunds = z_report.get('total_refunds', '0')
            net_total = z_report.get('net_total', '0')

            # Convert date to DD-MM-YYYY if needed
            if '-' not in date_str and z_report.get('date'):
                date_str = self._printer_date_to_csv_date(z_report.get('date'))

            # Build Line Type 1 (28 fields)
            fields = [
                "1",  # Line type
                "Daily sales book",  # Description
                self.BUSINESS_NAME,
                self.TAX_NUMBER,
                date_str,  # Report date
                start_nkf,  # First NKF
                end_nkf,  # Last NKF
                z_number,  # Z report number
                sales_count,  # Sales count
                refund_count,  # Refund count
                void_count,  # Training count (using void as proxy)
                "0",  # Cancelled count
                tax_a_taxable,  # Tax A taxable
                tax_a_total,  # Tax A total
                "0.00",  # Tax B taxable
                "0.00",  # Tax B total
                "0.00",  # Tax C taxable
                "0.00",  # Tax C total
                "0.00",  # Tax D taxable
                "0.00",  # Tax D total
                "0.00",  # Tax E taxable
                "0.00",  # Tax E total
                "0.00",  # Tax F taxable
                "0.00",  # Tax F total
                "0.00",  # Exempt amount
                total_sales,  # Total sales
                total_refunds,  # Total refunds
                net_total,  # Total net
                cash_total,  # Cash total
                card_total,  # Card total
                "0.00",  # Other payment total
            ]

            return "||".join(fields)

        except Exception as e:
            logger.error(f"Error building Line Type 1: {e}")
            return None

    def _build_line_type_2_records(self, transactions, z_report):
        """
        Build CSV Line Type 2 records (Transaction Records)

        Args:
            transactions: List of transaction dicts from printer
            z_report: Z report dict for reference

        Returns:
            List of strings, each with 40 fields separated by ||

        Format:
            2||TransactionDate||TransactionTime||DocumentType||NKF||ZReportNumber||
            CustomerName||CustomerCRIB||ItemCount||Subtotal||Discount||Surcharge||
            ServiceCharge||Tip||TaxABase||TaxAAmount||TaxBBase||TaxBAmount||
            TaxCBase||TaxCAmount||TaxDBase||TaxDAmount||TaxEBase||TaxEAmount||
            TaxFBase||TaxFAmount||ExemptAmount||Total||
            PaymentMethod1||Amount1||PaymentMethod2||Amount2||
            PaymentMethod3||Amount3||PaymentMethod4||Amount4||
            Reserved||Reserved||Reserved||Reserved
        """
        line_type_2_records = []

        try:
            # Get Z number from Z report
            z_number = z_report.get('z_number', '0')

            for txn in transactions:
                if not txn:
                    continue

                # Use parsed transaction fields
                doc_type = txn.get('doc_type', '0')

                # Filter out non-sale transactions
                # Valid document types: 0=sale, 1=refund, 2=void, 3=training
                # Skip system events (20, 21, 32, 40) and other special types
                try:
                    doc_type_int = int(doc_type)
                    if doc_type_int < 0 or doc_type_int > 3:
                        logger.debug(f"Skipping non-sale transaction with doc_type={doc_type}")
                        continue
                except (ValueError, TypeError):
                    logger.debug(f"Skipping transaction with invalid doc_type={doc_type}")
                    continue

                nkf = txn.get('nkf', '000000')
                txn_date = txn.get('date', '')
                txn_time = txn.get('time', '')
                customer_name = txn.get('customer_name', '')
                customer_crib = txn.get('customer_crib', '')
                subtotal = txn.get('subtotal', '0.00')
                discount = txn.get('discount', '0.00')
                surcharge = txn.get('surcharge', '0.00')
                service_charge = txn.get('service_charge', '0.00')
                tip = txn.get('tip', '0.00')
                tax_a_base = txn.get('tax_a_base', '0.00')
                tax_a_amount = txn.get('tax_a_amount', '0.00')
                tax_b_base = txn.get('tax_b_base', '0.00')
                tax_b_amount = txn.get('tax_b_amount', '0.00')
                total = txn.get('total', '0.00')
                payment_method = txn.get('payment_method', 'Cash')

                # Convert date to DD-MM-YYYY format if needed
                if txn_date and len(txn_date) == 8:
                    txn_date = f"{txn_date[0:2]}-{txn_date[2:4]}-{txn_date[4:8]}"

                # Convert time to HH:MM:SS format if needed
                if txn_time and len(txn_time) == 6:
                    txn_time = f"{txn_time[0:2]}:{txn_time[2:4]}:{txn_time[4:6]}"

                # Build Line Type 2 (40 fields)
                fields = [
                    "2",  # Line type
                    txn_date or "01-01-2025",  # Transaction date
                    txn_time or "00:00:00",  # Transaction time
                    doc_type,  # Document type (0=sale, 1=refund)
                    nkf,  # NKF
                    z_number,  # Z report number
                    customer_name,  # Customer name
                    customer_crib,  # Customer CRIB
                    "0",  # Item count (TODO: if available in fields)
                    subtotal,  # Subtotal
                    discount,  # Discount
                    surcharge,  # Surcharge
                    service_charge,  # Service charge
                    tip,  # Tip
                    tax_a_base,  # Tax A base
                    tax_a_amount,  # Tax A amount
                    tax_b_base,  # Tax B base
                    tax_b_amount,  # Tax B amount
                    "0.00",  # Tax C base
                    "0.00",  # Tax C amount
                    "0.00",  # Tax D base
                    "0.00",  # Tax D amount
                    "0.00",  # Tax E base
                    "0.00",  # Tax E amount
                    "0.00",  # Tax F base
                    "0.00",  # Tax F amount
                    "0.00",  # Exempt amount
                    total,  # Total
                    payment_method,  # Payment method 1
                    total,  # Amount 1 (same as total for single payment)
                    "",  # Payment method 2
                    "",  # Amount 2
                    "",  # Payment method 3
                    "",  # Amount 3
                    "",  # Payment method 4
                    "",  # Amount 4
                    "",  # Reserved
                    "",  # Reserved
                    "",  # Reserved
                    "",  # Reserved
                ]

                line_type_2_records.append("||".join(fields))

            return line_type_2_records

        except Exception as e:
            logger.error(f"Error building Line Type 2 records: {e}")
            return []

    def _build_line_type_3(self, year, month, sha1_hash):
        """
        Build CSV Line Type 3 (Monthly Sales Book Header)

        Args:
            year: 4-digit year
            month: 1-12
            sha1_hash: 40-character SHA-1 hash string

        Returns:
            String with 16 fields separated by ||

        Format:
            3||Monthly sales book||BusinessName||TaxNumber||Year||Month||
            FileCreationDate||FileCreationTime||SHA1Hash||
            DeviceSerialNumber||FiscalMemorySerialNumber||
            SoftwareName||SoftwareVersion||CertificationNumber||
            Reserved||Reserved
        """
        try:
            now = datetime.now()
            file_creation_date = now.strftime("%d-%m-%Y")
            file_creation_time = now.strftime("%H:%M:%S")

            fields = [
                "3",  # Line type
                "Monthly sales book",  # Description
                self.BUSINESS_NAME,
                self.TAX_NUMBER,
                str(year),
                str(month),
                file_creation_date,
                file_creation_time,
                sha1_hash,
                self.DEVICE_SERIAL,
                self.FISCAL_MEMORY_SERIAL,
                self.SOFTWARE_NAME,
                self.SOFTWARE_VERSION,
                self.CERTIFICATION_NUMBER,
                "",  # Reserved
                "",  # Reserved
            ]

            return "||".join(fields)

        except Exception as e:
            logger.error(f"Error building Line Type 3: {e}")
            return None

    def _calculate_sha1_hash(self, line_type_2_records):
        """
        Calculate SHA-1 hash from all Line Type 2 transaction records

        Args:
            line_type_2_records: List of Line Type 2 strings

        Returns:
            40-character hexadecimal SHA-1 hash string
        """
        try:
            # Concatenate all Line Type 2 records
            all_transactions = ''.join(line_type_2_records)

            # Calculate SHA-1 hash
            sha1_hash = hashlib.sha1(all_transactions.encode('utf-8')).hexdigest()

            logger.debug(f"SHA-1 hash calculated: {sha1_hash}")
            return sha1_hash

        except Exception as e:
            logger.error(f"Error calculating SHA-1 hash: {e}")
            return "0" * 40  # Return placeholder on error

    def _ensure_directory_structure(self, year, month, day=None):
        """
        Create directory structure: BASE_DIRECTORY\\Year\\Month\\Day\\

        Args:
            year: 4-digit year
            month: 1-12
            day: Day of month (optional, for daily files)

        Returns:
            Full directory path created, or None on error
        """
        try:
            month_name = self.MONTH_NAMES.get(month, str(month))

            if day:
                # Daily path: BASE_DIRECTORY\2025\December\20\
                dir_path = os.path.join(self.BASE_DIRECTORY, str(year), month_name, f"{day:02d}")
            else:
                # Monthly path: BASE_DIRECTORY\2025\December\
                dir_path = os.path.join(self.BASE_DIRECTORY, str(year), month_name)

            # Create directories if they don't exist
            os.makedirs(dir_path, exist_ok=True)

            logger.info(f"Directory ensured: {dir_path}")
            return dir_path

        except Exception as e:
            logger.error(f"Error creating directory structure: {e}")
            return None

    def _printer_date_to_csv_date(self, printer_date):
        """
        Convert printer date to CSV format

        Args:
            printer_date: DDMMYYYY format (e.g., "20122025")

        Returns:
            DD-MM-YYYY format (e.g., "20-12-2025")
        """
        try:
            if len(printer_date) == 8:
                dd = printer_date[0:2]
                mm = printer_date[2:4]
                yyyy = printer_date[4:8]
                return f"{dd}-{mm}-{yyyy}"
            else:
                return printer_date
        except Exception as e:
            logger.error(f"Error converting date: {e}")
            return printer_date
