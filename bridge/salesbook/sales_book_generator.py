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
        self.CLIENT_CRIB = self.config.get('client', {}).get('NKF', {}).get('crib_number', '')
        self.CASH_REGISTER = self.config.get('client', {}).get('NKF', {}).get('cash_register', '')

        # Get salesbook-specific config
        salesbook_config = self.config.get('salesbook', {})
        self.BASE_DIRECTORY = salesbook_config.get('csv_export_path', 'C:\\FBOOK')
        self.INCLUDE_SHA1 = salesbook_config.get('include_sha1_hash', True)
        self.INCLUDE_TRANSACTION_DETAILS = salesbook_config.get('include_transaction_details', True)
        self.RETAILER_TAXPAYER_ID = salesbook_config.get(
            'taxpayer_id',
            self.config.get('business', {}).get('tax_number', ''),
        )
        self.BRANCH_CODE = str(salesbook_config.get('branch_code', '0'))
        self.POS_NUMBER = str(salesbook_config.get('pos_number', self.CASH_REGISTER or '0'))
        self.FISCAL_DEVICE_ID = salesbook_config.get('fiscal_device_id')
        self.PROGRAM_PROVIDER = salesbook_config.get(
            'program_provider',
            self.config.get('business', {}).get('software_name', self.SOFTWARE_NAME),
        )
        self.TIP_LEGAL = str(salesbook_config.get('tip_legal', '2'))
        self.DAILY_FILENAME_TEMPLATE = salesbook_config.get('daily_filename_template', 'SB{date}.001')
        self.MONTHLY_FILENAME_TEMPLATE = salesbook_config.get('monthly_filename_template', 'SB{year}{month:02d}.001')
        self.DEFAULT_CLIENT_CRIB = self.config.get('miscellaneous', {}).get('default_client_crib', '1000000000')

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
            line_type_2_records = self._build_line_type_2_records(transactions)
            line_type_1_fields = self._build_line_type_1_fields(z_report, line_type_2_records)
            line_type_2_lines = [self._join_fields(record["fields"]) for record in line_type_2_records]

            if self.INCLUDE_SHA1:
                line_type_1_fields[1] = ""
                hash_input_lines = [self._join_fields(line_type_1_fields)] + line_type_2_lines
                sha1_hash = self._calculate_sha1_hash(hash_input_lines)
                line_type_1_fields[1] = sha1_hash
            else:
                sha1_hash = ""

            line_type_1 = self._join_fields(line_type_1_fields)

            # Create directory structure
            file_path = self._ensure_daily_directory(year, month, day)

            if not file_path:
                logger.error("Failed to create directory structure")
                return None

            # Build filename
            csv_filename = self._build_daily_filename(date_obj)
            full_path = os.path.join(file_path, csv_filename)

            # Write CSV file
            with open(full_path, 'w', encoding='utf-8') as f:
                # Write Line Type 1 (daily header)
                f.write(line_type_1 + "\r\n")

                # Write Line Type 2 records (transactions)
                for line in line_type_2_lines:
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

            # Group Z reports by date (YYYYMMDD)
            z_reports_by_date = {}
            for z_report in z_reports:
                report_date = self._normalize_printer_date(z_report.get('date', ''))
                if report_date and report_date not in z_reports_by_date:
                    z_reports_by_date[report_date] = z_report

            # Group transactions by date (YYYYMMDD)
            transactions_by_date = {}
            for txn in transactions:
                txn_date = self._normalize_printer_date(txn.get('date', ''))
                if not txn_date:
                    continue
                transactions_by_date.setdefault(txn_date, []).append(txn)

            # Build all CSV lines
            all_line_type_1 = []
            all_line_type_2 = []
            all_records = []

            for day_key in sorted(z_reports_by_date.keys()):
                z_report = z_reports_by_date[day_key]
                day_transactions = transactions_by_date.get(day_key, [])

                day_records = self._build_line_type_2_records(day_transactions)
                day_lines = [self._join_fields(record["fields"]) for record in day_records]
                line_type_1_fields = self._build_line_type_1_fields(z_report, day_records)

                if self.INCLUDE_SHA1:
                    line_type_1_fields[1] = ""
                    day_hash = self._calculate_sha1_hash([self._join_fields(line_type_1_fields)] + day_lines)
                    line_type_1_fields[1] = day_hash

                all_line_type_1.append(self._join_fields(line_type_1_fields))
                all_line_type_2.extend(day_lines)
                all_records.extend(day_records)

            line_type_3_fields = self._build_line_type_3_fields(all_records)
            line_type_3_fields[1] = "" if self.INCLUDE_SHA1 else line_type_3_fields[1]

            if self.INCLUDE_SHA1:
                hash_input_lines = [self._join_fields(line_type_3_fields)] + all_line_type_1 + all_line_type_2
                sha1_hash = self._calculate_sha1_hash(hash_input_lines)
                line_type_3_fields[1] = sha1_hash
            else:
                sha1_hash = ""

            line_type_3 = self._join_fields(line_type_3_fields)

            # Create directory structure
            file_path = self._ensure_monthly_directory(year, month)

            if not file_path:
                logger.error("Failed to create directory structure")
                return None

            # Build filename
            csv_filename = self._build_monthly_filename(year, month)
            full_path = os.path.join(file_path, csv_filename)

            # Write CSV file
            with open(full_path, 'w', encoding='utf-8') as f:
                # Line Type 3 (monthly header)
                f.write(line_type_3 + "\r\n")

                # Line Type 1 (daily headers)
                for line1 in all_line_type_1:
                    f.write(line1 + "\r\n")

                # Line Type 2 records
                for line2 in all_line_type_2:
                    f.write(line2 + "\r\n")

            logger.info(f"Monthly sales book generated: {full_path}")
            logger.info(f"  Z reports: {len(all_line_type_1)}")
            logger.info(f"  Transactions: {len(all_line_type_2)}")
            if self.INCLUDE_SHA1:
                logger.info(f"  SHA-1 hash: {sha1_hash}")

            return full_path

        except Exception as e:
            logger.error(f"Error generating monthly sales book: {e}")
            return None

    def _build_line_type_1_fields(self, z_report, line_type_2_records):
        """
        Build Line Type 1 fields (Daily Sales Book Header) per spec.
        """
        try:
            totals = self._summarize_records(line_type_2_records)
            first_nkk, last_nkk = self._find_nkk_bounds(line_type_2_records)
            z_number = z_report.get('z_number', '')

            fields = [
                "1",
                "",
                self._get_fiscal_device_id(),
                str(totals["count"]),
                self._format_amount(totals["amount_total"]),
                self._format_amount(totals["iva_total"]),
                self._format_amount(totals["iva_tax1"]),
                self._format_amount(totals["iva_tax2"]),
                self._format_amount(totals["iva_tax3"]),
                self._format_amount(totals["amount_final_consumer"]),
                self._format_amount(totals["iva_final_consumer"]),
                self._format_amount(totals["amount_final_consumer"]),
                self._format_amount(totals["amount_fiscal"]),
                self._format_amount(totals["iva_fiscal"]),
                self._format_amount(totals["amount_fiscal"]),
                self._format_amount(totals["amount_credit_final"]),
                self._format_amount(totals["iva_credit_final"]),
                self._format_amount(totals["amount_credit_final"]),
                self._format_amount(totals["amount_credit_fiscal"]),
                self._format_amount(totals["iva_credit_fiscal"]),
                self._format_amount(totals["amount_credit_fiscal"]),
                self._format_count(0),
                first_nkk,
                last_nkk,
                z_number,
                self.PROGRAM_PROVIDER,
                self.SOFTWARE_VERSION,
                self.TIP_LEGAL,
            ]

            return fields
        except Exception as e:
            logger.error(f"Error building Line Type 1: {e}")
            return None

    def _build_line_type_2_records(self, transactions):
        """
        Build Line Type 2 record dicts (Transaction Records) per spec.
        """
        records = []

        try:
            for txn in transactions:
                if not txn:
                    continue

                doc_type = self._map_doc_type(txn)
                if doc_type is None:
                    continue

                nkk_number = self._format_nkk(txn.get('nkf', ''))
                txn_date = self._to_csv_yyyymmdd(txn.get('date', ''))
                txn_time = self._to_csv_hhmmss(txn.get('time', ''))
                customer_crib = self._format_taxpayer_id(
                    txn.get('customer_crib', '') or self.DEFAULT_CLIENT_CRIB
                )
                nkf = self._format_nkf(txn.get('client_field', '') or "")
                nkf_affected = self._format_nkf("")

                amount_total = self._format_amount(txn.get('total'))
                iva_total = self._format_amount(self._sum_numeric_fields(
                    txn.get('tax_a_amount'),
                    txn.get('tax_b_amount'),
                ))
                tax1_amount = self._format_amount(txn.get('tax_a_base'))
                tax1_iva = self._format_amount(txn.get('tax_a_amount'))
                tax2_amount = self._format_amount(txn.get('tax_b_base'))
                tax2_iva = self._format_amount(txn.get('tax_b_amount'))
                tax3_amount = self._format_amount(0)
                tax3_iva = self._format_amount(0)

                subtotal = self._safe_float(txn.get('subtotal'))
                service_charge = self._safe_float(txn.get('service_charge'))
                service_charge_pct = self._format_amount(
                    (service_charge / subtotal * 100) if subtotal else 0
                )

                discount_amount = self._format_amount(txn.get('discount'))
                donation_amount = self._format_amount(0)
                exempt_qty = self._format_count(0)

                payment_amounts = self._payment_amounts(txn.get('payment_method', ''), amount_total)

                fields = [
                    "2",
                    self._format_taxpayer_id(self.RETAILER_TAXPAYER_ID),
                    self._format_code(self.BRANCH_CODE, 4),
                    self._format_code(self.POS_NUMBER, 4),
                    nkk_number,
                    txn_date,
                    txn_time,
                    str(doc_type),
                    self._format_code(0, 3),
                    customer_crib,
                    nkf,
                    nkf_affected,
                    amount_total,
                    iva_total,
                    self._format_code(0, 6),
                    tax1_amount,
                    tax1_iva,
                    self._format_code(0, 6),
                    tax2_amount,
                    tax2_iva,
                    self._format_code(0, 6),
                    tax3_amount,
                    tax3_iva,
                    self._format_code(0, 6),
                    service_charge_pct,
                    self._format_amount(service_charge),
                    discount_amount,
                    donation_amount,
                    self._format_code(exempt_qty, 6),
                    *payment_amounts,
                    self.TIP_LEGAL,
                ]

                records.append({
                    "fields": fields,
                    "doc_type": doc_type,
                    "amount": self._safe_float(amount_total),
                    "iva_total": self._safe_float(iva_total),
                    "iva_tax1": self._safe_float(tax1_iva),
                    "iva_tax2": self._safe_float(tax2_iva),
                    "iva_tax3": self._safe_float(tax3_iva),
                    "nkk": nkk_number,
                })

            return records

        except Exception as e:
            logger.error(f"Error building Line Type 2 records: {e}")
            return []

    def _build_line_type_3_fields(self, line_type_2_records):
        """
        Build Line Type 3 fields (Monthly Sales Book Header) per spec.
        """
        try:
            totals = self._summarize_records(line_type_2_records)
            fields = [
                "3",
                "",
                str(totals["count"]),
                self._format_amount(totals["amount_total"]),
                self._format_amount(totals["iva_total"]),
                self._format_amount(totals["iva_tax1"]),
                self._format_amount(totals["iva_tax2"]),
                self._format_amount(totals["iva_tax3"]),
                self._format_amount(totals["amount_final_consumer"]),
                self._format_amount(totals["iva_final_consumer"]),
                self._format_amount(totals["amount_fiscal"]),
                self._format_amount(totals["iva_fiscal"]),
                self._format_amount(totals["amount_credit_final"]),
                self._format_amount(totals["iva_credit_final"]),
                self._format_amount(totals["amount_credit_fiscal"]),
                self._format_amount(totals["iva_credit_fiscal"]),
            ]
            return fields
        except Exception as e:
            logger.error(f"Error building Line Type 3: {e}")
            return None

    def _calculate_sha1_hash(self, lines):
        """
        Calculate SHA-1 hash from all lines in the file.
        """
        try:
            content = "\r\n".join(lines)
            sha1_hash = hashlib.sha1(content.encode('utf-8')).hexdigest()
            logger.debug(f"SHA-1 hash calculated: {sha1_hash}")
            return sha1_hash
        except Exception as e:
            logger.error(f"Error calculating SHA-1 hash: {e}")
            return "0" * 40

    def _ensure_daily_directory(self, year, month, day):
        try:
            dir_path = os.path.join(self.BASE_DIRECTORY, str(year), f"{month:02d}", f"{day:02d}")
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Directory ensured: {dir_path}")
            return dir_path
        except Exception as e:
            logger.error(f"Error creating directory structure: {e}")
            return None

    def _ensure_monthly_directory(self, year, month):
        try:
            dir_path = os.path.join(self.BASE_DIRECTORY, str(year), f"{month:02d}")
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

    def _build_daily_filename(self, date_obj):
        return self.DAILY_FILENAME_TEMPLATE.format(date=date_obj.strftime("%Y%m%d"))

    def _build_monthly_filename(self, year, month):
        return self.MONTHLY_FILENAME_TEMPLATE.format(year=year, month=month)

    @staticmethod
    def _join_fields(fields):
        return "||".join(fields)

    def _get_fiscal_device_id(self):
        value = self.FISCAL_DEVICE_ID
        if not value:
            value = str(self.DEVICE_SERIAL or "")[-6:]
        return self._format_code(value, 6)

    @staticmethod
    def _format_code(value, length):
        cleaned = "".join(ch for ch in str(value) if ch.isdigit())
        return cleaned.zfill(length) if cleaned else "0".zfill(length)

    def _format_taxpayer_id(self, value):
        cleaned = "".join(ch for ch in str(value) if ch.isdigit())
        return cleaned.zfill(14) if cleaned else "0".zfill(14)

    @staticmethod
    def _format_count(value):
        try:
            return str(int(value))
        except Exception:
            return "0"

    @staticmethod
    def _format_amount(value):
        try:
            return f"{float(value):.2f}"
        except Exception:
            return "0.00"

    @staticmethod
    def _sum_numeric_fields(*values):
        total = 0.0
        for value in values:
            try:
                total += float(value)
            except Exception:
                continue
        return total

    @staticmethod
    def _safe_float(value):
        try:
            return float(value)
        except Exception:
            return 0.0

    def _map_doc_type(self, txn):
        doc_type_raw = txn.get('doc_type')
        try:
            doc_type_raw = int(doc_type_raw)
        except Exception:
            doc_type_raw = 0

        customer_crib = (txn.get('customer_crib') or "").strip()
        is_fiscal_credit = customer_crib and customer_crib != self.DEFAULT_CLIENT_CRIB
        is_refund = doc_type_raw == 1

        if is_refund:
            return 4 if is_fiscal_credit else 3
        if doc_type_raw == 0:
            return 2 if is_fiscal_credit else 1
        return None

    def _payment_amounts(self, payment_method, amount_total):
        amounts = ["0.00"] * 10
        amount_value = self._format_amount(amount_total)
        value = (payment_method or "").strip().lower()

        if "cash" in value:
            amounts[0] = amount_value
        elif "cheque" in value:
            amounts[1] = amount_value
        elif "credit" in value:
            amounts[2] = amount_value
        elif "debit" in value:
            amounts[3] = amount_value
        elif "note" in value:
            amounts[4] = amount_value
        elif "coupon" in value:
            amounts[5] = amount_value
        else:
            amounts[6] = amount_value

        return amounts

    def _summarize_records(self, records):
        totals = {
            "count": len(records),
            "amount_total": 0.0,
            "iva_total": 0.0,
            "iva_tax1": 0.0,
            "iva_tax2": 0.0,
            "iva_tax3": 0.0,
            "amount_final_consumer": 0.0,
            "iva_final_consumer": 0.0,
            "amount_fiscal": 0.0,
            "iva_fiscal": 0.0,
            "amount_credit_final": 0.0,
            "iva_credit_final": 0.0,
            "amount_credit_fiscal": 0.0,
            "iva_credit_fiscal": 0.0,
        }

        for record in records:
            amount = record["amount"]
            iva_total = record["iva_total"]
            totals["amount_total"] += amount
            totals["iva_total"] += iva_total
            totals["iva_tax1"] += record["iva_tax1"]
            totals["iva_tax2"] += record["iva_tax2"]
            totals["iva_tax3"] += record["iva_tax3"]

            if record["doc_type"] == 1:
                totals["amount_final_consumer"] += amount
                totals["iva_final_consumer"] += iva_total
            elif record["doc_type"] == 2:
                totals["amount_fiscal"] += amount
                totals["iva_fiscal"] += iva_total
            elif record["doc_type"] == 3:
                totals["amount_credit_final"] += amount
                totals["iva_credit_final"] += iva_total
            elif record["doc_type"] == 4:
                totals["amount_credit_fiscal"] += amount
                totals["iva_credit_fiscal"] += iva_total

        return totals

    @staticmethod
    def _find_nkk_bounds(records):
        nkk_values = [record["nkk"] for record in records if record.get("nkk")]
        if not nkk_values:
            return "", ""
        numeric_values = [n for n in nkk_values if n.isdigit()]
        if numeric_values:
            return min(numeric_values), max(numeric_values)
        return min(nkk_values), max(nkk_values)

    def _format_nkk(self, value):
        cleaned = "".join(ch for ch in str(value) if ch.isdigit())
        if cleaned:
            return cleaned.zfill(16)
        return ""

    def _format_nkf(self, value):
        text = str(value).strip()
        if not text:
            return ""
        if text.isdigit():
            return text.zfill(19)
        return text

    def _to_csv_yyyymmdd(self, printer_date):
        try:
            if len(printer_date) == 8:
                return f"{printer_date[4:8]}{printer_date[2:4]}{printer_date[0:2]}"
            if len(printer_date) == 6:
                return f"20{printer_date[4:6]}{printer_date[2:4]}{printer_date[0:2]}"
        except Exception:
            pass
        return printer_date

    def _to_csv_hhmmss(self, printer_time):
        try:
            if len(printer_time) == 6:
                return printer_time
        except Exception:
            pass
        return printer_time

    def _normalize_printer_date(self, printer_date):
        if not printer_date:
            return ""
        if len(printer_date) == 8:
            return self._to_csv_yyyymmdd(printer_date)
        if len(printer_date) == 6:
            return self._to_csv_yyyymmdd(printer_date)
        return ""
