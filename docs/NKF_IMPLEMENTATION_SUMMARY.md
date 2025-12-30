# NKF Dynamic Generation - Implementation Summary

## Overview
Successfully implemented dynamic NKF (Number di Komprobante Fiskal) generation across all printer drivers, replacing the static placeholder with a proper dynamic system based on the fiscal requirements.

## NKF Structure (19 characters)
- **Source of document** (1 char): `A` (from config)
- **CRIB number** (9 digits): `122202235` (from config)
- **Cash register/printer number** (2 digits): `11` (from config)
- **Type of receipt/invoice** (1 digit): `1`, `2` (credit note), `3`, or `4` (credit note)
- **Sequential number** (6 digits): Padded from `last_order_id`

### Example NKFs
```
A122202235111000417  (Type 1, Order 417)
A122202235112000417  (Type 2, Order 417)
A122202235113000417  (Type 3, Order 417)
A122202235114000417  (Type 4, Order 417)
```

## Files Changed

### 1. Configuration (`config.json`)
**Before:**
```json
"client": {
  "NKF": "1234567890123456789"
}
```

**After:**
```json
"client": {
  "NKF": {
    "source": "A",
    "crib_number": "122202235",
    "cash_register": "11"
  }
}
```

### 2. New Utility Module (`core/fiscal_utils.py`)
Created a new fiscal utilities module with:
- `generate_nkf(nkf_config, document_type, last_order_id)` - Generates dynamic NKF
- `parse_nkf(nkf)` - Parses NKF string into components

### 3. Printer Drivers Updated
Updated all three printer drivers to use dynamic NKF generation:

#### CTS310ii Driver (`printers/cts310ii/cts310ii_driver.py`)
- Added import for `generate_nkf`
- Updated `print_document()` method to generate NKF dynamically
- Updated `print_no_sale()` method to generate NKF dynamically

#### Citizen Driver (`printers/citizen/citizen_driver.py`)
- Added import for `generate_nkf`
- Updated `print_document()` method to generate NKF dynamically
- Updated `print_no_sale()` method to generate NKF dynamically

#### Star Driver (`printers/star/star_driver.py`)
- Added import for `generate_nkf`
- Updated `print_document()` method to generate NKF dynamically
- Updated `print_no_sale()` method to generate NKF dynamically

## Code Changes in Drivers

### Before:
```python
# Get client NKF
client_nkf = self.client_config.get("NKF", "")
```

### After:
```python
# Generate dynamic NKF
nkf_config = self.client_config.get("NKF", {})

# Get last_order_id from active software config
software_config = self.config.get('software', {})
active_software = software_config.get('active', 'odoo')
last_order_id = software_config.get(active_software, {}).get('last_order_id', 0)

# Generate NKF using fiscal_utils
client_nkf = generate_nkf(nkf_config, doc_type, last_order_id)
logger.info(f"Generated NKF: {client_nkf} (type={doc_type}, order_id={last_order_id})")
```

## Testing

Created comprehensive test suite (`test_nkf_integration.py`) that validates:
1. ✅ Config structure is correct
2. ✅ NKF generation for all document types (1, 2, 3, 4)
3. ✅ All three printer drivers import successfully
4. ✅ Driver initialization and NKF generation in driver context

### Test Results
```
[OK] CTS310ii driver imports successfully
[OK] Citizen driver imports successfully
[OK] Star driver imports successfully
[OK] Driver context NKF generation: A122202235111000417
```

## Document Type Mapping

| Type | Description | Usage |
|------|-------------|-------|
| 1 | Invoice Final Consumer | Regular invoices without customer |
| 2 | Invoice Fiscal Credit | Invoices with customer present |
| 3 | Credit Note Final Consumer | Refunds without customer |
| 4 | Credit Note Fiscal | Refunds with customer present |

## Configuration Notes

The NKF configuration in `config.json` should be updated if:
- The business changes location (different CRIB number)
- A new cash register/printer is added (different cash_register number)
- The source identifier changes (currently "A")

The sequential number (`last_order_id`) is automatically retrieved from the active software configuration (Odoo, TCPOS, etc.) and is incremented with each order.

## Backward Compatibility

The implementation includes fallback mechanisms:
- If the fiscal_utils module fails to import, a fallback function returns a default NKF
- The code gracefully handles both old (string) and new (dict) NKF config formats
- Logger warnings are issued if imports fail

## Running the Application

To run with Python 3.13 (required):
```bash
py -3.13 fiscal_printer_hub.py
```

## Next Steps

The application is ready for:
1. Full integration testing with real printer
2. Testing with live Odoo orders
3. Verification of NKF on printed receipts
