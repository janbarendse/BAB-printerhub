<?php
/**
 * BABCloud Admin UI Class
 * Handles WordPress admin interface for printer management
 */

if (!defined('ABSPATH')) {
    exit;
}

class BABCloud_Admin_UI {

    /**
     * Initialize admin UI
     */
    public static function init() {
        if (!is_admin()) {
            return;
        }

        add_action('admin_menu', array(__CLASS__, 'add_admin_menu'));
        // Only add token management meta box - Voxel manages other fields
        add_action('add_meta_boxes', array(__CLASS__, 'add_token_meta_box'));
        add_action('save_post_printer', array(__CLASS__, 'save_token_meta'), 10, 2);
        add_filter('manage_printer_posts_columns', array(__CLASS__, 'custom_columns'));
        add_action('manage_printer_posts_custom_column', array(__CLASS__, 'custom_column_content'), 10, 2);
        // Show the raw token in the metabox only (single-use).
    }

    /**
     * Add admin menu
     */
    public static function add_admin_menu() {
        add_menu_page(
            __('BAB Cloud', 'babcloud'),
            __('BAB Cloud', 'babcloud'),
            'edit_posts',
            'babcloud-printers',
            array(__CLASS__, 'printer_list_page'),
            'dashicons-printer',
            30
        );

        add_submenu_page(
            'babcloud-printers',
            __('All Printers', 'babcloud'),
            __('All Printers', 'babcloud'),
            'edit_posts',
            'edit.php?post_type=printer'
        );

        add_submenu_page(
            'babcloud-printers',
            __('Add New', 'babcloud'),
            __('Add New', 'babcloud'),
            'edit_posts',
            'post-new.php?post_type=printer'
        );

        add_submenu_page(
            'babcloud-printers',
            __('Test Shortcodes', 'babcloud'),
            __('Test Shortcodes', 'babcloud'),
            'edit_posts',
            'babcloud-test-shortcodes',
            array(__CLASS__, 'test_shortcodes_page')
        );

        // Remove the duplicate submenu
        remove_submenu_page('babcloud-printers', 'babcloud-printers');
    }

    /**
     * Printer list page
     */
    public static function printer_list_page() {
        wp_redirect(admin_url('edit.php?post_type=printer'));
        exit;
    }

    /**
     * Test shortcodes page
     */
    public static function test_shortcodes_page() {
        include BABCLOUD_PLUGIN_DIR . 'templates/admin-test-shortcodes.php';
    }

    /**
     * Add only token management meta box
     */
    public static function add_token_meta_box() {
        add_meta_box(
            'printer_token',
            __('BABCloud Device Token', 'babcloud'),
            array(__CLASS__, 'printer_token_metabox'),
            'printer',
            'side',
            'high'
        );
    }

    /**
     * Old add_meta_boxes - disabled to avoid conflicts with Voxel
     */
    public static function add_meta_boxes() {
        add_meta_box(
            'printer_details',
            __('Printer Details', 'babcloud'),
            array(__CLASS__, 'printer_details_metabox'),
            'printer',
            'normal',
            'high'
        );

        add_meta_box(
            'printer_token',
            __('Device Authentication', 'babcloud'),
            array(__CLASS__, 'printer_token_metabox'),
            'printer',
            'side',
            'high'
        );

        add_meta_box(
            'printer_status',
            __('Status & Activity', 'babcloud'),
            array(__CLASS__, 'printer_status_metabox'),
            'printer',
            'side',
            'default'
        );
    }

