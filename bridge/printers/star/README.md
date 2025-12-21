# Star Fiscal Printer Driver

## Overview

This driver provides support for Star fiscal printers that use the MHI fiscal protocol.

## Important Note

**Star printers use the same MHI fiscal protocol as CTS310ii printers.** This means:

- The protocol implementation is identical to CTS310ii
- All commands, responses, and communication patterns are the same
- The only difference is the printer brand name

## Protocol

- **Protocol Type**: MHI Fiscal Protocol
- **Based on**: MHI_Programacion_CW_(EN).pdf specification
- **Communication**: Serial (RS-232)
- **Baud Rate**: 9600 (default)
- **Data Format**: Hex-encoded commands with STX/ETX framing

## Features

All features are inherited from the CTS310ii implementation:

- Fiscal document printing (invoices, credit notes)
- X Reports (non-fiscal daily reports)
- Z Reports (fiscal day closing)
- Document reprinting
- No Sale operations
- Customer information handling
- Multiple payment methods
- Discounts and surcharges

## Configuration

```json
{
  "printer_type": "star",
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

## Usage

```python
from bridge.printers.star import StarDriver

config = {
    'baud_rate': 9600,
    'serial_timeout': 5,
    'debug': False
}

driver = StarDriver(config)
if driver.connect():
    print("Connected to Star printer")
    status = driver.get_status()
    print(status)
```

## Testing

The driver supports debug mode for testing without physical hardware:

```python
config = {'debug': True}
driver = StarDriver(config)
driver.connect()  # Will succeed without actual printer
```

## Compatibility

This driver should work with any Star fiscal printer that supports the MHI protocol, including but not limited to:

- Star TSP series with fiscal capabilities
- Star mPOP with fiscal module
- Other Star models certified for fiscal printing

## Support

For issues or questions, contact the BAB Printhub Team.
