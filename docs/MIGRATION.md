# BAB-Cloud PrintHub - Migration Guide

Guide for migrating from bab-salesbook-v251217 (Odoo) and bab-tcpos-interface-v251217 (TCPOS) to the unified BAB-Cloud PrintHub v2026.

---

## Table of Contents

1. [Migration Overview](#migration-overview)
2. [Migrating from Odoo Version](#migrating-from-odoo-version)
3. [Migrating from TCPOS Version](#migrating-from-tcpos-version)
4. [Configuration Migration](#configuration-migration)
5. [Breaking Changes](#breaking-changes)

---

## Migration Overview

### What's Changed

**Old Architecture:**
- Two separate codebases (Odoo and TCPOS)
- Hardcoded POS integration
- Monolithic printer driver
- Config in different formats

**New Architecture:**
- Single unified codebase
- Modular POS integrations (plugin architecture)
- Modular printer drivers
- Standardized config schema
- Factory pattern for extensibility

### Benefits

1. ✅ **No Code Duplication** - Shared code for printer, UI, system tray
2. ✅ **Config-Driven** - Switch POS/printer without code changes
3. ✅ **Easier Maintenance** - Fix bugs once, benefit all configurations
4. ✅ **Extensible** - Add new POS/printers without modifying core
5. ✅ **Better Logging** - Unified logging with rotation
6. ✅ **Single Instance** - Prevents duplicate processes

---

## Migrating from Odoo Version

### Current Installation

```
D:\...\bab-salesbook-v251217\
├── bridge\
│   ├── fiscal_printer_hub.py
│   ├── cts310ii.py
│   ├── rpc_client.py
│   ├── odoo_parser.py
│   ├── config.json
│   ├── odoo_credentials_encrypted.json
│   └── transactions\
```

### Migration Steps

#### Step 1: Backup Current System

```batch
# Backup configuration
copy D:\...\bab-salesbook-v251217\bridge\config.json config_backup.json

# Backup credentials
copy D:\...\bab-salesbook-v251217\bridge\odoo_credentials_encrypted.json credentials_backup.json

# Backup transactions (optional)
xcopy /s /i D:\...\bab-salesbook-v251217\bridge\transactions transactions_backup\
```

#### Step 2: Install BAB-Cloud

```batch
# Option A: Use pre-built executable
# Extract BAB_Cloud.zip to desired location

# Option B: Build from source
git clone https://github.com/solutech/bab-cloud.git
cd bab-cloud
setup.bat
```

#### Step 3: Migrate Configuration

**Old config.json:**
```json
{
  "pos": {
    "name": "odoo"
  },
  "printer": {
    "name": "cts310ii"
  },
  "polling": {
    "odoo_retry_interval_seconds": 10
  },
  "wordpress": {
    "enabled": false
  }
}
```

**New config.json:**
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
        "Cash puna": "00",
        "Credit Card": "02",
        "Swipe punda": "03"
      }
    }
  },
  "printer": {
    "active": "cts310ii",
    "cts310ii": {
      "enabled": true,
      "com_port": null,
      "baud_rate": 9600,
      "timeout": 5
    }
  },
  "wordpress": {
    "enabled": false,
    "url": "https://babcloud.linux",
    "poll_interval": 5
  }
}
```

**Migration Script** (manual):
1. Copy `polling.odoo_retry_interval_seconds` → `software.odoo.polling_interval_seconds`
2. Move `payment_methods` → `software.odoo.payment_methods`
3. Keep `wordpress` section as-is
4. Add `software.active = "odoo"`
5. Add `printer.active = "cts310ii"`

#### Step 4: Migrate Credentials

```batch
# Copy encrypted credentials file
copy credentials_backup.json BAB_Cloud\odoo_credentials_encrypted.json
```

**Note**: Credentials format unchanged - no re-encryption needed.

#### Step 5: Migrate Last Order ID

**Old system:**
```batch
type D:\...\bab-salesbook-v251217\bridge\last_order_id.txt
# Example output: 12345
```

**New system:**
Edit `config.json`:
```json
{
  "software": {
    "odoo": {
      "last_order_id": 12345  // <- Insert value from file
    }
  }
}
```

#### Step 6: Migrate Transactions (Optional)

```batch
# Copy transaction history
xcopy /s D:\...\bab-salesbook-v251217\bridge\transactions\*.json BAB_Cloud\odoo-transactions\
```

**Note**: Folder renamed from `transactions/` to `odoo-transactions/`

#### Step 7: Test

```batch
# Run new system
cd BAB_Cloud
run.bat  # or BAB_Cloud.exe

# Check logs
type log.log

# Verify:
# - Printer connects
# - Odoo polling starts
# - System tray icon appears
```

---

## Migrating from TCPOS Version

### Current Installation

```
D:\...\bab-tcpos-interface-v251217\
├── fiscal_printer_hub.py
├── cts310ii.py
├── tcpos_parser.py
├── config.json
```

### Migration Steps

#### Step 1: Backup

```batch
copy D:\...\bab-tcpos-interface-v251217\config.json config_tcpos_backup.json
```

#### Step 2: Install BAB-Cloud

Same as Odoo migration (Step 2).

#### Step 3: Migrate Configuration

**Old config.json:**
```json
{
  "pos": {
    "name": "tcpos",
    "transactions_folder": "D:\\TCpos\\FrontEnd\\Transactions"
  },
  "printer": {
    "name": "cts310ii"
  }
}
```

**New config.json:**
```json
{
  "software": {
    "active": "tcpos",
    "tcpos": {
      "enabled": true,
      "transactions_folder": "D:\\TCpos\\FrontEnd\\Transactions",
      "last_order_id": 0
    }
  },
  "printer": {
    "active": "cts310ii",
    "cts310ii": {
      "enabled": true,
      "com_port": null,
      "baud_rate": 9600,
      "timeout": 5
    }
  }
}
```

**Migration Script** (manual):
1. Copy `pos.transactions_folder` → `software.tcpos.transactions_folder`
2. Add `software.active = "tcpos"`
3. Add `printer.active = "cts310ii"`

#### Step 4: Marker Files

**Note**: The new system uses the same marker file approach (.processed/.skipped).

**No action needed** - existing marker files will be recognized.

#### Step 5: Test

```batch
cd BAB_Cloud
run.bat

# Create test transaction in TCPOS
# Verify XML file is processed
# Check for .processed marker file
```

---

## Configuration Migration

### Config Schema Changes

| Old Path | New Path | Notes |
|----------|----------|-------|
| `pos.name` | `software.active` | Value unchanged |
| `pos.transactions_folder` | `software.tcpos.transactions_folder` | TCPOS only |
| `polling.odoo_retry_interval_seconds` | `software.odoo.polling_interval_seconds` | Odoo only |
| `printer.name` | `printer.active` | Value unchanged |
| `payment_methods` | `software.odoo.payment_methods` | Odoo only |
| `last_order_id.txt` (file) | `software.{name}.last_order_id` (config) | In JSON now |

### New Required Fields

Add these to config.json:

```json
{
  "client": {
    "NKF": "1234567890123456789"  // From old config
  },
  "miscellaneous": {
    "default_client_name": "Regular client",  // From old config
    "default_client_crib": "1000000000"       // From old config
  },
  "system": {
    "single_instance": true,
    "log_level": "INFO",
    "log_file": "log.log"
  }
}
```

### Removed Fields

These are no longer used:

- `pos.name` → Use `software.active`
- Global `payment_methods` → Now in `software.odoo.payment_methods`

---

## Breaking Changes

### 1. Import Paths Changed

**Old (Odoo):**
```python
import cts310ii
cts310ii.print_document(...)
```

**New:**
```python
from bridge.printers.cts310ii import CTS310iiDriver
driver = CTS310iiDriver(config)
driver.print_document(...)
```

**Impact**: Custom scripts need updating

---

### 2. Config File Structure

**Old**: Flat structure with `pos.name`

**New**: Nested structure with `software.active` and per-software settings

**Impact**: Must migrate config.json (see above)

---

### 3. Last Order ID Storage

**Old**: `last_order_id.txt` file

**New**: `config.json` → `software.{name}.last_order_id`

**Impact**: Must copy value to new location

---

### 4. Transaction Folder Names

**Old**: `transactions/`

**New**: `{software}-transactions/` (e.g., `odoo-transactions/`)

**Impact**: Historical transactions need moving if desired

---

### 5. Payment Method Configuration

**Old**: Global `payment_methods` dict

**New**: Per-software `software.odoo.payment_methods`

**Impact**: Odoo users must add to odoo config section

---

## Compatibility Layer

### Backwards Compatibility

**Not Provided**: No compatibility layer for old config format

**Reason**: Clean break for better architecture

**Recommendation**: Migrate fully to new format

---

## Rollback Procedure

If migration fails and you need to rollback:

### Step 1: Stop New System

```batch
# Find BAB_Cloud process
tasklist | findstr BAB_Cloud

# Kill if running
taskkill /f /im BAB_Cloud.exe
```

### Step 2: Restore Old Config

```batch
copy config_backup.json D:\...\bab-salesbook-v251217\bridge\config.json
```

### Step 3: Restart Old System

```batch
cd D:\...\bab-salesbook-v251217\bridge
python fiscal_printer_hub.py
```

---

## Post-Migration Checklist

- [ ] Backup old system completed
- [ ] New system installed
- [ ] config.json migrated
- [ ] Credentials copied (Odoo only)
- [ ] last_order_id migrated
- [ ] Test printer connection
- [ ] Test POS integration (process one order)
- [ ] Verify receipt prints correctly
- [ ] Test X-Report from system tray
- [ ] Test fiscal tools modal
- [ ] Monitor logs for errors
- [ ] Verify single instance enforcement
- [ ] Old system can be archived

---

## Common Migration Issues

### Issue: "Another instance is already running"

**Cause**: Old version still running

**Solution:**
```batch
# Kill old process
taskkill /f /im fiscal_printer_hub.exe
taskkill /f /im BAB_PrintHub.exe

# Wait 5 seconds
timeout /t 5

# Start new version
BAB_Cloud.exe
```

---

### Issue: "Printer not detected"

**Cause**: COM port changed or config incorrect

**Solution:**
```batch
# Check Device Manager for COM port
devmgmt.msc

# Update config.json:
{
  "printer": {
    "cts310ii": {
      "com_port": "COM3"  // Set manually
    }
  }
}
```

---

### Issue: "Configuration validation failed"

**Cause**: Missing required config fields

**Solution**: Use template from `docs/SETUP.md` and fill in your values

---

### Issue: "Odoo authentication failed"

**Cause**: Credentials file missing or corrupt

**Solution:**
```batch
# Re-create credentials
cd tools
python update_odoo_credentials.py

# Copy to application folder
copy odoo_credentials_encrypted.json ..\bridge\
```

---

## Migration Automation

### Automatic Migration Script (Future)

A migration script could be created:

```python
# migrate.py (not yet implemented)
import json

def migrate_config(old_path, new_path):
    # Load old config
    with open(old_path) as f:
        old = json.load(f)

    # Convert to new format
    new = {
        "software": {
            "active": old['pos']['name'],
            old['pos']['name']: {
                "enabled": True,
                # ... map old fields to new
            }
        },
        "printer": {
            "active": old['printer']['name'],
            # ...
        }
    }

    # Save new config
    with open(new_path, 'w') as f:
        json.dump(new, f, indent=2)

def migrate_last_order_id(txt_path, software_name):
    # Read from last_order_id.txt
    with open(txt_path) as f:
        order_id = int(f.read().strip())

    # Update config.json
    # ...
```

**Status**: Not implemented yet
**Planned**: Q1 2026

---

## Support

If you encounter migration issues:

1. Check this migration guide
2. Check logs: `log.log`
3. Consult: `docs/SETUP.md`
4. GitHub Issues: https://github.com/solutech/bab-cloud/issues

---

**Last Updated**: 2025-12-18
**Migration Version**: 1.0
