# BAB-Cloud PrintHub - API Reference

Interface specifications for extending BAB-Cloud with new POS systems and printer drivers.

---

## Table of Contents

1. [BaseSoftware Interface](#basesoftware-interface)
2. [BasePrinter Interface](#baseprinter-interface)
3. [Standardized Transaction Format](#standardized-transaction-format)
4. [Configuration Schema](#configuration-schema)
5. [Adding New Software Tutorial](#adding-new-software-tutorial)
6. [Adding New Printer Tutorial](#adding-new-printer-tutorial)

---

## BaseSoftware Interface

**File**: `bridge/software/base_software.py`

### Class Definition

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseSoftware(ABC):
    """
    Abstract base class for POS software integrations.
    """

    def __init__(self, config: Dict[str, Any], printer):
        """
        Args:
            config: Software-specific config dict
            printer: Active printer instance (BasePrinter)
        """
        self.config = config
        self.printer = printer
        self.running = False
        self.thread = None
```

### Required Methods

#### start() -> bool

Start the integration (polling, watchdog, etc.).

**Returns**: `True` if started successfully

**Implementation Guidelines:**
- Should be non-blocking (start background thread)
- Set `self.running = True`
- Return `False` if startup fails

**Example:**
```python
def start(self) -> bool:
    try:
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        return True
    except Exception as e:
        logger.error(f"Failed to start: {e}")
        return False
```

---

#### stop() -> bool

Stop the integration gracefully.

**Returns**: `True` if stopped successfully

**Implementation Guidelines:**
- Set flag to stop background thread
- Wait for thread to finish (with timeout)
- Set `self.running = False`

**Example:**
```python
def stop(self) -> bool:
    self.running = False
    if self.thread:
        self.thread.join(timeout=5.0)
    return True
```

---

#### get_last_order_id() -> int

Get the last processed order ID.

**Returns**: Last order ID (0 if none)

**Implementation Guidelines:**
- Read from config or internal state
- Return 0 if not applicable (e.g., file-based systems)

**Example:**
```python
def get_last_order_id(self) -> int:
    return self.config.get('last_order_id', 0)
```

---

#### set_last_order_id(order_id: int) -> bool

Update the last processed order ID.

**Args**: `order_id` - New last order ID

**Returns**: `True` if saved successfully

**Implementation Guidelines:**
- Save to config via config_manager
- Update internal state
- Return `False` if save fails

**Example:**
```python
def set_last_order_id(self, order_id: int) -> bool:
    from core.config_manager import set_last_order_id
    return set_last_order_id(self.full_config, order_id, self.get_name())
```

---

#### get_status() -> Dict[str, Any]

Get current status of the integration.

**Returns**: Status dict with keys:
- `running`: bool
- `last_poll_time`: datetime or None
- `last_order_id`: int
- `errors`: List[str] (recent errors)
- Additional software-specific fields

**Example:**
```python
def get_status(self) -> Dict[str, Any]:
    return {
        "running": self.running,
        "last_poll_time": self.last_poll_time,
        "last_order_id": self.get_last_order_id(),
        "errors": self.error_log[-10:],  # Last 10 errors
        "software": self.get_name()
    }
```

---

#### parse_transaction(raw_data: Any) -> Optional[Dict[str, Any]]

Parse raw transaction data into standardized format.

**Args**: `raw_data` - Raw transaction (format varies by software)

**Returns**: Standardized transaction dict or `None` if parse fails

**Implementation Guidelines:**
- Convert software-specific format to standard format
- Validate required fields
- Return `None` on parse failure (log error)

**Example:**
```python
def parse_transaction(self, raw_data) -> Optional[Dict]:
    try:
        # Parse software-specific format
        # Convert to standard format
        return {
            "articles": [...],
            "payments": [...],
            # ... see Standardized Transaction Format
        }
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        return None
```

---

#### get_name() -> str

Get the software integration name.

**Returns**: Software name (lowercase, no spaces)

**Example:**
```python
def get_name(self) -> str:
    return "odoo"  # or "tcpos", "simphony", "quickbooks"
```

---

### Optional Helper Method

#### get_transaction_folder() -> str

Get the transaction storage folder name.

**Returns**: Folder name (e.g., "odoo-transactions")

**Implementation** (inherited from BaseSoftware):
```python
def get_transaction_folder(self) -> str:
    return f"{self.get_name()}-transactions"
```

---

## BasePrinter Interface

**File**: `bridge/printers/base_printer.py`

### Class Definition

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BasePrinter(ABC):
    """
    Abstract base class for fiscal printer drivers.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: Printer-specific config dict
        """
        self.config = config
        self.com_port = None
        self.connected = False
```

### Required Methods

#### connect() -> bool

Detect and connect to the printer.

**Returns**: `True` if connected successfully

**Implementation Guidelines:**
- Auto-detect printer on COM ports (or use config.com_port)
- Set `self.com_port`
- Set `self.connected = True` on success

**Example:**
```python
def connect(self) -> bool:
    # Auto-detect or use configured port
    port = self.config.get('com_port') or self._auto_detect()
    if port:
        self.com_port = port
        self.connected = True
        return True
    return False
```

---

#### disconnect() -> bool

Disconnect from the printer.

**Returns**: `True` if disconnected successfully

---

#### print_document(...) -> Dict[str, Any]

Print a fiscal receipt document.

**Full Signature:**
```python
def print_document(
    self,
    items: List[Dict],
    payments: List[Dict],
    service_charge: Optional[Dict] = None,
    tips: Optional[List[Dict]] = None,
    discount: Optional[Dict] = None,
    surcharge: Optional[Dict] = None,
    general_comment: str = "",
    is_refund: bool = False,
    receipt_number: Optional[str] = None,
    pos_name: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_crib: Optional[str] = None
) -> Dict[str, Any]:
```

**Args:**
- `items`: List of item dicts (see Transaction Format)
- `payments`: List of payment dicts
- `service_charge`: Service charge dict (optional)
- `tips`: List of tip dicts (optional)
- `discount`: Transaction discount (optional)
- `surcharge`: Transaction surcharge (optional)
- `general_comment`: Footer comment (optional)
- `is_refund`: True if credit note (optional)
- `receipt_number`: Display number (optional)
- `pos_name`: POS terminal name (optional)
- `customer_name`: Customer name (optional)
- `customer_crib`: Customer tax ID (optional)

**Returns:**
```python
{
    "success": True,  # or False
    "error": None,    # or error message
    "document_number": "00123"  # Fiscal document number
}
```

---

#### print_x_report() -> Dict[str, Any]

Print X report (non-fiscal daily sales summary).

**Returns:**
```python
{
    "success": True,
    "error": None
}
```

---

#### print_z_report(close_fiscal_day: bool = True) -> Dict[str, Any]

Print Z report (fiscal day closing).

**Args:**
- `close_fiscal_day`: If True, closes fiscal day (can only be done once/day)

**Returns:**
```python
{
    "success": True,
    "error": None
}
```

---

#### print_z_report_by_date(start_date, end_date) -> Dict[str, Any]

Print Z reports for a date range.

**Args:**
- `start_date`: Start date (datetime.date object)
- `end_date`: End date (datetime.date object)

**Returns:**
```python
{
    "success": True,
    "error": None,
    "message": "5 Z reports printed"
}
```

---

#### Other Report Methods

```python
print_z_report_by_number(report_number: int) -> Dict[str, Any]
print_z_report_by_number_range(start: int, end: int) -> Dict[str, Any]
reprint_document(document_number: str) -> Dict[str, Any]
print_no_sale() -> Dict[str, Any]
```

All return same format: `{"success": bool, "error": str}`

---

#### get_status() -> Dict[str, Any]

Get printer status.

**Returns:**
```python
{
    "connected": True,
    "com_port": "COM3",
    "state": "Standby",  # Printer state machine
    "paper_low": False,
    "cover_open": False,
    "error": None
}
```

---

#### get_name() -> str

Get printer driver name.

**Returns**: Printer name (e.g., "cts310ii", "star", "citizen")

---

## Standardized Transaction Format

### Complete Specification

```python
{
    # ========================================
    # REQUIRED FIELDS
    # ========================================

    "articles": [  # At least one required
        {
            "void": bool,                    # Is item voided?
            "vat_percent": str,              # "6.0", "7.0", "9.0"
            "discount_percent": str,          # "0", "10.5", "15.0"
            "surcharge_amount": str,          # "0", "2.50"
            "item_price": str,               # "10.50"
            "item_quantity": str,            # "1", "2.5"
            "item_unit": str,                # "Units", "kg", "L"
            "item_code": str | int,          # "PROD001" or 123
            "item_description": str,         # Max 144 chars
            "customer_note": str,            # Optional note
            "item_notes": List[str],         # Additional notes
        }
    ],

    "payments": [  # At least one required
        {
            "method": str,                   # "Cash", "Credit Card"
            "amount": str,                   # "21.00"
        }
    ],

    # ========================================
    # OPTIONAL FIELDS
    # ========================================

    "service_charge_percent": str,           # "0", "10.0"
    "tips": List[Dict[str, str]],           # [{"amount": "2.00"}]
    "order_id": str,                         # "12345"
    "receipt_number": str,                   # "POS-001-00123"
    "pos_id": int | None,                    # 1
    "pos_name": str | None,                  # "Main Register"
    "order_note": str,                       # Order comment
    "customer_name": str | None,             # "John Doe"
    "customer_crib": str | None,             # "1234567890"
}
```

### Field Specifications

#### articles[].void
**Type**: `bool`
**Purpose**: Mark item as voided/refunded
**Values**: `True` = void, `False` = normal

#### articles[].vat_percent
**Type**: `str`
**Purpose**: Tax rate percentage
**Values**: `"6.0"`, `"7.0"`, `"9.0"` (CTS310ii)
**Format**: String with one decimal place

#### articles[].discount_percent
**Type**: `str`
**Purpose**: Item-level discount percentage
**Values**: `"0"` (no discount) to `"100.0"` (100% off)
**Format**: String with decimals

#### articles[].item_price
**Type**: `str`
**Purpose**: Unit price (before tax)
**Format**: Decimal string (e.g., `"10.50"`)

#### articles[].item_quantity
**Type**: `str`
**Purpose**: Quantity sold
**Format**: Decimal string (e.g., `"1"`, `"2.5"`)

#### payments[].method
**Type**: `str`
**Purpose**: Payment method name
**Values**: Must match payment_methods in config
**Examples**: `"Cash"`, `"Credit Card"`, `"Cheque"`

---

## Configuration Schema

### Full Schema

```json
{
  "software": {
    "active": "odoo",  // Required
    "odoo": {
      "enabled": true,
      "credentials_file": "odoo_credentials_encrypted.json",
      "polling_interval_seconds": 10,
      "last_order_id": 0,
      "payment_methods": {
        "Cash": "00",
        "Credit Card": "02"
      }
    },
    "tcpos": {
      "enabled": false,
      "transactions_folder": "C:\\path\\to\\folder",
      "last_order_id": 0
    }
  },

  "printer": {
    "active": "cts310ii",  // Required
    "cts310ii": {
      "enabled": true,
      "com_port": null,        // null = auto-detect
      "baud_rate": 9600,
      "timeout": 5
    }
  },

  "client": {
    "NKF": "1234567890123456789"  // Required
  },

  "miscellaneous": {
    "default_client_name": "Regular client",  // Required
    "default_client_crib": "1000000000"       // Required
  },

  "polling": {
    "printer_retry_interval_seconds": 5,
    "software_retry_interval_seconds": 10
  },

  "wordpress": {
    "enabled": false,
    "url": "https://portal.example.com",
    "poll_interval": 5,
    "trigger_endpoint": "/wp-content/zreport.flag",
    "complete_endpoint": "/zreport-complete.php"
  },

  "fiscal_tools": {
    "Z_report_from": "2025-01-01",
    "last_z_report_print_time": null
  },

  "system": {
    "single_instance": true,
    "log_level": "INFO",
    "log_file": "log.log"
  }
}
```

---

## Adding New Software Tutorial

### Step 1: Create Folder Structure

```batch
cd bridge\software
mkdir newsystem
cd newsystem
```

Create files:
- `__init__.py`
- `newsystem_integration.py`
- `README.md` (optional)

---

### Step 2: Implement BaseSoftware

**File**: `newsystem_integration.py`

```python
from typing import Dict, Any, Optional
import logging
from ..base_software import BaseSoftware

logger = logging.getLogger(__name__)


class NewSystemIntegration(BaseSoftware):
    """
    Integration for NewSystem POS.

    TODO: Describe integration approach (API, database, files)
    """

    def __init__(self, config: Dict, printer, full_config: Dict):
        super().__init__(config, printer)
        self.full_config = full_config
        # Add custom initialization

    def start(self) -> bool:
        """Start the integration."""
        try:
            # Start your polling/monitoring logic
            self.running = True
            return True
        except Exception as e:
            logger.error(f"Start failed: {e}")
            return False

    def stop(self) -> bool:
        """Stop the integration."""
        self.running = False
        return True

    def get_last_order_id(self) -> int:
        """Get last order ID."""
        return self.config.get('last_order_id', 0)

    def set_last_order_id(self, order_id: int) -> bool:
        """Save last order ID."""
        from core.config_manager import set_last_order_id
        return set_last_order_id(
            self.full_config,
            order_id,
            self.get_name(),
            save=True
        )

    def get_status(self) -> Dict[str, Any]:
        """Get status."""
        return {
            "running": self.running,
            "last_order_id": self.get_last_order_id()
        }

    def parse_transaction(self, raw_data) -> Optional[Dict]:
        """Parse transaction."""
        # Convert newsystem format to standard format
        try:
            return {
                "articles": [...],
                "payments": [...],
                # ... see Standardized Transaction Format
            }
        except Exception as e:
            logger.error(f"Parse failed: {e}")
            return None

    def get_name(self) -> str:
        """Get software name."""
        return "newsystem"
```

---

### Step 3: Export in __init__.py

**File**: `__init__.py`

```python
from .newsystem_integration import NewSystemIntegration

__all__ = ['NewSystemIntegration']
```

---

### Step 4: Update Factory

**File**: `bridge/software/__init__.py`

```python
def create_software(config, printer):
    software_name = config['software']['active']

    # ... existing code ...

    elif software_name == 'newsystem':
        from .newsystem.newsystem_integration import NewSystemIntegration
        return NewSystemIntegration(
            config['software']['newsystem'],
            printer,
            config
        )

    # ... rest of code ...
```

---

### Step 5: Add Config Section

**File**: `bridge/config.json`

```json
{
  "software": {
    "newsystem": {
      "enabled": false,
      "connection_string": "",
      "last_order_id": 0
      // Add newsystem-specific settings
    }
  }
}
```

---

### Step 6: Test

```python
# Test import
from bridge.software.newsystem import NewSystemIntegration

# Test instantiation
config = {...}
printer = create_printer(config)
integration = NewSystemIntegration(config, printer, full_config)

# Test methods
assert integration.get_name() == "newsystem"
assert integration.start() == True
status = integration.get_status()
assert status['running'] == True
```

---

## Adding New Printer Tutorial

### Step 1: Create Folder Structure

```batch
cd bridge\printers
mkdir newprinter
cd newprinter
```

Create files:
- `__init__.py`
- `newprinter_driver.py`
- `protocol.py` (if needed)
- `README.md` (optional)

---

### Step 2: Implement BasePrinter

**File**: `newprinter_driver.py`

```python
from typing import Dict, Any, List, Optional
import logging
from ..base_printer import BasePrinter

logger = logging.getLogger(__name__)


class NewPrinterDriver(BasePrinter):
    """
    Driver for NewPrinter fiscal printer.

    Protocol: [Describe protocol]
    """

    def __init__(self, config: Dict, full_config: Dict):
        super().__init__(config)
        self.full_config = full_config
        # Initialize protocol-specific settings

    def connect(self) -> bool:
        """Connect to printer."""
        try:
            # Auto-detect or use config.com_port
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Connect failed: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect."""
        self.connected = False
        return True

    def print_document(self, items, payments, **kwargs) -> Dict:
        """Print receipt."""
        try:
            # Build and send print commands
            return {"success": True, "document_number": "00123"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def print_x_report(self) -> Dict:
        """Print X report."""
        try:
            # Send X report command
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def print_z_report(self, close_fiscal_day=True) -> Dict:
        """Print Z report."""
        try:
            # Send Z report command
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Implement remaining methods...

    def get_status(self) -> Dict:
        """Get status."""
        return {
            "connected": self.connected,
            "com_port": self.com_port
        }

    def get_name(self) -> str:
        """Get printer name."""
        return "newprinter"
```

---

### Step 3: Update Factory

**File**: `bridge/printers/__init__.py`

```python
def create_printer(config):
    printer_name = config['printer']['active']

    # ... existing code ...

    elif printer_name == 'newprinter':
        from .newprinter.newprinter_driver import NewPrinterDriver
        return NewPrinterDriver(
            config['printer']['newprinter'],
            config
        )

    # ... rest of code ...
```

---

### Step 4: Add Config Section

```json
{
  "printer": {
    "newprinter": {
      "enabled": false,
      "com_port": null,
      "baud_rate": 9600,
      "timeout": 5
      // Add printer-specific settings
    }
  }
}
```

---

### Step 5: Test

```python
# Test import
from bridge.printers.newprinter import NewPrinterDriver

# Test connection
driver = NewPrinterDriver(config, full_config)
assert driver.connect() == True
assert driver.get_name() == "newprinter"

# Test print
result = driver.print_document(items, payments)
assert result['success'] == True
```

---

## Error Handling Best Practices

### Return Format

All methods that can fail should return:

```python
{
    "success": bool,      # True if operation succeeded
    "error": str | None,  # Error message if failed, None if success
    "data": Any           # Optional: Additional return data
}
```

### Logging

```python
# Info: Normal operations
logger.info("Connected to printer on COM3")

# Warning: Recoverable issues
logger.warning("Printer paper low")

# Error: Operation failures
logger.error(f"Failed to print document: {e}")

# Debug: Detailed diagnostic info
logger.debug(f"Sent command: {hex_cmd}")
```

### Exception Handling

```python
def risky_operation(self):
    try:
        # Attempt operation
        result = perform_operation()
        return {"success": True, "data": result}
    except SpecificException as e:
        logger.error(f"Specific error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {"success": False, "error": "Internal error"}
```

---

## Testing Guidelines

### Unit Tests

```python
import unittest
from bridge.software.newsystem import NewSystemIntegration

class TestNewSystemIntegration(unittest.TestCase):
    def setUp(self):
        self.config = {...}
        self.printer = MockPrinter()
        self.integration = NewSystemIntegration(...)

    def test_start(self):
        self.assertTrue(self.integration.start())

    def test_parse_transaction(self):
        raw_data = {...}
        result = self.integration.parse_transaction(raw_data)
        self.assertIsNotNone(result)
        self.assertIn('articles', result)
```

### Integration Tests

```python
def test_end_to_end():
    # Load config
    config = load_config()

    # Create instances
    printer = create_printer(config)
    software = create_software(config, printer)

    # Test workflow
    assert printer.connect()
    assert software.start()

    # Simulate transaction
    # ...

    # Cleanup
    software.stop()
    printer.disconnect()
```

---

## Version History

### v2.0.0 (2025-12-18)
- Initial modular architecture
- Odoo and TCPOS support
- CTS310ii, Star, Citizen drivers
- Factory pattern implementation

### Future Versions
- v2.1.0 - Simphony support (Q2 2026)
- v2.2.0 - Epson driver (Q2 2026)
- v2.3.0 - QuickBooks POS (Q3 2026)

---

**For implementation examples, see:**
- `bridge/software/odoo/odoo_integration.py`
- `bridge/software/tcpos/tcpos_integration.py`
- `bridge/printers/cts310ii/cts310ii_driver.py`

---

**Last Updated**: 2025-12-18
**API Version**: 2.0