    /**
     * Printer details meta box
     */
    public static function printer_details_metabox($post) {
        wp_nonce_field('babcloud_save_printer', 'printer_nonce');

        $device_id = get_post_meta($post->ID, 'device_id', true);
        $device_label = get_post_meta($post->ID, 'device_label', true);
        $license_key = get_post_meta($post->ID, 'license_key', true);
        $license_expiry = get_post_meta($post->ID, 'license_expiry', true);
        $printer_model = get_post_meta($post->ID, 'printer_model', true);

        ?>
        <table class="form-table">
            <tr>
                <th><label for="babcloud_device_id"><?php _e('Device ID', 'babcloud'); ?> *</label></th>
                <td>
                    <input type="text" id="babcloud_device_id" name="babcloud_device_id" value="<?php echo esc_attr($device_id); ?>" class="regular-text" required>
                    <p class="description"><?php _e('Unique identifier for this printer (e.g., printer-001)', 'babcloud'); ?></p>
                </td>
            </tr>
            <tr>
                <th><label for="babcloud_device_label"><?php _e('Device Label', 'babcloud'); ?></label></th>
                <td>
                    <input type="text" id="babcloud_device_label" name="babcloud_device_label" value="<?php echo esc_attr($device_label); ?>" class="regular-text">
                    <p class="description"><?php _e('Human-friendly label for this device', 'babcloud'); ?></p>
                </td>
            </tr>
            <tr>
                <th><label for="printer_model"><?php _e('Printer Model', 'babcloud'); ?></label></th>
                <td>
                    <select id="printer_model" name="printer_model" class="regular-text">
                        <option value="">-- <?php _e('Select Model', 'babcloud'); ?> --</option>
                        <option value="cts310ii" <?php selected($printer_model, 'cts310ii'); ?>>CTS310ii</option>
                        <option value="star" <?php selected($printer_model, 'star'); ?>>Star</option>
                        <option value="citizen" <?php selected($printer_model, 'citizen'); ?>>Citizen</option>
                        <option value="epson" <?php selected($printer_model, 'epson'); ?>>Epson</option>
                    </select>
                    <p class="description"><?php _e('Fiscal printer model', 'babcloud'); ?></p>
                </td>
            </tr>
            <tr>
                <th><label for="babcloud_license_key"><?php _e('License Key', 'babcloud'); ?></label></th>
                <td>
                    <input type="text" id="babcloud_license_key" name="babcloud_license_key" value="<?php echo esc_attr($license_key); ?>" class="regular-text">
                    <p class="description"><?php _e('Software license key', 'babcloud'); ?></p>
                </td>
            </tr>
            <tr>
                <th><label for="babcloud_license_expiry"><?php _e('License Expiry', 'babcloud'); ?></label></th>
                <td>
                    <input type="date" id="babcloud_license_expiry" name="babcloud_license_expiry" value="<?php echo esc_attr($license_expiry); ?>" class="regular-text">
                    <p class="description"><?php _e('License expiration date', 'babcloud'); ?></p>
                </td>
            </tr>
        </table>
        <?php
    }

    /**
     * Device token meta box
     */
    public static function printer_token_metabox($post) {
        $token_hash = get_post_meta($post->ID, 'device_token_hash', true);
        $token_generated = get_post_meta($post->ID, 'token_generated_at', true);
        $new_token = get_transient('babcloud_new_token_' . $post->ID);

        ?>
        <div style="padding: 10px;">
            <?php if ($new_token): ?>
                <div style="background: #f0f0f0; padding: 12px; margin: 0 0 12px 0; border-radius: 4px; border: 2px solid #00a32a;">
                    <p style="margin: 0 0 6px 0;"><strong><?php _e('✓ New Device Token (copy now)', 'babcloud'); ?></strong></p>
                    <code style="font-size: 13px; font-family: 'Courier New', monospace; word-break: break-all; display: block;"><?php echo esc_html($new_token); ?></code>
                    <button type="button" class="button" style="margin-top: 8px;" onclick="navigator.clipboard.writeText('<?php echo esc_js($new_token); ?>').then(() => alert('✓ Token copied to clipboard'))"><?php _e('Copy Token', 'babcloud'); ?></button>
                </div>
                <?php delete_transient('babcloud_new_token_' . $post->ID); ?>
            <?php endif; ?>
            <?php if ($token_hash): ?>
                <p><strong><?php _e('Token Status:', 'babcloud'); ?></strong> <span style="color: green;">✓ <?php _e('Generated', 'babcloud'); ?></span></p>
                <p><small><?php _e('Generated:', 'babcloud'); ?> <?php echo esc_html($token_generated); ?></small></p>
                <p><code style="word-break: break-all;"><?php echo esc_html(substr($token_hash, 0, 32)); ?>...</code></p>
                <p class="description"><?php _e('Token hash (for verification only)', 'babcloud'); ?></p>
                <hr>
                <p><button type="button" class="button" onclick="if(confirm('This will invalidate the current token. Continue?')) { document.getElementById('babcloud_regenerate_token').value='1'; this.form.submit(); }"><?php _e('Regenerate Token', 'babcloud'); ?></button></p>
                <input type="hidden" id="babcloud_regenerate_token" name="babcloud_regenerate_token" value="0">
            <?php else: ?>
                <p><strong><?php _e('Token Status:', 'babcloud'); ?></strong> <span style="color: red;">✗ <?php _e('Not Generated', 'babcloud'); ?></span></p>
                <p class="description"><?php _e('Token will be generated when you save this printer.', 'babcloud'); ?></p>
            <?php endif; ?>
        </div>
        <?php
    }

