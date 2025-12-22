# Citizen Fiscal Printer Driver

This driver implements support for Citizen fiscal printers using the MHI fiscal protocol.

## Protocol Information

**Important**: Citizen fiscal printers use the **same MHI fiscal protocol** as CTS310ii printers.

This driver is a direct implementation of the CTS310ii driver with Citizen-specific branding and identification. All protocol commands, data formats, and communication patterns are identical to the CTS310ii implementation.

## Protocol Specification

Based on: `MHI_Programacion_CW_(EN).pdf`

## Features

- Full fiscal document printing (invoices, credit notes)
- X and Z reports
- Document reprinting (NO SALE)
- Cash drawer opening
- Date range and number range Z reports
- Automatic printer detection via COM port scanning
- Datetime synchronization
- Comprehensive error handling

## Configuration

```json
{
  "printer_type": "citizen",
  "baud_rate": 9600,
  "serial_timeout": 5,
  "debug": false,
  "client": {
    "NKF": "1234567890123456789"
  },
  "miscellaneous": {
    "default_client_name": "Regular client",
    "default_client_crib": "1000000000"
  }
}
```

## Usage Example

```python
from bridge.printers.citizen import CitizenDriver

config = {
    'baud_rate': 9600,
    'serial_timeout': 5,
    'debug': False,
    'client': {'NKF': '1234567890123456789'},
    'miscellaneous': {
        'default_client_name': 'Regular client',
        'default_client_crib': '1000000000'
    }
}

driver = CitizenDriver(config)
if driver.connect():
    print("Connected to Citizen printer")
    status = driver.get_status()
    print(status)
```

## Implementation Notes

1. **Protocol Compatibility**: This driver uses the exact same protocol implementation as CTS310ii
2. **Auto-detection**: Scans COM ports to automatically detect the printer
3. **Datetime Sync**: Automatically synchronizes printer datetime on connection
4. **Error Recovery**: Includes comprehensive error handling and recovery mechanisms
5. **Debug Mode**: Supports debug mode for testing without physical printer

## Version History

- **v1.0.0** (2026): Initial implementation based on CTS310ii protocol
