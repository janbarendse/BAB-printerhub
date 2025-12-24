r"""
Salesbook CSV Exporter for BAB PrinterHub

Exports transaction data to CSV files in the configured directory (C:\Fbook by default).
Automatically generates CSV files after Z-report printing.
"""

import os
import json
import csv
import datetime
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SalesbookExporter:
    """
    Exports transaction data from JSON files to CSV format.

    Creates CSV files with transaction details including:
    - Transaction date/time
    - Receipt number
    - Items sold with prices and VAT
    - Payment methods
    - Totals
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the salesbook exporter.

        Args:
            config: Configuration dictionary containing salesbook settings
        """
        self.config = config
        salesbook_config = config.get('salesbook', {})

        self.enabled = salesbook_config.get('csv_export_enabled', True)
        self.export_path = salesbook_config.get('csv_export_path', 'C:\\Fbook')
        self.auto_export = salesbook_config.get('auto_export_on_z_report', True)
        self.include_details = salesbook_config.get('include_transaction_details', True)

        # Get base directory for transactions
        from .config_manager import get_base_dir
        self.base_dir = get_base_dir()
        self.transactions_dir = os.path.join(self.base_dir, 'transactions')

        logger.info(f"Salesbook exporter initialized: enabled={self.enabled}, path={self.export_path}")

    def ensure_export_directory(self) -> bool:
        """
        Ensure the export directory exists, create if needed.

        Returns:
            bool: True if directory exists or was created successfully
        """
        try:
            Path(self.export_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"Export directory ready: {self.export_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create export directory {self.export_path}: {e}")
            return False

    def read_transaction_files(self, date: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
        """
        Read transaction JSON files for a specific date.

        Args:
            date: Date to read transactions for (defaults to today)

        Returns:
            List of transaction dictionaries
        """
        if date is None:
            date = datetime.date.today()

        date_str = date.strftime('%Y-%m-%d')
        transactions = []

        if not os.path.exists(self.transactions_dir):
            logger.warning(f"Transactions directory not found: {self.transactions_dir}")
            return transactions

        try:
            for filename in os.listdir(self.transactions_dir):
                if filename.startswith(date_str) and filename.endswith('.json'):
                    file_path = os.path.join(self.transactions_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            transaction = json.load(f)
                            transaction['_filename'] = filename
                            transactions.append(transaction)
                    except Exception as e:
                        logger.error(f"Failed to read transaction file {filename}: {e}")

            logger.info(f"Read {len(transactions)} transaction(s) for date {date_str}")
            return transactions

        except Exception as e:
            logger.error(f"Error reading transaction files: {e}")
            return transactions

    def export_transactions_summary(self, date: Optional[datetime.date] = None) -> Optional[str]:
        """
        Export daily transaction summary to CSV.

        Creates a summary CSV with one row per transaction showing totals.

        Args:
            date: Date to export (defaults to today)

        Returns:
            str: Path to created CSV file, or None if failed
        """
        if not self.enabled:
            logger.info("Salesbook export is disabled in config")
            return None

        if not self.ensure_export_directory():
            return None

        if date is None:
            date = datetime.date.today()

        date_str = date.strftime('%Y-%m-%d')
        transactions = self.read_transaction_files(date)

        if not transactions:
            logger.warning(f"No transactions found for {date_str}, skipping CSV export")
            return None

        # Generate CSV filename
        csv_filename = f"salesbook_summary_{date_str}.csv"
        csv_path = os.path.join(self.export_path, csv_filename)

        try:
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    'Date', 'Time', 'Receipt_Number', 'POS', 'Customer_Name', 'Customer_CRIB',
                    'Subtotal', 'Discount', 'Surcharge', 'Service_Charge', 'Tips', 'Total',
                    'Payment_Method_1', 'Payment_Amount_1', 'Payment_Method_2', 'Payment_Amount_2',
                    'Is_Refund', 'Item_Count'
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for transaction in transactions:
                    row = self._extract_transaction_summary(transaction)
                    writer.writerow(row)

            logger.info(f"Exported {len(transactions)} transactions to {csv_path}")
            return csv_path

        except Exception as e:
            logger.error(f"Failed to export transactions summary: {e}")
            return None

    def export_transactions_detailed(self, date: Optional[datetime.date] = None) -> Optional[str]:
        """
        Export detailed transaction data to CSV with one row per line item.

        Args:
            date: Date to export (defaults to today)

        Returns:
            str: Path to created CSV file, or None if failed
        """
        if not self.enabled or not self.include_details:
            return None

        if not self.ensure_export_directory():
            return None

        if date is None:
            date = datetime.date.today()

        date_str = date.strftime('%Y-%m-%d')
        transactions = self.read_transaction_files(date)

        if not transactions:
            return None

        # Generate CSV filename
        csv_filename = f"salesbook_details_{date_str}.csv"
        csv_path = os.path.join(self.export_path, csv_filename)

        try:
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    'Date', 'Time', 'Receipt_Number', 'POS', 'Customer_Name', 'Customer_CRIB',
                    'Line_Number', 'Product_Code', 'Item_Description', 'Quantity', 'Unit_Price',
                    'VAT_Rate', 'VAT_Amount', 'Line_Total', 'Is_Refund'
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for transaction in transactions:
                    rows = self._extract_transaction_details(transaction)
                    for row in rows:
                        writer.writerow(row)

            logger.info(f"Exported detailed transactions to {csv_path}")
            return csv_path

        except Exception as e:
            logger.error(f"Failed to export detailed transactions: {e}")
            return None

    def _extract_transaction_summary(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Extract summary data from a transaction."""
        # Parse timestamp from filename
        filename = transaction.get('_filename', '')
        date_time_str = '_'.join(filename.split('_')[:2]) if filename else ''

        try:
            if date_time_str:
                dt = datetime.datetime.strptime(date_time_str, '%Y-%m-%d_%H-%M-%S')
                date_str = dt.strftime('%Y-%m-%d')
                time_str = dt.strftime('%H:%M:%S')
            else:
                date_str = datetime.date.today().strftime('%Y-%m-%d')
                time_str = datetime.datetime.now().strftime('%H:%M:%S')
        except:
            date_str = datetime.date.today().strftime('%Y-%m-%d')
            time_str = datetime.datetime.now().strftime('%H:%M:%S')

        # Extract basic info
        receipt_number = transaction.get('receipt_number', '')
        pos_name = transaction.get('pos_name', '')
        customer_name = transaction.get('customer_name', '')
        customer_crib = transaction.get('customer_crib', '')
        is_refund = transaction.get('is_refund', False)

        # Calculate totals
        items = transaction.get('items', [])
        payments = transaction.get('payments', [])

        subtotal = sum(float(item.get('price', 0)) * float(item.get('quantity', 1))
                      for item in items)

        discount = float(transaction.get('discount', {}).get('amount', 0))
        surcharge = float(transaction.get('surcharge', {}).get('amount', 0))
        service_charge = float(transaction.get('service_charge', {}).get('amount', 0))

        tips = sum(float(tip.get('amount', 0)) for tip in transaction.get('tips', []))

        total = subtotal - discount + surcharge + service_charge

        # Extract payment methods
        payment_method_1 = payments[0].get('payment_method', '') if len(payments) > 0 else ''
        payment_amount_1 = float(payments[0].get('amount', 0)) if len(payments) > 0 else 0
        payment_method_2 = payments[1].get('payment_method', '') if len(payments) > 1 else ''
        payment_amount_2 = float(payments[1].get('amount', 0)) if len(payments) > 1 else 0

        return {
            'Date': date_str,
            'Time': time_str,
            'Receipt_Number': receipt_number,
            'POS': pos_name,
            'Customer_Name': customer_name,
            'Customer_CRIB': customer_crib,
            'Subtotal': f"{subtotal:.2f}",
            'Discount': f"{discount:.2f}",
            'Surcharge': f"{surcharge:.2f}",
            'Service_Charge': f"{service_charge:.2f}",
            'Tips': f"{tips:.2f}",
            'Total': f"{total:.2f}",
            'Payment_Method_1': payment_method_1,
            'Payment_Amount_1': f"{payment_amount_1:.2f}",
            'Payment_Method_2': payment_method_2,
            'Payment_Amount_2': f"{payment_amount_2:.2f}",
            'Is_Refund': 'Yes' if is_refund else 'No',
            'Item_Count': len(items)
        }

    def _extract_transaction_details(self, transaction: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract detailed line items from a transaction."""
        # Parse timestamp from filename
        filename = transaction.get('_filename', '')
        date_time_str = '_'.join(filename.split('_')[:2]) if filename else ''

        try:
            if date_time_str:
                dt = datetime.datetime.strptime(date_time_str, '%Y-%m-%d_%H-%M-%S')
                date_str = dt.strftime('%Y-%m-%d')
                time_str = dt.strftime('%H:%M:%S')
            else:
                date_str = datetime.date.today().strftime('%Y-%m-%d')
                time_str = datetime.datetime.now().strftime('%H:%M:%S')
        except:
            date_str = datetime.date.today().strftime('%Y-%m-%d')
            time_str = datetime.datetime.now().strftime('%H:%M:%S')

        # Extract basic info
        receipt_number = transaction.get('receipt_number', '')
        pos_name = transaction.get('pos_name', '')
        customer_name = transaction.get('customer_name', '')
        customer_crib = transaction.get('customer_crib', '')
        is_refund = transaction.get('is_refund', False)

        items = transaction.get('items', [])
        rows = []

        for line_num, item in enumerate(items, start=1):
            product_code = item.get('product_code', '')
            description = item.get('item_description', '')
            quantity = float(item.get('quantity', 1))
            unit_price = float(item.get('price', 0))
            vat_rate = item.get('vat_percentage', '')

            line_total = unit_price * quantity

            # Calculate VAT amount (simplified)
            try:
                vat_pct = float(vat_rate) if vat_rate else 0
                vat_amount = line_total * (vat_pct / (100 + vat_pct))
            except:
                vat_amount = 0

            rows.append({
                'Date': date_str,
                'Time': time_str,
                'Receipt_Number': receipt_number,
                'POS': pos_name,
                'Customer_Name': customer_name,
                'Customer_CRIB': customer_crib,
                'Line_Number': line_num,
                'Product_Code': product_code,
                'Item_Description': description,
                'Quantity': f"{quantity:.2f}",
                'Unit_Price': f"{unit_price:.2f}",
                'VAT_Rate': f"{vat_rate}%" if vat_rate else "",
                'VAT_Amount': f"{vat_amount:.2f}",
                'Line_Total': f"{line_total:.2f}",
                'Is_Refund': 'Yes' if is_refund else 'No'
            })

        return rows

    def export_daily_salesbook(self, date: Optional[datetime.date] = None) -> Dict[str, Any]:
        """
        Export complete daily salesbook (summary + details).

        Args:
            date: Date to export (defaults to today)

        Returns:
            dict: {"success": bool, "summary_file": str, "details_file": str, "error": str}
        """
        if not self.enabled:
            return {"success": False, "error": "CSV export is disabled in config"}

        try:
            summary_file = self.export_transactions_summary(date)
            details_file = self.export_transactions_detailed(date)

            if summary_file or details_file:
                return {
                    "success": True,
                    "summary_file": summary_file,
                    "details_file": details_file
                }
            else:
                return {"success": False, "error": "No transactions to export"}

        except Exception as e:
            logger.error(f"Failed to export daily salesbook: {e}")
            return {"success": False, "error": str(e)}


def export_salesbook_after_z_report(config: Dict[str, Any], date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    Export salesbook CSV files after Z-report is printed.

    This is called automatically after Z-report printing to export
    the day's transactions to CSV format.

    Args:
        config: Configuration dictionary
        date: Date to export (defaults to today)

    Returns:
        dict: Export result with success status and file paths
    """
    try:
        exporter = SalesbookExporter(config)

        if not exporter.auto_export:
            logger.info("Auto-export is disabled, skipping salesbook export")
            return {"success": False, "error": "Auto-export disabled"}

        result = exporter.export_daily_salesbook(date)
        return result

    except Exception as e:
        logger.error(f"Error in export_salesbook_after_z_report: {e}")
        return {"success": False, "error": str(e)}