    /**
     * Printer status meta box
     */
    public static function printer_status_metabox($post) {
        $last_seen = get_post_meta($post->ID, 'last_seen', true);
        $hub_version = get_post_meta($post->ID, 'hub_version', true);
        $last_zreport = get_post_meta($post->ID, 'last_zreport_at', true);
        $last_xreport = get_post_meta($post->ID, 'last_xreport_at', true);
        $pending_command = get_post_meta($post->ID, 'pending_command', true);
        $command_status = get_post_meta($post->ID, 'command_status', true);

        $is_online = false;
        if ($last_seen) {
            $last_seen_time = strtotime($last_seen);
            $now = current_time('timestamp');
            $is_online = ($now - $last_seen_time) < 120;
        }

        ?>
        <div style="padding: 10px;">
            <p><strong><?php _e('Status:', 'babcloud'); ?></strong>
                <?php if ($is_online): ?>
                    <span style="color: green;">● <?php _e('Online', 'babcloud'); ?></span>
                <?php else: ?>
                    <span style="color: red;">● <?php _e('Offline', 'babcloud'); ?></span>
                <?php endif; ?>
            </p>

            <?php if ($last_seen): ?>
                <p><small><?php _e('Last Seen:', 'babcloud'); ?><br><?php echo esc_html($last_seen); ?></small></p>
            <?php endif; ?>

            <?php if ($hub_version): ?>
                <p><small><?php _e('Hub Version:', 'babcloud'); ?> <?php echo esc_html($hub_version); ?></small></p>
            <?php endif; ?>

            <hr>

            <?php if ($pending_command): ?>
                <p><strong><?php _e('Pending Command:', 'babcloud'); ?></strong></p>
                <p><span style="background: #fff3cd; padding: 2px 6px; border-radius: 3px;"><?php echo esc_html($command_status ?: 'pending'); ?></span></p>
            <?php else: ?>
                <p><small><?php _e('No pending commands', 'babcloud'); ?></small></p>
            <?php endif; ?>

            <?php if ($last_zreport): ?>
                <hr>
                <p><small><?php _e('Last Z-Report:', 'babcloud'); ?><br><?php echo esc_html($last_zreport); ?></small></p>
            <?php endif; ?>

            <?php if ($last_xreport): ?>
                <p><small><?php _e('Last X-Report:', 'babcloud'); ?><br><?php echo esc_html($last_xreport); ?></small></p>
            <?php endif; ?>
        </div>
        <?php
    }

    /**
     * Save only token generation - Voxel handles other fields
     */
    public static function save_token_meta($post_id, $post) {
        // Check autosave
        if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
            return;
        }

        // Check permissions
        if (!current_user_can('edit_post', $post_id)) {
            return;
        }

        // Check if token exists
        $existing_token = get_post_meta($post_id, 'device_token_hash', true);

        // If a raw device token is entered via Voxel fields, hash it for auth.
        $raw_token = get_post_meta($post_id, 'device_token', true);
        if (is_string($raw_token)) {
            $raw_token = trim($raw_token);
        }
        if (!empty($raw_token)) {
            update_post_meta($post_id, 'device_token_hash', hash('sha256', $raw_token));
            update_post_meta($post_id, 'token_generated_at', current_time('mysql'));
            set_transient('babcloud_new_token_' . $post_id, $raw_token, 300);
            delete_post_meta($post_id, 'device_token');
            $existing_token = get_post_meta($post_id, 'device_token_hash', true);
        }

        // Generate token if:
        // 1. No token exists (first save)
        // 2. Regenerate button was clicked
        $regenerate = isset($_POST['babcloud_regenerate_token']) && $_POST['babcloud_regenerate_token'] == '1';

        if (!$existing_token || $regenerate) {
            $token = BABCloud_Auth::generate_device_token($post_id);

            // Store token in transient for display on next page load
            if ($token) {
                set_transient('babcloud_new_token_' . $post_id, $token, 300); // 5 minute expiry
            }
        }

