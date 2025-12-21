# BAB-Cloud PrintHub - Setup Guide

Complete setup instructions for developers and system administrators.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Methods](#installation-methods)
3. [Configuration](#configuration)
4. [First Run](#first-run)
5. [Troubleshooting](#troubleshooting)
6. [For AI Agents](#for-ai-agents)

---

## Prerequisites

### Required Software

#### Python 3.13 (EXACTLY)
- **Version**: Python 3.13.x (not 3.12 or 3.14+)
- **Reason**: pythonnet compatibility requirement
- **Download**: https://www.python.org/downloads/release/python-3130/

**Verification:**
```batch
py -3.13 --version
# Should output: Python 3.13.x
```

#### Git (Optional)
- For cloning from GitHub
- Download: https://git-scm.com/downloads

### Hardware Requirements

- **Fiscal Printer**: CTS310ii, Star, or Citizen with MHI protocol
- **Connection**: USB or Serial (COM port)
- **COM Port**: Available serial port (will auto-detect)

### Access Requirements

**For Odoo:**
- Odoo server URL
- Database name
- Username and password with POS access
- POS config name

**For TCPOS:**
- File system access to TCPOS transactions folder
- Read/write permissions on the folder

---

## Installation Methods

### Method 1: Pre-Built Executable (Recommended for Production)

#### Step 1: Download
```
Download BAB_Cloud_v2026.zip from GitHub releases
```

#### Step 2: Extract
```
Extract to: C:\Program Files\BAB Cloud\
```

#### Step 3: Configure
```
Edit: C:\Program Files\BAB Cloud\config.json
```

#### Step 4: Run
```
Double-click: BAB_Cloud.exe
```

---

### Method 2: Build from Source (Recommended for Development)

#### Step 1: Clone Repository
```batch
git clone https://github.com/solutech/bab-cloud.git
cd bab-cloud
```

Or download ZIP and extract:
```
https://github.com/solutech/bab-cloud/archive/main.zip
```

#### Step 2: Verify Python 3.13
```batch
py -3.13 --version
```

If not installed:
1. Download Python 3.13 installer
2. Run installer
3. ✅ Check "Add Python 3.13 to PATH"
4. Complete installation
5. Verify: `py -3.13 --version`

#### Step 3: Run Setup Script
```batch
setup.bat
```

This will:
- Install all Python dependencies
- Create transaction folders
- Verify environment

**Manual Setup (if script fails):**
```batch
py -3.13 -m pip install --upgrade pip
py -3.13 -m pip install -r requirements.txt
```

#### Step 4: Configure (see Configuration section below)

#### Step 5: Test Run
```batch
run.bat
```

Check output for errors. Press Ctrl+C to stop.

#### Step 6: Build Executable (optional)
```batch
build.bat
```

Output: `dist\BAB_Cloud\BAB_Cloud.exe`

---

## Configuration

### Configuration File Location

**Pre-built:** `BAB_Cloud\config.json`
**Source:** `bridge\config.json`

### Basic Configuration

#### 1. Select Active Software

```json
{
  "software": {
    "active": "odoo"  // Options: "odoo", "tcpos", "simphony", "quickbooks"
  }
}
```

#### 2. Select Active Printer

```json
{
  "printer": {
    "active": "star"  // Options: "cts310ii", "star", "citizen", "epson"
  }
}
```

---

### Odoo Configuration

#### Step 1: Configure Software Section
```json
{
  "software": {
    "active": "odoo",
    "odoo": {
      "enabled": true,
      "credentials_file": "odoo_credentials_encrypted.json",
      "polling_interval_seconds": 10,
      "last_order_id": 0,
      "payment_methods": {
        "Cash": "00",
        "Credit Card": "02",
        "Debit Card": "03"
      }
    }
  }
}
```

#### Step 2: Create Encrypted Credentials

**From Source:**
```batch
cd tools
py -3.13 update_odoo_credentials.py
```

**From Executable:**
```batch
cd tools
python update_odoo_credentials.py
```

Enter when prompted:
- Odoo URL (e.g., `https://yourdomain.odoo.com`)
- Database name
- Username
- Password
- POS config name (exact match from Odoo)

This creates: `odoo_credentials_encrypted.json`

**Move to application folder:**
```batch
# From source:
copy tools\odoo_credentials_encrypted.json bridge\

# From executable:
copy tools\odoo_credentials_encrypted.json .
```

---

### TCPOS Configuration

#### Step 1: Configure Software Section
```json
{
  "software": {
    "active": "tcpos",
    "tcpos": {
      "enabled": true,
      "transactions_folder": "D:\\TCpos\\FrontEnd\\Transactions",
      "last_order_id": 0
    }
  }
}
```

#### Step 2: Verify Folder Access
```batch
# Check folder exists:
dir "D:\TCpos\FrontEnd\Transactions"

# Check you can write:
echo test > "D:\TCpos\FrontEnd\Transactions\test.txt"
del "D:\TCpos\FrontEnd\Transactions\test.txt"
```

#### Step 3: Test TCPOS Export
1. Complete a sale in TCPOS
2. Check if XML file appears in transactions folder
3. Verify XML format (should have `<SoftwareVersion>` tag)

---

### Printer Configuration

#### CTS310ii / Star / Citizen (MHI Protocol)

```json
{
  "printer": {
    "active": "star",
    "star": {
      "enabled": true,
      "com_port": null,        // null = auto-detect
      "baud_rate": 9600,
      "timeout": 5
    }
  }
}
```

**Manual COM Port** (if auto-detect fails):
```json
{
  "com_port": "COM3"  // Check Device Manager for correct port
}
```

**Find COM Port:**
1. Open Device Manager
2. Expand "Ports (COM & LPT)"
3. Look for printer device
4. Note COM port number

---

### Client Configuration

```json
{
  "client": {
    "NKF": "1234567890123456789"  // Your fiscal device number
  },
  "miscellaneous": {
    "default_client_name": "Walk-in Customer",
    "default_client_crib": "1000000000"
  }
}
```

**NKF**: Tax authority assigned fiscal device number

---

### WordPress Configuration (Optional)

```json
{
  "wordpress": {
    "enabled": false,  // Set to true to enable
    "url": "https://your-portal.com",
    "poll_interval": 5,
    "trigger_endpoint": "/wp-content/zreport.flag",
    "complete_endpoint": "/zreport-complete.php"
  }
}
```

**Note**: This is temporary. Will be replaced by Portal system in Q2 2026.

---

### System Configuration

```json
{
  "system": {
    "single_instance": true,  // Prevent duplicate processes
    "log_level": "INFO",      // DEBUG, INFO, WARNING, ERROR, CRITICAL
    "log_file": "log.log"
  }
}
```

---

## First Run

### Development Mode

```batch
run.bat
```

**Expected Output:**
```
========================================
BAB-Cloud PrintHub v2026 Starting...
========================================
[1/7] Enforcing single instance...
✓ Single instance lock acquired
[2/7] Loading configuration...
✓ Configuration loaded and validated
  Active software: odoo
  Active printer: star
[3/7] Initializing printer...
✓ Printer driver loaded: star
  Connecting to printer...
  ✓ Connected to star on COM3
[4/7] Initializing POS software integration...
✓ Software integration loaded: odoo
  Starting integration...
  ✓ odoo integration started
[5/7] Checking WordPress configuration...
  WordPress polling: disabled
[6/7] Starting system tray...
✓ System tray started
[7/7] Main loop ready
========================================
BAB-Cloud PrintHub is running
Check system tray for application icon
========================================
```

### Production Mode

```batch
BAB_Cloud.exe
```

**Check System Tray:**
- Look for BAB Cloud icon in system tray (bottom-right)
- Right-click for menu
- Check `log.log` for startup messages

---

## Troubleshooting

### Python 3.13 Not Found

**Error:**
```
ERROR: Python 3.13 is required
```

**Solution:**
1. Install Python 3.13 from python.org
2. During installation: ✅ Add Python to PATH
3. Restart command prompt
4. Verify: `py -3.13 --version`

---

### Printer Not Detected

**Error:**
```
✗ Could not connect to printer
```

**Solutions:**

1. **Check Connection**
   ```batch
   # Open Device Manager
   devmgmt.msc

   # Look under "Ports (COM & LPT)"
   # Verify printer is listed
   ```

2. **Manual COM Port**
   ```json
   {
     "printer": {
       "star": {
         "com_port": "COM3"  // Set manually
       }
     }
   }
   ```

3. **Check Baud Rate**
   ```json
   {
     "baud_rate": 9600  // Try 115200 if 9600 fails
   }
   ```

4. **Printer Power**
   - Ensure printer is powered on
   - Check USB cable is connected
   - Try different USB port

---

### Odoo Authentication Failed

**Error:**
```
Authentication failed! Please check your credentials.
```

**Solutions:**

1. **Verify Credentials**
   ```batch
   cd tools
   py -3.13 update_odoo_credentials.py
   # Re-enter credentials carefully
   ```

2. **Test Odoo Connection**
   ```python
   # Test script:
   import xmlrpc.client

   url = "https://yourdomain.odoo.com"
   db = "your_database"
   username = "your_username"
   password = "your_password"

   common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
   uid = common.authenticate(db, username, password, {})
   print(f"Authenticated: {uid}")
   ```

3. **Check Odoo Server**
   - Verify URL is accessible
   - Check firewall rules
   - Verify XML-RPC is enabled on Odoo

---

### TCPOS Files Not Processing

**Error:**
```
No XML files detected
```

**Solutions:**

1. **Verify Folder Path**
   ```batch
   dir "D:\TCpos\FrontEnd\Transactions"
   # Should show files
   ```

2. **Check TCPOS Version**
   - Must be TCPOS 8.0 or higher
   - Check XML file has: `<SoftwareVersion>8.0</SoftwareVersion>`

3. **Check Permissions**
   ```batch
   # Try creating a file:
   echo test > "D:\TCpos\FrontEnd\Transactions\test.txt"

   # If error: permission denied
   # Run as Administrator
   ```

4. **Check Marker Files**
   - Look for `.processed` or `.skipped` files
   - Delete to reprocess: `del *.processed`

---

### Single Instance Error

**Error:**
```
Another instance is already running!
```

**Solutions:**

1. **Close Existing Instance**
   - Right-click system tray icon → Quit
   - Or kill process: `taskkill /f /im BAB_Cloud.exe`

2. **Clean Shutdown**
   - Always use "Quit" from system tray
   - Don't kill process unless necessary

3. **Orphaned Mutex**
   ```batch
   # Restart Windows
   # Or use Process Explorer to release mutex
   ```

---

### Dependencies Installation Failed

**Error:**
```
Failed to install dependencies
```

**Solutions:**

1. **Update pip**
   ```batch
   py -3.13 -m pip install --upgrade pip
   ```

2. **Install One-by-One**
   ```batch
   py -3.13 -m pip install pyserial
   py -3.13 -m pip install xmltodict
   py -3.13 -m pip install pywebview
   py -3.13 -m pip install pystray
   py -3.13 -m pip install Pillow
   py -3.13 -m pip install pythonnet
   py -3.13 -m pip install pywin32
   py -3.13 -m pip install cryptography
   py -3.13 -m pip install requests
   ```

3. **Check Internet Connection**
   ```batch
   ping pypi.org
   ```

4. **Use Offline Installation**
   - Download wheels from pypi.org
   - Install with: `py -3.13 -m pip install filename.whl`

---

## For AI Agents (Claude Code, etc.)

### Project Structure for AI
```
Main entry: bridge/fiscal_printer_hub.py
Config: bridge/config.json
Interfaces:
  - software/base_software.py (POS integration interface)
  - printers/base_printer.py (Printer driver interface)
```

### Adding New Features

**New POS System:**
1. Create: `bridge/software/newsystem/newsystem_integration.py`
2. Implement: `BaseSoftware` interface
3. Update: `bridge/software/__init__.py` factory
4. Add config section to `config.json`

**New Printer:**
1. Create: `bridge/printers/newprinter/newprinter_driver.py`
2. Implement: `BasePrinter` interface
3. Update: `bridge/printers/__init__.py` factory
4. Add config section to `config.json`

### Key Files to Understand
1. `fiscal_printer_hub.py` - Main entry point (7-step initialization)
2. `config_manager.py` - Configuration handling
3. `base_software.py` - POS integration contract
4. `base_printer.py` - Printer driver contract
5. `system_tray.py` - UI and menu handling

### Running Tests
```batch
# Development mode:
run.bat

# Check logs:
type bridge\log.log

# Build:
build.bat

# Test executable:
cd dist\BAB_Cloud
BAB_Cloud.exe
```

---

## Next Steps

After successful setup:

1. **Test X-Report**
   - Right-click system tray icon
   - Click "Print X-Report"
   - Verify receipt prints

2. **Test POS Integration**
   - Create a sale in your POS
   - Watch `log.log` for polling activity
   - Verify receipt prints automatically

3. **Test Fiscal Tools**
   - Right-click system tray icon
   - Click "Fiscal Tools"
   - Test various report functions

4. **Monitor Logs**
   ```batch
   # Watch in real-time:
   powershell Get-Content log.log -Wait -Tail 50
   ```

5. **Schedule Backups**
   - Backup `config.json`
   - Backup `*-transactions/` folders
   - Backup `odoo_credentials_encrypted.json` (if using Odoo)

---

## Support

If you encounter issues not covered here:

1. Check `log.log` for error messages
2. Search GitHub issues: https://github.com/solutech/bab-cloud/issues
3. Create new issue with:
   - Operating system version
   - Python version (`py -3.13 --version`)
   - Error message from log
   - Steps to reproduce

---

**Last Updated**: 2025-12-18
**Version**: 2026.1
