# WordPress Plugin Changes (Not in Git)

The WordPress plugin is located at `Z:\babcloud\app\public\wp-content\plugins\babcloud\` and is not tracked in this repository.

## Latest Changes

### Date: 2025-12-22 (Update 2 - Shortcode JavaScript Fixes)

**File**: `Z:\babcloud\app\public\wp-content\plugins\babcloud\includes\class-shortcodes.php`

**Change**: Fixed Print Check and No Sale button click handlers to read input values

**Why**: The JavaScript wasn't reading the document number and reason from the input fields, so commands were sent without parameters.

**Code Modified** (lines 172-184 and 227-239):

**Print Check Button** (lines 172-184):
```javascript
// OLD:
babcloud.triggerCommand(deviceId, 'print_check', {}, button);

// NEW:
var documentNumber = $('#check-number-' + deviceId).val();
if (!documentNumber) {
    alert('Please enter a document number');
    return;
}
babcloud.triggerCommand(deviceId, 'print_check', {document_number: documentNumber}, button);
```

**No Sale Button** (lines 227-239):
```javascript
// OLD:
babcloud.triggerCommand(deviceId, 'no_sale', {}, button);

// NEW:
var reason = $('#no-sale-reason-' + deviceId).val();
var params = {};
if (reason) {
    params.reason = reason;
}
babcloud.triggerCommand(deviceId, 'no_sale', params, button);
```

**Impact**:
- Print Check now reads document number from input and sends to API
- No Sale now reads optional reason from input and sends to API
- Fixes "not printing, no logs" issue in portal shortcode

---

### Date: 2025-12-22 (Update 1 - Authentication)

**File**: `Z:\babcloud\app\public\wp-content\plugins\babcloud\includes\class-auth.php`

**Change**: Updated `check_user_permission()` to support dual authentication

**Why**: The trigger endpoints need to accept both:
1. Device token authentication (X-Device-Token header) - for local UI in cloud mode
2. WordPress user session - for portal shortcodes

**Code Modified** (lines 152-206):

```php
public static function check_user_permission($request) {
    // Try device token authentication first (for local UI in cloud mode)
    $token = $request->get_header('X-Device-Token');
    if (!empty($token)) {
        // Use device token authentication
        return self::check_device_permission($request);
    }

    // Fall back to WordPress user session authentication
    if (!is_user_logged_in()) {
        return new WP_Error(
            'not_logged_in',
            __('You must be logged in to perform this action', 'babcloud'),
            array('status' => 401)
        );
    }

    // ... rest of user authentication logic
}
```

**Impact**:
- Fixes 401 authentication errors when local modal/system tray tries to queue commands in cloud mode
- Maintains security for portal shortcodes (requires WordPress login)
- Allows seamless operation in both contexts

---

## All WordPress Plugin Files

Location: `Z:\babcloud\app\public\wp-content\plugins\babcloud\`

```
babcloud/
├── babcloud.php                    # Main plugin file
├── includes/
│   ├── class-cpt-printer.php       # CPT meta field registration (uses Voxel's printer CPT)
│   ├── class-rest-api.php          # REST API endpoints
│   ├── class-auth.php              # Authentication (MODIFIED 2025-12-22)
│   ├── class-admin-ui.php          # Admin interface
│   └── class-shortcodes.php        # Portal shortcodes with styling
└── readme.txt                       # WordPress plugin readme
```

---

## Deployment Notes

When deploying updates to production:

1. **Backup** the entire `Z:\babcloud\app\public\wp-content\plugins\babcloud\` directory
2. **Test** authentication with both:
   - Local modal (device token)
   - Portal shortcode (WordPress user)
3. **Verify** no 401 errors in bridge logs
4. **Check** shortcode styling matches local modal

---

## Testing Checklist

- [ ] Local modal X-Report works in cloud mode
- [ ] Local modal Z-Report works in cloud mode
- [ ] Local modal No Sale works in cloud mode
- [ ] Local modal Print Check works in cloud mode
- [ ] Portal shortcode X-Report works (logged-in user)
- [ ] Portal shortcode Z-Report works (logged-in user)
- [ ] Portal shortcode No Sale works (logged-in user)
- [ ] Portal shortcode Print Check works (logged-in user)
- [ ] Bridge logs show no 401 errors
- [ ] Commands queue and execute successfully
- [ ] Shortcode styling matches local modal design

---

## Related Documentation

- `CLOUD_MODE_IMPLEMENTATION.md` - Complete cloud mode architecture
- `bridge/wordpress/wordpress_command_sender.py` - Bridge-side command sender
- `bridge/wordpress/wordpress_poller.py` - Bridge-side command executor