        self::normalize_device_id($post_id);
    }

    /**
     * Normalize device_id to slug style (lowercase, spaces to dashes).
     */
    private static function normalize_device_id($post_id) {
        static $updating = false;
        if ($updating) {
            return;
        }

        $device_id = get_post_meta($post_id, 'device_id', true);
        if (!$device_id) {
            return;
        }

        $normalized = sanitize_title($device_id);
        if ($normalized && $normalized !== $device_id) {
            $updating = true;
            update_post_meta($post_id, 'device_id', $normalized);
            $updating = false;
        }
    }

    /**
     * Old save_printer_meta - disabled, Voxel handles field saving
     */
    public static function save_printer_meta($post_id, $post) {
        // Check nonce
        if (!isset($_POST['printer_nonce']) || !wp_verify_nonce($_POST['printer_nonce'], 'babcloud_save_printer')) {
            return;
        }

        // Check autosave
        if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
            return;
        }

        // Check permissions
        if (!current_user_can('edit_post', $post_id)) {
            return;
        }

        // Save meta fields
        $fields = array(
            'device_id' => 'device_id',
            'device_label' => 'device_label',
            'license_key' => 'license_key',
            'license_expiry' => 'license_expiry',
            'printer_model' => 'printer_model',
        );

        foreach ($fields as $field => $meta_key) {
            if (isset($_POST['babcloud_' . $field])) {
                update_post_meta($post_id, $meta_key, sanitize_text_field($_POST['babcloud_' . $field]));
            }
        }

        // Generate or regenerate token
        $regenerate = isset($_POST['babcloud_regenerate_token']) && $_POST['babcloud_regenerate_token'] == '1';
        $existing_token = get_post_meta($post_id, 'device_token_hash', true);

        if (!$existing_token || $regenerate) {
            $token = BABCloud_Auth::generate_device_token($post_id);

            // Store token in transient for display on next page load
            if ($token) {
                set_transient('babcloud_new_token_' . $post_id, $token, 300); // 5 minute expiry
            }
        }
    }

    /**
     * Display token generation notice
     */
    public static function display_token_notice() {
        // Check if we're on a printer edit page
        $screen = get_current_screen();
        if (!$screen || $screen->post_type !== 'printer' || $screen->base !== 'post') {
            return;
        }

        // Get post ID
        $post_id = isset($_GET['post']) ? intval($_GET['post']) : 0;
        if (!$post_id) {
            return;
        }

        // Check for token transient
        $token = get_transient('babcloud_new_token_' . $post_id);
        if ($token) {
            // Display token
            ?>
            <div class="notice notice-success is-dismissible">
                <p><strong><?php _e('✓ Device Token Generated Successfully', 'babcloud'); ?></strong></p>
                <p><?php _e('Copy this token NOW and save it in your PrintHub config.json:', 'babcloud'); ?></p>
                <div style="background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 4px; border: 2px solid #00a32a;">
                    <code style="font-size: 14px; font-family: 'Courier New', monospace; word-break: break-all; display: block;"><?php echo esc_html($token); ?></code>
                </div>
                <button type="button" class="button" onclick="navigator.clipboard.writeText('<?php echo esc_js($token); ?>').then(() => alert('✓ Token copied to clipboard!\n\nToken length: <?php echo strlen($token); ?> characters'))">📋 Copy Token to Clipboard</button>
                <p style="background: #fff3cd; padding: 10px; border-left: 4px solid #f0b849; margin-top: 10px;">
                    <strong>⚠️ IMPORTANT:</strong> This is the <strong>ONLY TIME</strong> you will see this token. The token is <strong><?php echo strlen($token); ?> characters</strong> long.
                </p>
            </div>
            <?php
        }
    }

    /**
     * Custom columns for printer list
     */
    public static function custom_columns($columns) {
        $new_columns = array();
        $new_columns['cb'] = $columns['cb'];
        $new_columns['title'] = $columns['title'];
        $new_columns['device_id'] = __('Device ID', 'babcloud');
        $new_columns['status'] = __('Status', 'babcloud');
        $new_columns['last_seen'] = __('Last Seen', 'babcloud');
        $new_columns['license'] = __('License', 'babcloud');
        $new_columns['author'] = __('Owner', 'babcloud');
        $new_columns['date'] = $columns['date'];

        return $new_columns;
    }

    /**
     * Custom column content
     */
    public static function custom_column_content($column, $post_id) {
        switch ($column) {
            case 'device_id':
                $device_id = get_post_meta($post_id, 'device_id', true);
                echo $device_id ? esc_html($device_id) : '—';
                break;

            case 'status':
                $last_seen = get_post_meta($post_id, 'last_seen', true);
                if ($last_seen) {
                    $last_seen_time = strtotime($last_seen);
                    $now = current_time('timestamp');
                    $is_online = ($now - $last_seen_time) < 120;

                    if ($is_online) {
                        echo '<span style="color: green;">● Online</span>';
                    } else {
                        echo '<span style="color: red;">● Offline</span>';
                    }
                } else {
                    echo '<span style="color: gray;">— Never seen</span>';
                }
                break;

            case 'last_seen':
                $last_seen = get_post_meta($post_id, 'last_seen', true);
                if ($last_seen) {
                    $timestamp = strtotime($last_seen);
                    echo human_time_diff($timestamp, current_time('timestamp')) . ' ago';
                } else {
                    echo '—';
                }
                break;

            case 'license':
                $license_expiry = get_post_meta($post_id, 'license_expiry', true);
                if ($license_expiry) {
                    $expiry_date = strtotime($license_expiry);
                    $now = current_time('timestamp');

                    if ($expiry_date < $now) {
                        echo '<span style="color: red;">✗ Expired</span>';
                    } else {
                        $days = floor(($expiry_date - $now) / (60 * 60 * 24));
                        echo '<span style="color: green;">✓ Valid (' . $days . ' days)</span>';
                    }
                } else {
                    echo '—';
                }
                break;
        }
    }
}
