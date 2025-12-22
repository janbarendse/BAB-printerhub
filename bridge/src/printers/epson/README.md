# Epson Fiscal Printer Driver (STUB)

This is a placeholder stub for the Epson fiscal printer driver. Implementation is planned for Q2 2026.

## Status

**Current Status**: NOT IMPLEMENTED - Stub only

All methods raise `NotImplementedError` with the message:
```
Epson driver not implemented. Planned for Q2 2026. Uses different ESC/POS protocol.
```

## Protocol Differences

Unlike CTS310ii, Star, and Citizen printers (which use the MHI fiscal protocol), Epson fiscal printers use the **ESC/POS protocol**. This requires a completely different implementation approach.

### Key Differences:

1. **Protocol**: ESC/POS vs MHI
2. **Command Structure**: Different command syntax and encoding
3. **Communication**: Different serial communication patterns
4. **Data Formats**: Different data encoding and field structures

## Implementation Plan (Q2 2026)

### Phase 1: Protocol Research
- [ ] Obtain Epson ESC/POS fiscal protocol documentation
- [ ] Study command structure and communication patterns
- [ ] Identify compatible Epson fiscal printer models
- [ ] Document protocol differences vs MHI

### Phase 2: Core Implementation
- [ ] Implement serial communication layer
- [ ] Implement protocol command encoding/decoding
- [ ] Implement printer detection and connection
- [ ] Implement status checking and error handling

### Phase 3: Fiscal Operations
- [ ] Implement print_document (fiscal receipts, invoices, credit notes)
- [ ] Implement X and Z reports
- [ ] Implement document reprinting
- [ ] Implement cash drawer operations

### Phase 4: Testing & Validation
- [ ] Unit tests for all methods
- [ ] Integration tests with physical Epson printer
- [ ] Fiscal compliance validation
- [ ] Performance testing

### Phase 5: Documentation & Deployment
- [ ] Complete API documentation
- [ ] Usage examples and tutorials
- [ ] Configuration guide
- [ ] Deployment and rollout

## Supported Models (Planned)

The following Epson fiscal printer models are planned for support:

- Epson TM-T88 series (fiscal versions)
- Epson FP-81 II
- Epson FP-90 III
- Other ESC/POS fiscal-compliant models

## Configuration (Planned)

Expected configuration format when implemented:

```json
{
  "printer_type": "epson",
  "model": "TM-T88V",
  "baud_rate": 9600,
  "serial_timeout": 5,
  "debug": false,
  "fiscal_settings": {
    "operator_id": "001",
    "tax_rates": [7.0, 0.0, 0.0, 0.0]
  }
}
```

## Current Usage

```python
from bridge.printers.epson import EpsonDriver

config = {'debug': False}
driver = EpsonDriver(config)

# All operations will raise NotImplementedError
try:
    driver.connect()
except NotImplementedError as e:
    print(e)  # "Epson driver not implemented. Planned for Q2 2026..."
```

## Migration Path

When the Epson driver is implemented, existing code using the stub will continue to work. The only change will be that methods will return actual results instead of raising `NotImplementedError`.

## Contributing

If you have experience with Epson ESC/POS fiscal printers or protocol documentation, please contact the BAB Printhub team.

## Version History

- **v0.1.0** (2026): Initial stub implementation with NotImplementedError placeholders

## References

- ESC/POS Protocol Documentation (to be obtained)
- Epson Fiscal Printer Technical Manual (to be obtained)
- Epson Developer Resources: https://www.epson.com/developer
