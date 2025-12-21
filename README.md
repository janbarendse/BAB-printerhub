# BAB-Cloud PrintHub v2026

**Unified Fiscal Printer Bridge for Multiple POS Systems**

BAB-Cloud PrintHub is a modular, config-driven fiscal printer bridge application that connects multiple point-of-sale systems (Odoo, TCPOS, Simphony, QuickBooks) with multiple fiscal printer brands (CTS310ii, Star, Citizen, Epson).

---

## 🚀 Features

### Multi-POS Support
- ✅ **Odoo POS** - XML-RPC polling with encrypted credentials
- ✅ **TCPOS** - File-based transaction monitoring
- 🔜 **Simphony** - Oracle POS integration (Q2 2026)
- 🔜 **QuickBooks POS** - Desktop POS integration (Q3 2026)

### Multi-Printer Support
- ✅ **CTS310ii** - MHI fiscal protocol (fully implemented)
- ✅ **Star** - MHI fiscal protocol (same as CTS310ii)
- ✅ **Citizen** - MHI fiscal protocol (same as CTS310ii)
- 🔜 **Epson** - ESC/POS protocol (Q2 2026)

### Core Features
- 🔐 **Single Instance** - Prevents duplicate processes
- ⚙️ **Config-Driven** - One config.json controls everything
- 🎨 **Modern UI** - HTML-based fiscal tools modal
- 📊 **System Tray** - Runs in background, quick actions
- 📝 **Comprehensive Logging** - Debug and audit trails
- 🌐 **WordPress Polling** - Remote Z-report triggers (temporary)
- 🔄 **Modular Architecture** - Easy to add new POS/printer support

---

## 📋 Requirements

### System Requirements
- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.13 (exactly - not 3.12 or 3.14+)
- **RAM**: 512 MB minimum, 1 GB recommended
- **Disk**: 100 MB for application + space for logs/transactions

### Hardware Requirements
- **Printer**: Fiscal printer with serial/USB connection
- **COM Port**: Available serial port (auto-detected)

---

## 🛠️ Installation

### Option 1: Use Pre-Built Executable (Recommended)

1. Download the latest release from GitHub
2. Extract `BAB_Cloud` folder to desired location
3. Edit `config.json` to configure your POS and printer
4. Run `BAB_Cloud.exe`

### Option 2: Build from Source

#### Step 1: Clone Repository
```bash
git clone https://github.com/solutech/bab-cloud.git
cd bab-cloud
```

#### Step 2: Setup Environment
```batch
# Install Python 3.13 first
# Then run:
setup.bat
```

#### Step 3: Configure
Edit `bridge\config.json`:
```json
{
  "software": {
    "active": "odoo",  // or "tcpos"
    "odoo": {
      "enabled": true,
      "credentials_file": "odoo_credentials_encrypted.json",
      "polling_interval_seconds": 10,
      "last_order_id": 0
    }
  },
  "printer": {
    "active": "cts310ii",  // or "star", "citizen"
    "cts310ii": {
      "enabled": true,
      "com_port": null,  // null = auto-detect
      "baud_rate": 9600
    }
  }
}
```

#### Step 4: Run or Build
```batch
# Development mode:
run.bat

# Build executable:
build.bat
```

---

## 📖 Configuration

### Software Configuration

#### Odoo POS
```json
{
  "software": {
    "active": "odoo",
    "odoo": {
      "enabled": true,
      "credentials_file": "odoo_credentials_encrypted.json",
      "polling_interval_seconds": 10,
      "last_order_id": 0
    }
  }
}
```

**Create encrypted credentials:**
```batch
cd tools
python update_odoo_credentials.py
```

#### TCPOS
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

### Printer Configuration

```json
{
  "printer": {
    "active": "star",  // Choose: cts310ii, star, citizen, epson
    "star": {
      "enabled": true,
      "com_port": null,  // null = auto-detect
      "baud_rate": 9600,
      "timeout": 5
    }
  }
}
```

---

## 🎯 Usage

### System Tray Menu

Once running, BAB-Cloud appears in the system tray with these options:

- **Fiscal Tools** - Opens full fiscal reporting interface
- **Print X-Report** - Quick daily sales report (non-fiscal)
- **Print Z-Report** - Close fiscal day
- **NO SALE** - Open cash drawer
- **Quit BAB Cloud** - Exit application

### Fiscal Tools Modal

The fiscal tools modal provides:
- **X Reports** - Daily sales without closing fiscal day
- **Z Reports** - Fiscal day closing (once per day)
- **Historical Z Reports** - By date range or report number
- **Document Reprint** - Copy of previous receipts (NO SALE)
- **NO SALE** - Cash drawer opening

---

## 📂 Project Structure

