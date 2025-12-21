# BAB-Cloud PrintHub - Tools

Utility scripts for debugging, testing, and occasional administrative tasks.

---

## Available Tools

### update_odoo_credentials.py

**Purpose**: Create encrypted Odoo credentials file

**Usage:**
```batch
cd tools
py -3.13 update_odoo_credentials.py
```

**Prompts:**
- Odoo URL (e.g., https://yourdomain.odoo.com)
- Database name
- Username
- Password
- POS config name

**Output**: `odoo_credentials_encrypted.json`

**Next Step**: Copy to bridge folder
```batch
copy odoo_credentials_encrypted.json ..\bridge\
```

---

## Future Tools

### test_printer_connection.py (Planned)

Test printer connection and basic commands.

```batch
py -3.13 test_printer_connection.py --port COM3
```

### test_odoo_connection.py (Planned)

Test Odoo XML-RPC connection.

```batch
py -3.13 test_odoo_connection.py
```

### test_tcpos_parser.py (Planned)

Test TCPOS XML parsing with sample files.

```batch
py -3.13 test_tcpos_parser.py sample.xml
```

### migrate_config.py (Planned)

Automatically migrate old config to new format.

```batch
py -3.13 migrate_config.py old_config.json new_config.json
```

---

## Adding New Tools

1. Create Python script in `tools/` folder
2. Add description to this README
3. Use standard argument parsing (argparse)
4. Include usage examples

---

**Last Updated**: 2025-12-18
