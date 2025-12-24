# FiscalCloud / Bab Cloud – Z-Report Initiation Plan

## Goal
Build a minimal proof of concept that allows a Z-report to be initiated from WordPress and picked up by the on-prem PrinterHub (Python exe).  
After validation, evolve this into a proper WordPress plugin using a Custom Post Type (CPT) for printers, including licensing and secure polling.

---

## Phase 1 – Proof of Concept (No Plugin, No CPT)

### Objective
Prove end-to-end flow:
WordPress → Z-report trigger → PrinterHub detects → prints Z-report → clears trigger.

No UI polish, no history, no licensing logic yet.

---

### 1.1 Initiator File in WordPress Root
Create a PHP file in the WordPress root:

`/zreport-trigger.php`

Purpose:
- Act as a simple trigger endpoint
- Create or update a flag that PrinterHub can poll

Example behavior:
- When accessed, write a trigger flag
- Output a simple success response

Recommended PoC approach:
- Write a flag file: `/wp-content/zreport.flag`
- Contents: timestamp or UUID (unique per request)

Constraints:
- No authentication for PoC (optionally restrict by IP at the webserver/CDN level)
- One active Z-report at a time (simple “latest wins” semantics)

---

### 1.2 Trigger Mechanism (Pick One)

#### Option A: File-based flag (recommended for PoC simplicity)
- Create file: `/wp-content/zreport.flag`
- Contents: `timestamp|random` or UUID

Pros:
- Dead simple
- No WordPress bootstrapping needed for polling

Cons:
- Needs correct file permissions
- Public file access should be protected later

#### Option B: WordPress option
- `update_option('solutech_zreport_request', time())`

Pros:
- Stored inside WP
- Easy to evolve into plugin logic

Cons:
- PrinterHub must call an endpoint that boots WP to read it

Pick **Option A** for fastest PoC; move to CPT/meta in Phase 2.

---

### 1.3 PrinterHub (Python exe) – PoC Changes

Add logic to existing polling loop:

1) Poll for trigger:
- `GET https://portal.solutech.cloud/wp-content/zreport.flag`
  - If HTTP 200 and body contains a request id → treat as pending
  - If 404 → no pending request

2) If trigger detected:
- Execute Z-report print (existing printer code path)

3) Cleanup on success:
- Call a cleanup endpoint (recommended), or
- Delete the flag file via an authenticated endpoint

Recommended cleanup endpoint:
- `POST https://portal.solutech.cloud/zreport-complete.php` (PoC helper)
  - Deletes `/wp-content/zreport.flag`

Success criteria:
- Z-report prints once per trigger
- Trigger is cleared
- No re-printing on subsequent polls

---

### 1.4 Validation Checklist
- Trigger file creation works from browser (or curl)
- PrinterHub detects trigger within polling interval
- Z-report prints successfully
- Cleanup clears the trigger correctly
- Repeated polling does not reprint once cleared

Only proceed to Phase 2 once this is stable.

---

## Phase 2 – WordPress Plugin + CPT Architecture

### Objective
Replace PoC hacks with a maintainable WordPress plugin:
- Printers as CPT
- Z-report trigger via post meta
- Secure REST API
- License validation support

---

## Phase 3 – Plugin Structure

### 3.1 Plugin Skeleton

`/wp-content/plugins/fiscalcloud/`

```
fiscalcloud/
├── fiscalcloud.php
├── includes/
│   ├── cpt-printer.php
│   ├── rest-api.php
│   ├── licensing.php
│   └── admin-ui.php
└── readme.txt
```

---

### 3.2 Printer Custom Post Type (CPT)

CPT:
- Slug: `printer`
- Public: false
- Show in admin: true
- Has archive: false

Ownership model:
- One WordPress user (client) can own multiple printers
- Each printer CPT is assigned to a user (post_author) OR a dedicated meta `owner_user_id`

Recommendation:
- Use `post_author` as the owner, plus capabilities to restrict access.

---

### 3.3 Printer Meta Fields

Each printer CPT stores:

- `device_id` (string, unique, required)
- `device_label` (string, human friendly)
- `license_key` (string, store encrypted or hashed + token scheme)
- `license_expiry` (date string `YYYY-MM-DD`)
- `license_valid` (bool computed, or stored and updated)
- `last_seen` (timestamp)
- `hub_version` (string)
- `zreport_request` (timestamp or UUID; presence = pending)

No separate task table.

---

## Phase 4 – Z-Report Trigger (CPT-based)

### 4.1 Portal Action (WordPress UI)
User clicks “Print Z-report” on a specific printer:
- Plugin sets:
  - `update_post_meta($printer_id, 'zreport_request', $request_id);`
  - Where `$request_id` = `time()` or a UUID

Optional: prevent accidental double-click
- If `zreport_request` already exists → return “already pending”

---

### 4.2 PrinterHub Polling (REST)
REST endpoint:
- `GET /wp-json/fiscalcloud/v1/printer/{device_id}/zreport`

Response:
- Pending:
  ```
  { "pending": true, "request_id": "1700000000-abc123" }
  ```
- Not pending:
  ```
  { "pending": false }
  ```

---

### 4.3 Completion Callback (REST)
After printing:
- `POST /wp-json/fiscalcloud/v1/printer/{device_id}/zreport/complete`
Body:
```
{ "request_id": "1700000000-abc123", "status": "ok" }
```

Plugin:
- Verifies request_id matches current pending request (prevents stale completions)
- Clears:
  - `delete_post_meta($printer_id, 'zreport_request');`
- Updates:
  - `last_seen` and optional `last_zreport_at`

---

## Phase 5 – Licensing (Phase 2 Feature)

### 5.1 License Check Endpoint
- `GET /wp-json/fiscalcloud/v1/printer/{device_id}/license`

Response:
```
{ "valid": true, "expiry": "2025-12-31" }
```

PrinterHub behavior:
- If invalid:
  - refuse Z-report (and other fiscal actions if desired)
  - tray icon indicates “License invalid/expired”
  - tray menu can open portal renewal page

---

## Phase 6 – Security (Post-PoC)

### 6.1 Device Authentication
Do not use WP user passwords on devices.

Preferred options:
- WordPress Application Passwords (per device or per “device service user”)
- Device token stored in printer CPT meta:
  - `device_token_hash`
  - PrinterHub authenticates with bearer token; WP compares hash

### 6.2 REST API Access Control
- Poll endpoints require authentication
- Enforce that device_id belongs to authenticated device principal
- Rate-limit polling (e.g., 5–10 seconds) and apply server-side throttling

### 6.3 Avoid Direct Hardware Commands in WordPress
WordPress should only:
- create/clear “requests”
- show status, licensing
PrinterHub executes any hardware actions locally.

---

## WordPress CPT Configuration Instructions (Admin)

### Create Printers
1) Install and activate the `fiscalcloud` plugin
2) In WP Admin, go to **Printers**
3) Add new Printer:
   - Title: e.g. “Papagayo POS Printer 1”
   - Device ID: unique identifier stored on the PrinterHub device
   - Assign Author: the client WP user that owns the printer
   - License expiry/key fields
4) Save

### Assign Users
- Ensure each client has a WP user account
- Client should only see their own printers
  - Implement via capability checks + query filtering by `post_author`

---

## Non-Goals (Out of Scope)
- Z-report history and audit trail (can be added later with a custom table)
- X-reports
- Accounting exports
- Multi-country fiscal logic
- UI polishing beyond a functional admin page

---

## End State
- Clean separation:
  - WordPress: portal, auth, configuration, licensing, “request flags”
  - PrinterHub: execution, hardware access
- Minimal moving parts
- No premature overengineering
