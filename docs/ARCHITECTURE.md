# BAB-Cloud PrintHub - Architecture Documentation

System architecture and design documentation for developers and AI agents.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Patterns](#architecture-patterns)
3. [Component Details](#component-details)
4. [Data Flow](#data-flow)
5. [Threading Model](#threading-model)
6. [Configuration System](#configuration-system)

---

## System Overview

BAB-Cloud PrintHub is a **modular fiscal printer bridge** that connects point-of-sale systems with fiscal printers. The system uses a **plugin architecture** with factory patterns to support multiple POS systems and printer brands.

### Key Design Principles

1. **Separation of Concerns** - POS integration, printer drivers, and UI are independent
2. **Config-Driven** - All behavior controlled via config.json
3. **Open-Closed Principle** - Open for extension (new POS/printers), closed for modification
4. **Single Responsibility** - Each module has one clear purpose
5. **Dependency Injection** - Components receive dependencies via constructors

---

## Architecture Patterns

### 1. Abstract Factory Pattern

**Purpose**: Create POS integrations and printer drivers dynamically based on config.

**Implementation:**

```python
# Software Factory (software/__init__.py)
def create_software(config, printer):
    software_name = config['software']['active']
    if software_name == 'odoo':
        return OdooIntegration(...)
    elif software_name == 'tcpos':
        return TCPOSIntegration(...)
    # ...

# Printer Factory (printers/__init__.py)
def create_printer(config):
    printer_name = config['printer']['active']
    if printer_name == 'cts310ii':
        return CTS310iiDriver(...)
    # ...
```

**Benefits:**
- Add new POS/printer without changing core code
- Config controls which implementation loads
- Easy to test with mocks

### 2. Strategy Pattern

**Purpose**: Abstract different POS integration strategies (polling vs file-watching).

**Implementation:**

```python
class BaseSoftware(ABC):
    @abstractmethod
    def start(self): pass

    @abstractmethod
    def parse_transaction(self, raw_data): pass

# Odoo Strategy: API Polling
class OdooIntegration(BaseSoftware):
    def start(self):
        # Start background polling thread

# TCPOS Strategy: File Monitoring
class TCPOSIntegration(BaseSoftware):
    def start(self):
        # Start file watchdog thread
```

### 3. Adapter Pattern

**Purpose**: Convert POS-specific transaction formats to standardized printer format.

**Implementation:**

```python
# Each software parses its format into standard format
class OdooIntegration:
    def parse_transaction(self, odoo_order):
        # Odoo format -> Standard format
        return {
            "articles": [...],
            "payments": [...],
            ...
        }

class TCPOSIntegration:
    def parse_transaction(self, xml_file):
        # TCPOS XML -> Standard format
        return {
            "articles": [...],
            "payments": [...],
            ...
        }
```

### 4. Singleton Pattern

**Purpose**: Ensure only one application instance runs.

**Implementation:**

```python
class SingleInstance:
    def __init__(self, app_name):
        self.mutex = win32event.CreateMutex(None, False, f"Global\\{app_name}")
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            return False  # Another instance running
```

---

## Component Details

### Entry Point: fiscal_printer_hub.py

**Responsibilities:**
1. Enforce single instance
2. Load configuration
3. Initialize printer via factory
4. Initialize POS software via factory
5. Start WordPress poller (optional)
6. Start system tray
7. Run main loop (process modal UI requests)

**Initialization Flow:**
```python
instance_lock = check_single_instance()
config = load_config()
printer = create_printer(config)
software = create_software(config, printer)
wordpress_thread = start_wordpress_poller(config, printer)
tray_thread = start_system_tray(config, printer, software, modal_queue)

while True:
    # Process modal requests
    if modal_queue.get() == 'open_fiscal_tools':
        open_fiscal_tools_modal(printer, config)
```

---

### Core Modules

#### config_manager.py

**Responsibilities:**
- Load config.json
- Validate configuration structure
- Get/set last_order_id
- Save config atomically

**Key Functions:**
```python
load_config() -> Dict
validate_config(config) -> bool
get_last_order_id(config, software_name) -> int
set_last_order_id(config, order_id, software_name, save=True) -> bool
```

#### system_tray.py

**Responsibilities:**
- Create system tray icon
- Build menu dynamically
- Handle menu actions
- Signal main thread for modal UI

**Key Class:**
```python
class SystemTray:
    def __init__(self, config, printer, software, modal_queue)
    def create_menu() -> Menu
    def run()  # Blocking
```

#### fiscal_ui.py

**Responsibilities:**
- Provide HTML-based fiscal tools UI
- JavaScript ↔ Python API bridge
- Call printer methods via interface

**Key Class:**
```python
class FiscalToolsAPI:
    def __init__(self, printer, config)
    def print_x_report()
    def print_z_report()
    def print_z_report_by_date(start, end)
    # ...

def open_fiscal_tools_modal(printer, config)
```

#### text_utils.py

**Responsibilities:**
- Word-aware text wrapping
- 48-character line limit
- Bottom-up text distribution

**Key Functions:**
```python
wrap_text_to_lines(text, max_chars=48, max_lines=3) -> List[str]
distribute_text_bottom_up(text, num_lines=3, max_chars=48) -> List[str]
```

---

### Software Integration Layer

#### Base Interface: base_software.py

```python
class BaseSoftware(ABC):
    @abstractmethod
    def start() -> bool

    @abstractmethod
    def stop() -> bool

    @abstractmethod
    def get_last_order_id() -> int

    @abstractmethod
    def set_last_order_id(order_id: int) -> bool

    @abstractmethod
    def get_status() -> Dict

    @abstractmethod
    def parse_transaction(raw_data) -> Optional[Dict]

    @abstractmethod
    def get_name() -> str
```

#### Odoo Implementation

**Files:**
- `odoo_integration.py` - Main wrapper class
- `rpc_client.py` - XML-RPC polling logic
- `odoo_parser.py` - Order parsing
- `credentials_handler.py` - Credential encryption

**Architecture:**
```
OdooIntegration
  └─> Background Thread (polling loop)
       ├─> Authenticate with Odoo
       ├─> Fetch orders (last 24 hours)
       ├─> Filter new orders (ID > last_order_id)
       ├─> Parse each order (odoo_parser)
       └─> Print document (printer.print_document)
```

#### TCPOS Implementation

**Files:**
- `tcpos_integration.py` - Main wrapper class
- `tcpos_parser.py` - XML parsing and file watchdog

**Architecture:**
```
TCPOSIntegration
  └─> Background Thread (watchdog loop)
       ├─> Scan transactions_folder
       ├─> Find .xml files without markers
       ├─> Parse XML (tcpos_parser)
       ├─> Print document (printer.print_document)
       └─> Create .processed marker
```

---

### Printer Driver Layer

#### Base Interface: base_printer.py

```python
class BasePrinter(ABC):
    @abstractmethod
    def connect() -> bool

    @abstractmethod
    def disconnect() -> bool

    @abstractmethod
    def print_document(items, payments, **kwargs) -> Dict

    @abstractmethod
    def print_x_report() -> Dict

    @abstractmethod
    def print_z_report(close_fiscal_day=True) -> Dict

    @abstractmethod
    def print_z_report_by_date(start, end) -> Dict

    @abstractmethod
    def print_z_report_by_number(number) -> Dict

    @abstractmethod
    def print_z_report_by_number_range(start, end) -> Dict

    @abstractmethod
    def reprint_document(doc_number) -> Dict

    @abstractmethod
    def print_no_sale() -> Dict

    @abstractmethod
    def get_status() -> Dict

    @abstractmethod
    def get_name() -> str
```

#### CTS310ii Implementation

**Files:**
- `cts310ii_driver.py` - Main driver class (59 KB)
- `protocol.py` - Protocol constants
- `__init__.py` - Package exports

**Protocol Architecture:**
```
CTS310iiDriver
  ├─> connect() - Auto-detect COM port
  ├─> print_document()
  │    ├─> _cancel_document() - Clear any open doc
  │    ├─> _prepare_document() - Open new doc
  │    ├─> _add_item_to_document() - For each item
  │    ├─> _discount_surcharge_service() - Discounts/charges
  │    ├─> _document_sub_or_total() - Calculate total
  │    ├─> _payment() - For each payment
  │    ├─> _add_comment() - Footer comment
  │    └─> _close_document() - Finalize
  └─> Serial Communication
       ├─> _send_to_serial(hex_cmd)
       ├─> _is_success_response(data)
       └─> Protocol: STX + CMD + FS + PARAMS + ETX
```

**MHI Protocol Format:**
```
STX + CommandCode + [FS + Param1 + FS + Param2 + ...] + ETX

Example:
02 40 1C 31 1C 03  = Prepare document type 1
└─ └─ └─ └─ └─
STX 40 FS  1 ETX
   CMD   P1
```

---

## Data Flow

### Odoo → Printer Flow

```
┌─────────────────┐
│   Odoo Server   │
│   (XML-RPC)     │
└────────┬────────┘
         │ Polls every 10s
         ↓
┌─────────────────────────────┐
│  OdooIntegration            │
│  (Background Thread)        │
│  - Fetch orders             │
│  - Filter new orders        │
│  - Parse each order         │
└────────┬────────────────────┘
         │ Standard format
         ↓
┌─────────────────────────────┐
│  CTS310iiDriver             │
│  - Format MHI commands      │
│  - Send to serial port      │
│  - Validate responses       │
└────────┬────────────────────┘
         │ Serial/USB
         ↓
┌─────────────────┐
│ Fiscal Printer  │
│  (Star/CTS)     │
└─────────────────┘
```

### TCPOS → Printer Flow

```
┌─────────────────┐
│  TCPOS System   │
│ (Writes XML)    │
└────────┬────────┘
         │ Creates XML files
         ↓
┌─────────────────────────────┐
│  File System                │
│  D:\TCpos\...\Transactions\ │
│  - order_001.xml            │
│  - order_002.xml            │
└────────┬────────────────────┘
         │ Scans every 1s
         ↓
┌─────────────────────────────┐
│  TCPOSIntegration           │
│  (Background Thread)        │
│  - Detect new XML           │
│  - Parse transaction        │
│  - Create .processed marker │
└────────┬────────────────────┘
         │ Standard format
         ↓
┌─────────────────────────────┐
│  CTS310iiDriver             │
│  - Format MHI commands      │
│  - Send to serial port      │
└────────┬────────────────────┘
         │ Serial/USB
         ↓
┌─────────────────┐
│ Fiscal Printer  │
└─────────────────┘
```

### User → Fiscal Tools Flow

```
┌─────────────────┐
│      User       │
│ (System Tray)   │
└────────┬────────┘
         │ Right-click menu
         ↓
┌─────────────────────────────┐
│  SystemTray                 │
│  - Fiscal Tools             │
│  - Print X-Report           │
│  - Print Z-Report           │
└────────┬────────────────────┘
         │ Signals modal_queue
         ↓
┌─────────────────────────────┐
│  Main Thread                │
│  - Listens to queue         │
│  - Opens pywebview modal    │
└────────┬────────────────────┘
         │ Creates webview
         ↓
┌─────────────────────────────┐
│  FiscalToolsAPI             │
│  (Python ↔ JavaScript)      │
│  - HTML UI with Tailwind    │
│  - JavaScript calls Python  │
└────────┬────────────────────┘
         │ Calls printer methods
         ↓
┌─────────────────────────────┐
│  CTS310iiDriver             │
│  - print_x_report()         │
│  - print_z_report()         │
│  - print_z_report_by_date() │
└────────┬────────────────────┘
         │ Serial/USB
         ↓
┌─────────────────┐
│ Fiscal Printer  │
└─────────────────┘
```

---

## Threading Model

### Thread Architecture

```
Main Thread (fiscal_printer_hub.py)
  │
  ├─> SystemTray Thread (daemon)
  │    └─> pystray.Icon.run() - Blocking
  │
  ├─> Software Integration Thread (daemon)
  │    └─> Odoo: Polling loop
  │    └─> TCPOS: File watchdog loop
  │
  ├─> WordPress Poller Thread (daemon, optional)
  │    └─> HTTP polling loop
  │
  └─> Main Loop
       ├─> Listen to modal_queue
       ├─> Open pywebview modal (blocks until closed)
       └─> Sleep 0.1s
```

### Thread Communication

**Modal Queue:**
```python
modal_queue = queue.Queue()

# SystemTray signals main thread:
modal_queue.put('open_fiscal_tools')

# Main thread processes:
if modal_queue.get() == 'open_fiscal_tools':
    open_fiscal_tools_modal(printer, config)
```

**Thread Safety:**
- All threads are daemon threads (exit when main exits)
- Queue-based communication (thread-safe)
- No shared mutable state
- Each integration has its own stop mechanism

---

## Component Details

### Layer 1: Entry Point

**File**: `fiscal_printer_hub.py`

**Initialization Steps:**
1. Enforce Python 3.13
2. Single instance check (Windows mutex)
3. Load and validate config
4. Create printer instance (factory)
5. Create software instance (factory)
6. Start WordPress poller (optional)
7. Start system tray (background thread)
8. Enter main loop (modal processing)

**Shutdown Steps:**
1. Stop software integration
2. Disconnect printer
3. Release instance lock
4. Exit

---

### Layer 2: Core Infrastructure

#### config_manager.py

**Purpose**: Centralized configuration management

**Design:**
- Thread-safe config loading
- Atomic config saves (write to .tmp, then replace)
- Validation before save
- Per-software last_order_id tracking

**API:**
```python
load_config() -> Dict
save_config(config) -> bool
validate_config(config) -> bool
get_software_config(config, name) -> Dict
get_printer_config(config, name) -> Dict
get_last_order_id(config, software) -> int
set_last_order_id(config, order_id, software) -> bool
```

#### system_tray.py

**Purpose**: System tray icon and menu management

**Design:**
- Uses pystray library
- Menu items call printer/software methods directly
- Signals main thread for modal UI (requires main thread on Windows)
- Graceful quit with resource cleanup

**Menu Structure:**
```
├─ Fiscal Tools
├─ ───────────────
├─ Print X-Report
├─ Print Z-Report
├─ NO SALE (Open Drawer)
├─ ───────────────
└─ Quit BAB Cloud
```

#### fiscal_ui.py

**Purpose**: Webview-based fiscal tools interface

**Design:**
- Single HTML page with Tailwind CSS
- JavaScript calls Python methods via pywebview.api
- Python methods call printer driver
- Runs in main thread (Windows requirement)

**Tech Stack:**
- pywebview (Python)
- HTML5 + Tailwind CSS (Frontend)
- JavaScript API bridge

---

### Layer 3: Software Integrations

#### base_software.py

**Purpose**: Define contract for all POS integrations

**Required Methods:**
- `start()` - Start integration (non-blocking)
- `stop()` - Stop gracefully
- `get_last_order_id()` - Tracking
- `set_last_order_id()` - Persistence
- `get_status()` - Monitoring
- `parse_transaction()` - Format conversion
- `get_name()` - Identification

#### Odoo Integration

**Threading:**
- Background polling thread
- Polls every N seconds (configurable)
- Graceful stop via flag

**State:**
- Last order ID (in config)
- Running flag
- Error log (last 10 errors)

**Dependencies:**
- xmlrpc.client (Python standard library)
- cryptography.fernet (credential encryption)

#### TCPOS Integration

**Threading:**
- Background watchdog thread
- Scans folder every 1 second
- Graceful stop via threading.Event

**State:**
- Last file processed
- Running flag
- Error log

**File Processing:**
- Preserve original XML (TCPOS needs for refunds)
- Create `.processed` marker on success
- Create `.skipped` marker on parse failure

---

### Layer 4: Printer Drivers

#### base_printer.py

**Purpose**: Define contract for all printer drivers

**Required Methods:**
- Connection: `connect()`, `disconnect()`, `get_status()`
- Receipt: `print_document(items, payments, ...)`
- Reports: `print_x_report()`, `print_z_report()`, variants
- Utilities: `reprint_document()`, `print_no_sale()`

#### CTS310ii Driver

**Protocol**: MHI Fiscal Protocol (proprietary hex-based)

**Components:**
- `protocol.py` - Constants (STX, ETX, ACK, NAK, FS, response codes)
- `cts310ii_driver.py` - Main driver class

**State Machine:**
```
0: Standby
1: Start of sale
2: Sale (adding items)
3: Subtotal
4: Payment
5: End of sale
6: Non-fiscal
```

**Command Flow:**
```
1. Cancel any open document
2. Prepare document (type 1-4)
3. Add items (one command per item)
4. Apply discounts/surcharges
5. Calculate subtotal
6. Process payments (one command per payment)
7. Add tips
8. Add comments
9. Close document
```

**Serial Communication:**
- Baud rate: 9600
- Timeout: 5 seconds
- Auto-detect: Scans all COM ports
- Response validation: Expects ACK (0x06)

---

## Configuration System

### Configuration Schema

```json
{
  "software": {
    "active": "odoo",
    "odoo": { /* software-specific config */ },
    "tcpos": { /* software-specific config */ }
  },
  "printer": {
    "active": "star",
    "star": { /* printer-specific config */ }
  },
  "client": {
    "NKF": "fiscal_device_id"
  },
  "miscellaneous": {
    "default_client_name": "...",
    "default_client_crib": "..."
  },
  "polling": {
    "printer_retry_interval_seconds": 5,
    "software_retry_interval_seconds": 10
  },
  "wordpress": { /* optional */ },
  "fiscal_tools": { /* Z report settings */ },
  "system": { /* app settings */ }
}
```

### Configuration Loading Locations

**Development (script mode):**
- Config: `bridge/config.json`
- Base dir: `bridge/`
- Logs: `bridge/log.log`

**Production (frozen/PyInstaller):**
- Config: `{exe_dir}/config.json`
- Base dir: `{exe_dir}/`
- Logs: `{exe_dir}/log.log`

**Detection:**
```python
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
```

---

## Standardized Transaction Format

All POS integrations must convert to this format:

```python
{
    "articles": [
        {
            "void": False,
            "vat_percent": "9.0",
            "discount_percent": "0",
            "surcharge_amount": "0",
            "item_price": "10.50",
            "item_quantity": "2",
            "item_unit": "Units",
            "item_code": "PROD001",
            "item_description": "Product Name",
            "customer_note": "",
            "item_notes": []
        }
    ],
    "payments": [
        {
            "method": "Cash",
            "amount": "21.00"
        }
    ],
    "service_charge_percent": "10.0",
    "tips": [{"amount": "2.00"}],
    "order_id": "12345",
    "receipt_number": "POS-001-00123",
    "pos_id": 1,
    "pos_name": "Main Register",
    "order_note": "",
    "customer_name": None,
    "customer_crib": None
}
```

**Validation Rules:**
- At least one article required
- At least one payment required
- Numeric strings must be parseable as floats
- VAT percent must be valid for printer (6.0, 7.0, 9.0 for CTS310ii)

---

## Error Handling Strategy

### Principles

1. **Fail Gracefully** - Log error, continue operation
2. **User Notification** - Critical errors show in UI
3. **Retry Logic** - Network errors retry automatically
4. **Detailed Logging** - All errors logged with context

### Error Categories

**Critical (Stop Application):**
- Config file missing/invalid
- Python version mismatch
- Duplicate instance running

**High (Log and Notify):**
- Printer connection failed
- POS authentication failed

**Medium (Log and Retry):**
- Network timeout
- Printer timeout
- Malformed transaction

**Low (Log Only):**
- WordPress poller connection error
- Non-critical validation warnings

---

## Security Considerations

### Credentials

**Odoo:**
- Encrypted with Fernet (AES-128 CBC)
- Key hardcoded (acceptable for desktop app)
- Never logged or displayed

**Config:**
- Contains NKF (fiscal ID) - treat as sensitive
- File permissions: Read/write for application only

### Network

**Odoo:**
- HTTPS recommended
- Certificate validation (production)
- Firewall: Allow outbound to Odoo server

**WordPress:**
- Temporary solution (will be replaced)
- No authentication in Phase 1 (intentional)
- Use HTTPS in production

---

## Performance Characteristics

### Startup Time

- **Cold start**: 3-5 seconds
- **Printer detection**: 1-3 seconds (depends on COM ports)
- **Software startup**: <1 second

### Runtime Performance

**Odoo Polling:**
- Poll interval: 10 seconds (configurable)
- CPU usage: <1% (idle between polls)
- Memory: ~50 MB

**TCPOS Watchdog:**
- Scan interval: 1 second
- CPU usage: <1% (idle between scans)
- Memory: ~45 MB

**Printer Operations:**
- Receipt print: 2-5 seconds
- X-Report: 3-8 seconds
- Z-Report: 5-15 seconds (varies by daily volume)

---

## Extensibility

### Adding New POS System

**Checklist:**
1. Create folder: `software/newsystem/`
2. Implement `BaseSoftware` class
3. Implement required methods (start, stop, parse, etc.)
4. Add config section to schema
5. Update `software/__init__.py` factory
6. Add documentation to `docs/COMPATIBILITY.md`
7. Test end-to-end

**Estimated Effort:** 8-16 hours (depends on POS complexity)

### Adding New Printer

**Checklist:**
1. Create folder: `printers/newprinter/`
2. Implement `BasePrinter` class
3. Implement required methods (connect, print_document, reports, etc.)
4. Create protocol constants module (if needed)
5. Add config section to schema
6. Update `printers/__init__.py` factory
7. Add documentation to `docs/COMPATIBILITY.md`
8. Test with real hardware

**Estimated Effort:** 16-40 hours (depends on protocol complexity)

---

## Future Enhancements

### Short Term (Q1-Q2 2026)
- Log viewer window
- Simphony integration
- Epson driver
- Enhanced WordPress portal

### Medium Term (Q3-Q4 2026)
- QuickBooks POS integration
- Auto-update mechanism
- Remote configuration
- Cloud transaction backup

### Long Term (2027+)
- Multi-printer routing
- Mobile monitoring app
- Analytics dashboard
- API for third-party integrations

---

**For more details, see:**
- [SETUP.md](SETUP.md) - Installation and configuration
- [COMPATIBILITY.md](COMPATIBILITY.md) - Compatibility matrix
- [API.md](API.md) - Interface specifications
- [MIGRATION.md](MIGRATION.md) - Migration guides

---

**Last Updated**: 2025-12-18
**Architecture Version**: 2.0