```
BABprinterhub-v2026/
├── bridge/                      # Main application
│   ├── fiscal_printer_hub.py   # Entry point
│   ├── config.json              # Configuration
│   ├── core/                    # Core infrastructure
│   │   ├── config_manager.py
│   │   ├── system_tray.py
│   │   ├── fiscal_ui.py
│   │   └── text_utils.py
│   ├── software/                # POS integrations
│   │   ├── base_software.py
│   │   ├── odoo/
│   │   ├── tcpos/
│   │   ├── simphony/
│   │   └── quickbooks/
│   ├── printers/                # Printer drivers
│   │   ├── base_printer.py
│   │   ├── cts310ii/
│   │   ├── star/
│   │   ├── citizen/
│   │   └── epson/
│   └── wordpress/               # Remote triggers
├── tools/                       # Utility scripts
├── portal/                      # Future portal integration
├── docs/                        # Documentation
├── build.bat                    # Build script
├── run.bat                      # Development runner
└── setup.bat                    # Environment setup
```

---

## 🔧 Development

### Adding a New POS System

1. Create folder: `bridge/software/newsoftware/`
2. Implement `BaseSoftware` interface
3. Add config section to `config.json`
4. Update factory in `bridge/software/__init__.py`

See `docs/API.md` for full interface specification.

### Adding a New Printer Driver

1. Create folder: `bridge/printers/newprinter/`
2. Implement `BasePrinter` interface
3. Add config section to `config.json`
4. Update factory in `bridge/printers/__init__.py`

See `docs/API.md` for full interface specification.

---

## 📚 Documentation

- **[SETUP.md](docs/SETUP.md)** - Detailed setup guide
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture
- **[COMPATIBILITY.md](docs/COMPATIBILITY.md)** - POS/Printer compatibility
- **[API.md](docs/API.md)** - Interface specifications
- **[MIGRATION.md](docs/MIGRATION.md)** - Migration from old versions

---

## 🐛 Troubleshooting

### Printer Not Detected
- Check USB/serial connection
- Verify printer is powered on
- Check Device Manager for COM port
- Try manual COM port in config: `"com_port": "COM3"`

### Odoo Polling Not Working
- Verify credentials file exists
- Check Odoo server is reachable
- Check `log.log` for connection errors
- Verify POS config name matches Odoo

### TCPOS Files Not Processing
- Verify `transactions_folder` path is correct
- Check TCPOS is generating XML files
- Look for `.processed` or `.skipped` marker files
- Check file permissions

### Application Won't Start
- Verify Python 3.13 is installed
- Check `log.log` for error messages
- Ensure only one instance is running
- Try running `run.bat` to see console errors

---

## 📝 Logging

Logs are written to `log.log` in the application directory.

**Log Levels:**
- `DEBUG` - Detailed diagnostic information
- `INFO` - General information (default)
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical failures

**Configure log level in config.json:**
```json
{
  "system": {
    "log_level": "INFO"  // DEBUG, INFO, WARNING, ERROR, CRITICAL
  }
}
```

---

## 🔐 Security

### Odoo Credentials
- Stored encrypted with Fernet (symmetric encryption)
- Never commit credentials files to version control
- Use `tools/update_odoo_credentials.py` to update

### Best Practices
- Keep config.json secure (contains NKF fiscal ID)
- Regularly backup transaction folders
- Use strong passwords for Odoo accounts
- Limit network access to trusted IPs only

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Follow existing code style
4. Add tests for new features
5. Update documentation
6. Submit a pull request

See `docs/ARCHITECTURE.md` for system design details.

---

## 📜 License

Copyright © 2025 SOLUTECH
All rights reserved.

This software is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.

---

## 📞 Support

- **GitHub Issues**: https://github.com/solutech/bab-cloud/issues
- **Documentation**: https://github.com/solutech/bab-cloud/wiki
- **Email**: support@solutech.com

---

## 🗺️ Roadmap

### Q1 2026
- ✅ Merge Odoo and TCPOS codebases
- ✅ Modular architecture
- ✅ Multi-printer support (Star, Citizen)

### Q2 2026
- 🔜 Simphony POS integration
- 🔜 Epson printer driver
- 🔜 WordPress Portal replacement

### Q3 2026
- 🔜 QuickBooks POS integration
- 🔜 Auto-update mechanism
- 🔜 Remote configuration

### Q4 2026
- 🔜 Cloud backup/sync
- 🔜 Multi-printer support (route by location)
- 🔜 Mobile app monitoring

---

## 🙏 Acknowledgments

- MHI for CTS310ii protocol documentation
- Odoo community for XML-RPC guidance
- PyInstaller team for excellent packaging tool

---

**Built with ❤️ by SOLUTECH**
