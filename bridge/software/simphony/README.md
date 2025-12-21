# Simphony POS Integration (Placeholder)

## Overview

Oracle Simphony is an enterprise-grade point-of-sale system primarily used in the hospitality industry (restaurants, hotels, casinos). This integration is planned for **Q2 2026**.

## Current Status

**Status**: Not Implemented (Placeholder)
**Planned Release**: Q2 2026
**Priority**: Medium

## Technical Requirements

### System Information
- **Vendor**: Oracle Corporation
- **Product**: Simphony POS (formerly MICROS Simphony)
- **Database**: Oracle Database or MS SQL Server
- **Architecture**: Client-server with centralized database

### Integration Approaches (To Be Evaluated)

#### Option 1: Database Polling (Recommended)
- **Method**: Direct database queries to transaction tables
- **Pros**: Real-time access, no API dependencies
- **Cons**: Requires database credentials, schema knowledge
- **Tables to Monitor**:
  - `GuestCheck` (orders)
  - `CheckDetail` (order lines)
  - `Tender` (payments)

#### Option 2: API Integration
- **Method**: Use Simphony Integration Services (SIS) if available
- **Pros**: Official integration method, supported by Oracle
- **Cons**: May require licensing, API documentation access

#### Option 3: File Export
- **Method**: Configure Simphony to export transaction files
- **Pros**: Similar to TCPOS approach, no database access needed
- **Cons**: Not real-time, requires Simphony configuration

## Planned Implementation

### Phase 1: Research (Q1 2026)
- [ ] Obtain Simphony technical documentation
- [ ] Access test Simphony database/system
- [ ] Analyze transaction data structure
- [ ] Decide on integration approach

### Phase 2: Development (Q2 2026)
- [ ] Implement `SimphonyIntegration` class
- [ ] Create database polling or API client
- [ ] Develop transaction parser
- [ ] Map Simphony fields to standardized format

### Phase 3: Testing (Q2 2026)
- [ ] Test with sample Simphony data
- [ ] Verify all payment methods supported
- [ ] Test edge cases (voids, refunds, discounts)
- [ ] Integration testing with CTS310ii printer

## Data Mapping

### Transaction Structure (Preliminary)
```python
{
    "articles": [...],  # From CheckDetail table
    "payments": [...],  # From Tender table
    "order_id": "...",  # From GuestCheck.CheckID
    "receipt_number": "...",
    "customer_name": None,  # May not be available
    "customer_crib": None
}
```

## Configuration Schema

```json
{
  "software": {
    "simphony": {
      "enabled": true,
      "connection_string": "Server=hostname;Database=SimphonyDB;User=user;Password=pass;",
      "polling_interval_seconds": 5,
      "last_order_id": 0
    }
  }
}
```

## Known Challenges

1. **Database Schema Complexity**: Simphony has a complex normalized database schema
2. **Licensing Requirements**: May require specific Simphony modules/licenses
3. **Multi-site Support**: Simphony supports multiple locations in one database
4. **RVC (Revenue Center) Filtering**: Need to filter by specific revenue center
5. **Employee Information**: Simphony tracks employee/server per transaction

## Resources

- Oracle Simphony Documentation: [Oracle Support Portal](https://support.oracle.com/)
- Database Schema Reference: Available through Oracle support
- Integration Guide: Available through Oracle Professional Services

## Contact

For questions about Simphony integration:
- **Implementation Lead**: TBD
- **Target Customers**: Enterprise hospitality clients
- **Estimated Development Time**: 4-6 weeks

---

**Last Updated**: 2025-12-18
**Status**: Planning Phase
