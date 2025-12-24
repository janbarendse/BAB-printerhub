"""
Test script for Salesbook CSV Exporter

This script tests the salesbook CSV export functionality without
requiring a real printer or Z-report execution.
"""

import json
import os
import sys
import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.salesbook_exporter import SalesbookExporter


def create_sample_transaction():
    """Create a sample transaction for testing."""
    return {
        "receipt_number": "TEST-001",
        "pos_name": "Test POS",
        "customer_name": "Test Customer",
        "customer_crib": "123456789",
        "is_refund": False,
        "items": [
            {
                "product_code": "PROD001",
                "item_description": "Test Item 1",
                "quantity": 2,
                "price": 15.50,
                "vat_percentage": "6"
            },
            {
                "product_code": "PROD002",
                "item_description": "Test Item 2",
                "quantity": 1,
                "price": 25.00,
                "vat_percentage": "9"
            }
        ],
        "payments": [
            {
                "payment_method": "cash",
                "amount": 56.00
            }
        ],
        "discount": {
            "amount": 0
        },
        "surcharge": {
            "amount": 0
        },
        "service_charge": {
            "amount": 0
        },
        "tips": []
    }


def setup_test_environment():
    """Setup test environment with sample transactions."""
    print("Setting up test environment...")

    # Create transactions directory if it doesn't exist
    transactions_dir = os.path.join(os.path.dirname(__file__), 'transactions')
    Path(transactions_dir).mkdir(exist_ok=True)

    # Create sample transaction files for today
    today = datetime.date.today()
    date_str = today.strftime('%Y-%m-%d')

    for i in range(1, 4):
        filename = f"{date_str}_{datetime.datetime.now().strftime('%H-%M-%S')}_{i}.json"
        filepath = os.path.join(transactions_dir, filename)

        transaction = create_sample_transaction()
        transaction["receipt_number"] = f"TEST-{i:03d}"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(transaction, f, indent=4)

        print(f"  Created: {filename}")

    print(f"Created {3} sample transaction files")


def test_csv_export():
    """Test the CSV export functionality."""
    print("\n" + "="*60)
    print("TESTING SALESBOOK CSV EXPORT")
    print("="*60)

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"\n[OK] Config loaded from: {config_path}")
    except Exception as e:
        print(f"\n[ERROR] Failed to load config: {e}")
        return False

    # Display salesbook config
    salesbook_config = config.get('salesbook', {})
    print("\nSalesbook Configuration:")
    print(f"  Enabled: {salesbook_config.get('csv_export_enabled')}")
    print(f"  Export Path: {salesbook_config.get('csv_export_path')}")
    print(f"  Auto Export: {salesbook_config.get('auto_export_on_z_report')}")
    print(f"  Include Details: {salesbook_config.get('include_transaction_details')}")

    # Create exporter instance
    try:
        exporter = SalesbookExporter(config)
        print("\n[OK] SalesbookExporter initialized")
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize exporter: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test export directory creation
    try:
        result = exporter.ensure_export_directory()
        if result:
            print(f"[OK] Export directory ready: {exporter.export_path}")
        else:
            print(f"[ERROR] Failed to create export directory")
            return False
    except Exception as e:
        print(f"[ERROR] Error creating export directory: {e}")
        return False

    # Read transaction files
    print("\nReading transaction files...")
    try:
        transactions = exporter.read_transaction_files()
        print(f"[OK] Found {len(transactions)} transaction(s) for today")

        if len(transactions) == 0:
            print("  Note: No transactions found. Run setup_test_environment() first.")
            return False

    except Exception as e:
        print(f"[ERROR] Error reading transactions: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test summary export
    print("\nExporting summary CSV...")
    try:
        summary_file = exporter.export_transactions_summary()
        if summary_file:
            print(f"[OK] Summary CSV exported: {summary_file}")
            print(f"  File size: {os.path.getsize(summary_file)} bytes")
        else:
            print("[ERROR] Failed to export summary CSV")
            return False
    except Exception as e:
        print(f"[ERROR] Error exporting summary: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test details export
    print("\nExporting details CSV...")
    try:
        details_file = exporter.export_transactions_detailed()
        if details_file:
            print(f"[OK] Details CSV exported: {details_file}")
            print(f"  File size: {os.path.getsize(details_file)} bytes")
        else:
            print("[ERROR] Failed to export details CSV")
            return False
    except Exception as e:
        print(f"[ERROR] Error exporting details: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test complete export
    print("\nTesting complete daily salesbook export...")
    try:
        result = exporter.export_daily_salesbook()
        if result.get("success"):
            print("[OK] Daily salesbook export completed")
            print(f"  Summary: {result.get('summary_file')}")
            print(f"  Details: {result.get('details_file')}")
        else:
            print(f"[ERROR] Export failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"[ERROR] Error in daily export: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*60)
    print("ALL TESTS PASSED!")
    print("="*60)
    print(f"\nCSV files are available in: {exporter.export_path}")
    print("You can open them in Excel or any CSV viewer.")
    return True


if __name__ == "__main__":
    print("Salesbook CSV Export Test Script")
    print("-" * 60)

    # Setup test environment
    setup_test_environment()

    # Run tests
    success = test_csv_export()

    if success:
        print("\n[SUCCESS] All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n[FAILED] Some tests failed. Check the output above.")
        sys.exit(1)
