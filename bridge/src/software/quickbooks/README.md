# QuickBooks POS Integration (Placeholder)

## Overview

QuickBooks Point of Sale (QBPOS) is Intuit's desktop-based point-of-sale solution for small to medium-sized retail and restaurant businesses. This integration is planned for **Q3 2026**.

## Current Status

**Status**: Not Implemented (Placeholder)
**Planned Release**: Q3 2026
**Priority**: Medium

## Technical Requirements

### System Information
- **Vendor**: Intuit Inc.
- **Product**: QuickBooks Point of Sale (Desktop)
- **Platform**: Windows only
- **Architecture**: Local desktop application with file-based database
- **Current Versions**: QBPOS v19 (2019), v20 (Desktop Plus)

### Integration Approaches (To Be Evaluated)

#### Option 1: QuickBooks SDK (Recommended)
- **Method**: Use QuickBooks SDK (QBSDK) for programmatic access
- **Pros**: Official integration method, well-documented
- **Cons**: Requires SDK licensing, desktop-only, COM-based
- **Requirements**:
  - QBSDK Web Connector
  - Certificate from Intuit
  - COM interop (pythonnet or comtypes)

#### Option 2: File Export Monitoring
- **Method**: Configure QBPOS to export transaction files (CSV/XML)
- **Pros**: No SDK required, similar to TCPOS approach
- **Cons**: Requires manual QBPOS configuration, not real-time
- **Export Options**:
  - Sales receipts export
  - Transaction log export

#### Option 3: Database File Access
- **Method**: Direct read access to QBPOS database files
- **Pros**: No configuration needed
- **Cons**: Proprietary format, file locking issues, unsupported
- **Risk**: High - may break with QBPOS updates

## Planned Implementation

### Phase 1: Research & SDK Setup (Q2 2026)
- [ ] Obtain QuickBooks SDK documentation
- [ ] Register for Intuit developer account
- [ ] Get SDK certificate for testing
- [ ] Set up test QuickBooks POS environment
- [ ] Evaluate SDK vs file export approach

### Phase 2: Development (Q3 2026)
- [ ] Implement `QuickBooksIntegration` class
- [ ] Develop SDK client or file monitor
- [ ] Create transaction parser
- [ ] Map QBPOS fields to standardized format
- [ ] Handle QBPOS-specific features (item modifiers, discounts)

### Phase 3: Testing (Q3 2026)
- [ ] Test with sample QBPOS data
- [ ] Verify payment method mapping
- [ ] Test refunds and exchanges
- [ ] Test with multiple QBPOS versions (v18, v19, v20)

## Data Mapping

### Transaction Structure (Preliminary)
```python
{
    "articles": [...],  # From SalesReceipt line items
    "payments": [...],  # From payment tender types
    "order_id": "...",  # Receipt number
    "receipt_number": "...",
    "customer_name": "...",  # From customer record
    "customer_crib": None  # May not be available
}
```

## Configuration Schema

```json
{
  "software": {
    "quickbooks": {
      "enabled": true,
      "company_file": "C:\\QuickBooks\\Company.qbw",
      "polling_interval_seconds": 10,
      "last_order_id": 0,
      "sdk_connection_mode": "desktop"
    }
  }
}
```

## Known Challenges

1. **SDK Certification**: Requires Intuit developer certification process
2. **Desktop-Only**: QBPOS is not cloud-based, requires local installation
3. **File Locking**: Database file may be locked by QBPOS
4. **Version Compatibility**: Multiple QBPOS versions in use
5. **Windows COM Dependencies**: SDK uses COM, requires Windows and pythonnet

## QuickBooks SDK Resources

- **QuickBooks SDK Documentation**: [Intuit Developer Portal](https://developer.intuit.com/)
- **QBSDK Download**: Available through Intuit developer account
- **Python Integration**: Use `pythonnet` or `comtypes` for COM interop
- **Community**: [Intuit Developer Community](https://community.intuit.com/)

## Alternative: QuickBooks Online

If QuickBooks Online (cloud version) is preferred:
- Use QuickBooks Online API (REST-based)
- Easier integration than desktop SDK
- Requires OAuth 2.0 authentication
- Not the same as QuickBooks POS (different product)

## Technical Dependencies

### Python Libraries Required
- `pythonnet` or `comtypes` (for COM interop)
- `pywin32` (for Windows-specific operations)
- Standard libraries: `xml.etree.ElementTree`, `csv`

### System Requirements
- Windows OS (QuickBooks POS is Windows-only)
- QuickBooks POS v18 or later
- Administrator privileges (for SDK access)

## Contact

For questions about QuickBooks POS integration:
- **Implementation Lead**: TBD
- **Target Customers**: Small retail businesses using QBPOS
- **Estimated Development Time**: 6-8 weeks (including SDK certification)

---

**Last Updated**: 2025-12-18
**Status**: Planning Phase
**Note**: QuickBooks POS has been discontinued by Intuit as of 2023. Existing installations still supported, but no new licenses available. Consider migrating customers to Odoo or other alternatives.
