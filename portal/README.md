# Portal Integration (Placeholder)

This folder is a placeholder for the future WordPress-based licensing and management portal for BAB-Cloud PrintHub.

---

## Overview

The Portal system will replace the current temporary WordPress Z-report polling mechanism with a comprehensive cloud-based management platform.

**Status**: Planned for Q2 2026
**Current Workaround**: WordPress polling (bridge/wordpress/)

---

## Planned Features

### Device Management
- Device registration and licensing
- Serial number/NKF tracking
- License activation/deactivation
- Multi-device dashboard

### Remote Operations
- Remote Z-report triggers
- Remote configuration updates
- Firmware update distribution
- Remote diagnostics

### Monitoring & Analytics
- Real-time device status
- Sales analytics
- Error reporting
- Uptime monitoring

### Security
- Device authentication (token-based)
- Encrypted communication
- IP whitelisting
- Rate limiting

---

## Technical Architecture (Planned)

### WordPress Backend

**Plugins Required:**
- Custom BAB-Cloud Portal plugin
- WordPress REST API
- JWT authentication

**Database Tables:**
- `bab_devices` - Registered devices
- `bab_licenses` - License management
- `bab_commands` - Remote command queue
- `bab_logs` - Device logs and events

### Device-Side Client

**File**: `bridge/portal/portal_client.py` (to be created)

**Functionality:**
- Register device on first run
- Heartbeat polling (every 60s)
- Command queue polling
- Status reporting
- Log upload

### API Endpoints

```
POST /wp-json/bab/v1/device/register
POST /wp-json/bab/v1/device/heartbeat
GET  /wp-json/bab/v1/device/commands
POST /wp-json/bab/v1/device/logs
POST /wp-json/bab/v1/reports/z-trigger
GET  /wp-json/bab/v1/device/status
```

---

## Migration from WordPress Poller

### Current WordPress Poller

**File**: `bridge/wordpress/wordpress_poller.py`

**Functionality:**
- Polls for Z-report trigger flag file
- Executes Z-report
- Sends completion callback

**Limitations:**
- No authentication
- No device tracking
- No licensing
- Simple file-based triggers

### Future Portal Client

**Enhanced Features:**
- Device registration and authentication
- License validation
- Encrypted communication
- Command queue (not just Z-reports)
- Bi-directional status updates

---

## Development Roadmap

### Phase 1: Portal Backend (Q1 2026)
- [ ] WordPress plugin development
- [ ] Database schema design
- [ ] REST API implementation
- [ ] Admin dashboard UI
- [ ] Device registration flow

### Phase 2: Portal Client (Q2 2026)
- [ ] Device registration client
- [ ] Heartbeat polling
- [ ] Command execution
- [ ] Log upload
- [ ] License validation

### Phase 3: Integration (Q2 2026)
- [ ] Replace wordpress_poller.py
- [ ] Update config schema
- [ ] Migration tool for existing installations
- [ ] Testing with production devices

### Phase 4: Advanced Features (Q3 2026)
- [ ] Remote configuration
- [ ] Firmware updates
- [ ] Analytics dashboard
- [ ] Multi-device management

---

## Configuration (Future)

### Config Schema (Planned)

```json
{
  "portal": {
    "enabled": true,
    "url": "https://portal.babcloud.com",
    "device_id": "uuid-generated-on-registration",
    "license_key": "LICENSE-KEY-HERE",
    "heartbeat_interval": 60,
    "command_poll_interval": 30,
    "auto_update": true
  }
}
```

---

## Security Considerations

### Device Authentication

**Method**: JWT tokens

**Flow:**
1. Device registers with NKF and serial number
2. Portal generates device_id and JWT token
3. Device stores token securely
4. All API calls include token in Authorization header

### Encrypted Communication

**Protocol**: HTTPS only (TLS 1.2+)

**Certificate Validation**: Strict (no self-signed in production)

### License Validation

**Online**: Validate on every heartbeat (every 60s)

**Offline**: Grace period of 7 days

**Expired**: Disable printing, show warning

---

## Contact

For Portal development questions:
- **Project Lead**: TBD
- **Timeline**: Q1-Q2 2026
- **Priority**: High

---

**Last Updated**: 2025-12-18
**Status**: Planning Phase
**Estimated Launch**: Q2 2026
