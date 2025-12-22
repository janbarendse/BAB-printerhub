<?php
/**
 * BABCloud Shortcodes Class
 * Handles shortcodes for Elementor portal integration
 */

if (!defined('ABSPATH')) {
    exit;
}

class BABCloud_Shortcodes {

    /**
     * Initialize shortcodes
     */
    public static function init() {
        // Register shortcodes
        add_shortcode('babcloud_zreport', array(__CLASS__, 'zreport_shortcode'));
        add_shortcode('babcloud_xreport', array(__CLASS__, 'xreport_shortcode'));
        add_shortcode('babcloud_print_check', array(__CLASS__, 'print_check_shortcode'));
        add_shortcode('babcloud_zreport_range', array(__CLASS__, 'zreport_range_shortcode'));
        add_shortcode('babcloud_zreport_date', array(__CLASS__, 'zreport_date_shortcode'));
        add_shortcode('babcloud_no_sale', array(__CLASS__, 'no_sale_shortcode'));
        add_shortcode('babcloud_fiscal_tools', array(__CLASS__, 'fiscal_tools_shortcode'));

        // Enqueue scripts for frontend and admin
        add_action('wp_enqueue_scripts', array(__CLASS__, 'enqueue_scripts'));
        add_action('admin_enqueue_scripts', array(__CLASS__, 'enqueue_scripts'));
    }

    /**
     * Enqueue scripts and styles
     */
    public static function enqueue_scripts() {
        // Enqueue jQuery if not already loaded
        wp_enqueue_script('jquery');

        // Enqueue inline script for AJAX handling
        wp_add_inline_script('jquery', self::get_inline_script());

        // Enqueue inline styles
        if (function_exists('wp_add_inline_style')) {
            wp_add_inline_style('wp-block-library', self::get_inline_styles());
        } else {
            // Fallback for admin pages
            add_action('admin_head', function() {
                echo '<style>' . BABCloud_Shortcodes::get_inline_styles() . '</style>';
            });
        }
    }

    /**
     * Get inline JavaScript for AJAX handling
     */
    private static function get_inline_script() {
        $ajax_url = admin_url('admin-ajax.php');
        $rest_url = rest_url('babcloud/v1');

        return <<<JS
        (function($) {
            window.babcloud = {
                restUrl: '{$rest_url}',
                nonce: null,

                triggerCommand: function(deviceId, endpoint, params, button) {
                    if (!deviceId) {
                        alert('Error: Device ID is required');
                        return;
                    }

                    var url = this.restUrl + '/printer/' + deviceId + '/trigger/' + endpoint;
                    var originalText = button.text();
                    button.prop('disabled', true).text('Processing...');

                    $.ajax({
                        url: url,
                        method: 'POST',
                        data: JSON.stringify(params),
                        contentType: 'application/json',
                        beforeSend: function(xhr) {
                            xhr.setRequestHeader('X-WP-Nonce', $('#babcloud-nonce').val());
                        },
                        success: function(response) {
                            if (response.success) {
                                button.text('✓ Queued');
                                var commandId = response.command_id;

                                // Poll for status
                                setTimeout(function() {
                                    babcloud.pollStatus(deviceId, commandId, button, originalText);
                                }, 1000);
                            } else {
                                alert('Error: ' + (response.message || 'Unknown error'));
                                button.prop('disabled', false).text(originalText);
                            }
                        },
                        error: function(xhr) {
                            var error = xhr.responseJSON && xhr.responseJSON.message ? xhr.responseJSON.message : 'Request failed';
                            alert('Error: ' + error);
                            button.prop('disabled', false).text(originalText);
                        }
                    });
                },

                pollStatus: function(deviceId, commandId, button, originalText) {
                    var url = this.restUrl + '/printer/' + deviceId + '/command/' + commandId + '/status';
                    var pollCount = 0;
                    var maxPolls = 60; // 60 seconds max

                    var poll = function() {
                        $.ajax({
                            url: url,
                            method: 'GET',
                            beforeSend: function(xhr) {
                                xhr.setRequestHeader('X-WP-Nonce', $('#babcloud-nonce').val());
                            },
                            success: function(response) {
                                if (response.status === 'completed') {
                                    button.text('✓ Completed').removeClass('babcloud-btn-primary').addClass('babcloud-btn-success');
                                    setTimeout(function() {
                                        button.prop('disabled', false).text(originalText).removeClass('babcloud-btn-success').addClass('babcloud-btn-primary');
                                    }, 3000);
                                } else if (response.status === 'failed') {
                                    button.text('✗ Failed').removeClass('babcloud-btn-primary').addClass('babcloud-btn-error');
                                    alert('Command failed: ' + (response.error || 'Unknown error'));
                                    setTimeout(function() {
                                        button.prop('disabled', false).text(originalText).removeClass('babcloud-btn-error').addClass('babcloud-btn-primary');
                                    }, 3000);
                                } else if (response.status === 'pending') {
                                    pollCount++;
                                    if (pollCount < maxPolls) {
                                        button.text('Processing... (' + pollCount + 's)');
                                        setTimeout(poll, 1000);
                                    } else {
                                        button.text('Timeout').removeClass('babcloud-btn-primary').addClass('babcloud-btn-warning');
                                        setTimeout(function() {
                                            button.prop('disabled', false).text(originalText).removeClass('babcloud-btn-warning').addClass('babcloud-btn-primary');
                                        }, 3000);
                                    }
                                }
                            },
                            error: function() {
                                button.prop('disabled', false).text(originalText);
                            }
                        });
                    };

                    poll();
                }
            };

            // Z-Report confirmation
            $(document).on('click', '.babcloud-zreport-btn', function(e) {
                e.preventDefault();
                var button = $(this);
                var deviceId = button.data('device-id');

                if (confirm('This will close the fiscal day and print a Z-Report. Continue?')) {
                    babcloud.triggerCommand(deviceId, 'zreport', {}, button);
                }
            });

            // X-Report (no confirmation)
            $(document).on('click', '.babcloud-xreport-btn', function(e) {
                e.preventDefault();
                var button = $(this);
                var deviceId = button.data('device-id');
                babcloud.triggerCommand(deviceId, 'xreport', {}, button);
            });

            // Print Check
            $(document).on('click', '.babcloud-print-check-btn', function(e) {
                e.preventDefault();
                var button = $(this);
                var deviceId = button.data('device-id');
                babcloud.triggerCommand(deviceId, 'print_check', {}, button);
            });

            // Z-Report Range
            $(document).on('click', '.babcloud-zreport-range-btn', function(e) {
                e.preventDefault();
                var button = $(this);
                var deviceId = button.data('device-id');
                var fromZ = $('#babcloud-from-z-' + deviceId).val();
                var toZ = $('#babcloud-to-z-' + deviceId).val();

                if (!fromZ || !toZ) {
                    alert('Please enter both From and To Z-numbers');
                    return;
                }

                if (confirm('Print Z-Reports from ' + fromZ + ' to ' + toZ + '?')) {
                    babcloud.triggerCommand(deviceId, 'zreport_range', {from_z: fromZ, to_z: toZ}, button);
                }
            });

            // Z-Report by Date
            $(document).on('click', '.babcloud-zreport-date-btn', function(e) {
                e.preventDefault();
                var button = $(this);
                var deviceId = button.data('device-id');
                var startDate = $('#babcloud-start-date-' + deviceId).val();
                var endDate = $('#babcloud-end-date-' + deviceId).val();

                if (!startDate || !endDate) {
                    alert('Please select both start and end dates');
                    return;
                }

                var confirmMsg = startDate === endDate ?
                    'Print Z-Report for ' + startDate + '?' :
                    'Print Z-Reports from ' + startDate + ' to ' + endDate + '?';

                if (confirm(confirmMsg)) {
                    babcloud.triggerCommand(deviceId, 'zreport_date', {start_date: startDate, end_date: endDate}, button);
                }
            });

            // No Sale
            $(document).on('click', '.babcloud-no-sale-btn', function(e) {
                e.preventDefault();
                var button = $(this);
                var deviceId = button.data('device-id');
                babcloud.triggerCommand(deviceId, 'no_sale', {}, button);
            });
        })(jQuery);
JS;
    }

    /**
     * Get inline CSS styles (Modal-matching Tailwind design)
     */
    private static function get_inline_styles() {
        return <<<CSS
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

        .babcloud-shortcode {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 20px 0;
            padding: 16px;
            border: 1px solid #d1d5db;
            border-radius: 12px;
            background: white;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        }
        .babcloud-shortcode h4 {
            margin-top: 0;
            margin-bottom: 12px;
            color: #1f2937;
            font-size: 16px;
            font-weight: 700;
        }
        .babcloud-status {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 10px;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }
        .babcloud-status-online {
            background: #10b981;
            color: white;
        }
        .babcloud-status-offline {
            background: #ef4444;
            color: white;
        }
        .babcloud-form-group {
            margin-bottom: 12px;
        }
        .babcloud-form-group label {
            display: block;
            margin-bottom: 4px;
            font-weight: 600;
            font-size: 12px;
            color: #4b5563;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }
        .babcloud-form-group input {
            width: 100%;
            padding: 10px;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.15s ease;
            font-family: 'Inter', sans-serif;
        }
        .babcloud-form-group input:focus {
            outline: none;
            border-color: #dc2626;
            box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1);
        }
        .babcloud-form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 12px;
        }
        .babcloud-btn {
            width: 100%;
            padding: 10px 16px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
            font-family: 'Inter', sans-serif;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        .babcloud-btn-primary {
            background: #dc2626;
            color: white;
        }
        .babcloud-btn-primary:hover:not(:disabled) {
            background: #b91c1c;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            transform: translateY(-1px);
        }
        .babcloud-btn-secondary {
            background: #4b5563;
            color: white;
        }
        .babcloud-btn-secondary:hover:not(:disabled) {
            background: #374151;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .babcloud-btn-success {
            background: #10b981;
            color: white;
        }
        .babcloud-btn-error {
            background: #ef4444;
            color: white;
        }
        .babcloud-btn-warning {
            background: #f59e0b;
            color: white;
        }
        .babcloud-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .babcloud-btn-large {
            padding: 16px;
            font-size: 16px;
            font-weight: 700;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .babcloud-btn-large:hover:not(:disabled) {
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            transform: scale(1.02);
        }
        .babcloud-info {
            margin-top: 8px;
            font-size: 12px;
            color: #6b7280;
            line-height: 1.5;
        }
        .babcloud-error {
            color: #dc2626;
            margin-top: 10px;
            font-weight: 600;
            padding: 12px;
            background: #fee2e2;
            border-radius: 8px;
            border-left: 4px solid #dc2626;
        }
        .babcloud-shortcode-zreport {
            background: #fef2f2;
            border: 2px solid #dc2626;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .babcloud-shortcode-zreport h4 {
            color: #991b1b;
            font-size: 18px;
        }
        /* Unified Fiscal Tools Modal */
        .babcloud-fiscal-tools {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 900px;
            margin: 20px auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            overflow: hidden;
        }
        .babcloud-fiscal-header {
            background: linear-gradient(to right, #b91c1c, #991b1b);
            padding: 24px;
            color: white;
        }
        .babcloud-fiscal-header h2 {
            margin: 0 0 4px 0;
            font-size: 24px;
            font-weight: 700;
            color: white;
        }
        .babcloud-fiscal-header p {
            margin: 0;
            color: rgba(255, 255, 255, 0.9);
            font-size: 14px;
        }
        .babcloud-fiscal-content {
            padding: 16px;
        }
        .babcloud-section-title {
            font-size: 16px;
            font-weight: 700;
            color: #1f2937;
            margin: 0 0 12px 0;
            padding-bottom: 8px;
        }
        .babcloud-grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 16px;
        }
        @media (max-width: 768px) {
            .babcloud-grid-2 {
                grid-template-columns: 1fr;
            }
        }
        .babcloud-card {
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        }
        .babcloud-card-zreport {
            background: #fef2f2;
            border: 2px solid #dc2626;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .babcloud-card-zreport h3 {
            color: #991b1b;
        }
        .babcloud-card h3 {
            font-size: 16px;
            font-weight: 700;
            margin: 0 0 8px 0;
            color: #1f2937;
        }
        .babcloud-card p {
            font-size: 13px;
            color: #6b7280;
            margin: 0 0 12px 0;
            line-height: 1.5;
        }
        .babcloud-quick-actions {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        .babcloud-quick-action {
            flex: 1;
            min-width: 250px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 12px;
        }
        .babcloud-quick-action h4 {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.025em;
            color: rgba(255, 255, 255, 0.9);
            margin: 0 0 8px 0;
        }
        .babcloud-quick-action-flex {
            display: flex;
            gap: 8px;
        }
        .babcloud-quick-action input {
            flex: 1;
            padding: 8px;
            border: none;
            border-radius: 8px;
            font-size: 13px;
        }
        .babcloud-quick-action button {
            white-space: nowrap;
            padding: 8px 16px;
            background: white;
            color: #dc2626;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.15s ease;
            font-size: 13px;
        }
        .babcloud-quick-action button:hover {
            background: #fef2f2;
        }
CSS;
    }

    /**
     * Common shortcode wrapper
     */
    private static function render_shortcode($device_id, $title, $content, $info = '', $extra_class = '') {
        if (!is_user_logged_in()) {
            return '<div class="babcloud-error">You must be logged in to use this feature. <a href="' . wp_login_url(get_permalink()) . '">Login</a></div>';
        }

        if (empty($device_id)) {
            return '<div class="babcloud-error">Error: device_id parameter is required</div>';
        }

        // Get printer
        $printer = babcloud_get_printer_by_device_id($device_id);

        if (!$printer) {
            return '<div class="babcloud-error">Error: Printer not found</div>';
        }

        // Check permissions
        $user_id = get_current_user_id();
        if (!babcloud_user_owns_printer($user_id, $printer->ID)) {
            return '<div class="babcloud-error">Error: You do not have permission to access this printer</div>';
        }

        // Check printer status (bridge must be active within last 3 minutes)
        $last_seen = get_post_meta($printer->ID, '_last_seen', true);
        $is_online = false;
        $bridge_active = false;
        $offline_message = '';

        if ($last_seen) {
            $last_seen_time = strtotime($last_seen);
            $now = current_time('timestamp');
            $offline_seconds = $now - $last_seen_time;

            // Consider online if seen within last 2 minutes (visual indicator)
            $is_online = $offline_seconds < 120;

            // Bridge is active (can send commands) if seen within last 3 minutes
            $bridge_active = $offline_seconds < 180;

            if (!$bridge_active) {
                $offline_minutes = ceil($offline_seconds / 60);
                $offline_message = sprintf('PrintHub bridge is offline (last seen %d minutes ago). Commands cannot be sent.', $offline_minutes);
            }
        } else {
            $offline_message = 'PrintHub bridge has never connected. Please configure and start the bridge.';
        }

        $status_class = $is_online ? 'babcloud-status-online' : 'babcloud-status-offline';
        $status_text = $is_online ? 'Online' : 'Offline';

        // Add nonce for REST API
        $nonce = wp_create_nonce('wp_rest');

        ob_start();
        ?>
        <div class="babcloud-shortcode <?php echo esc_attr($extra_class); ?>">
            <input type="hidden" id="babcloud-nonce" value="<?php echo esc_attr($nonce); ?>">
            <h4>
                <?php echo esc_html($title); ?>
                <span class="babcloud-status <?php echo esc_attr($status_class); ?>">
                    <?php echo esc_html($status_text); ?>
                </span>
            </h4>

            <?php if (!$bridge_active): ?>
                <div class="babcloud-error" style="margin-bottom: 15px;">
                    ⚠️ <?php echo esc_html($offline_message); ?>
                </div>
                <div style="opacity: 0.5; pointer-events: none;">
                    <?php echo $content; ?>
                </div>
            <?php else: ?>
                <?php echo $content; ?>
            <?php endif; ?>

            <?php if ($info): ?>
                <div class="babcloud-info"><?php echo esc_html($info); ?></div>
            <?php endif; ?>
        </div>
        <?php
        return ob_get_clean();
    }

    /**
     * Z-Report Now shortcode
     */
    public static function zreport_shortcode($atts) {
        $atts = shortcode_atts(array(
            'device_id' => '',
        ), $atts);

        $content = '<button class="babcloud-btn babcloud-btn-primary babcloud-btn-large babcloud-zreport-btn" data-device-id="' . esc_attr($atts['device_id']) . '">Close Fiscal Day - Z Report</button>';

        return self::render_shortcode($atts['device_id'], 'Z Report (Today)', $content, 'Closes the fiscal day and prints the Z Report. Printer will only print if there are transactions.', 'babcloud-shortcode-zreport');
    }

    /**
     * X-Report shortcode
     */
    public static function xreport_shortcode($atts) {
        $atts = shortcode_atts(array(
            'device_id' => '',
        ), $atts);

        $content = '<button class="babcloud-btn babcloud-btn-secondary babcloud-xreport-btn" data-device-id="' . esc_attr($atts['device_id']) . '">Print X Report</button>';

        return self::render_shortcode($atts['device_id'], 'X Report (Today)', $content, 'Current shift status without closing the fiscal day.');
    }

    /**
     * Print Check shortcode
     */
    public static function print_check_shortcode($atts) {
        $atts = shortcode_atts(array(
            'device_id' => '',
        ), $atts);

        $content = '<button class="babcloud-btn babcloud-btn-primary babcloud-print-check-btn" data-device-id="' . esc_attr($atts['device_id']) . '">Print Printer Check</button>';

        return self::render_shortcode($atts['device_id'], 'Printer Check', $content, 'Prints a test receipt to verify printer connectivity.');
    }

    /**
     * Z-Report Range shortcode
     */
    public static function zreport_range_shortcode($atts) {
        $atts = shortcode_atts(array(
            'device_id' => '',
        ), $atts);

        $device_id = esc_attr($atts['device_id']);

        $content = '
            <div class="babcloud-form-grid">
                <div class="babcloud-form-group">
                    <label for="babcloud-from-z-' . $device_id . '">Start #</label>
                    <input type="number" id="babcloud-from-z-' . $device_id . '" placeholder="100" min="1">
                </div>
                <div class="babcloud-form-group">
                    <label for="babcloud-to-z-' . $device_id . '">End #</label>
                    <input type="number" id="babcloud-to-z-' . $device_id . '" placeholder="150" min="1">
                </div>
            </div>
            <button class="babcloud-btn babcloud-btn-primary babcloud-zreport-range-btn" data-device-id="' . $device_id . '">Print Number Range</button>
        ';

        return self::render_shortcode($atts['device_id'], 'Z Reports by Number Range', $content, '');
    }

    /**
     * Z-Report by Date shortcode
     */
    public static function zreport_date_shortcode($atts) {
        $atts = shortcode_atts(array(
            'device_id' => '',
        ), $atts);

        $device_id = esc_attr($atts['device_id']);
        $yesterday = date('Y-m-d', strtotime('-1 day'));

        $content = '
            <div class="babcloud-form-grid">
                <div class="babcloud-form-group">
                    <label for="babcloud-start-date-' . $device_id . '">From</label>
                    <input type="date" id="babcloud-start-date-' . $device_id . '" value="' . $yesterday . '" max="' . date('Y-m-d') . '">
                </div>
                <div class="babcloud-form-group">
                    <label for="babcloud-end-date-' . $device_id . '">To</label>
                    <input type="date" id="babcloud-end-date-' . $device_id . '" value="' . $yesterday . '" max="' . date('Y-m-d') . '">
                </div>
            </div>
            <button class="babcloud-btn babcloud-btn-primary babcloud-zreport-date-btn" data-device-id="' . $device_id . '">Print Date Range</button>
        ';

        return self::render_shortcode($atts['device_id'], 'Z Reports by Date Range', $content, '');
    }

    /**
     * No Sale shortcode
     */
    public static function no_sale_shortcode($atts) {
        $atts = shortcode_atts(array(
            'device_id' => '',
        ), $atts);

        $content = '<button class="babcloud-btn babcloud-btn-primary babcloud-no-sale-btn" data-device-id="' . esc_attr($atts['device_id']) . '">Open Cash Drawer (No Sale)</button>';

        return self::render_shortcode($atts['device_id'], 'No Sale', $content, 'Opens the cash drawer without recording a transaction.');
    }

    /**
     * Unified Fiscal Tools shortcode - Complete modal-style interface
     */
    public static function fiscal_tools_shortcode($atts) {
        $atts = shortcode_atts(array(
            'device_id' => '',
        ), $atts);

        if (!is_user_logged_in()) {
            return '<div class="babcloud-error">You must be logged in to use this feature. <a href="' . wp_login_url(get_permalink()) . '">Login</a></div>';
        }

        if (empty($atts['device_id'])) {
            return '<div class="babcloud-error">Error: device_id parameter is required</div>';
        }

        $device_id = esc_attr($atts['device_id']);

        // Get printer
        $printer = babcloud_get_printer_by_device_id($device_id);

        if (!$printer) {
            return '<div class="babcloud-error">Error: Printer not found</div>';
        }

        // Check permissions
        $user_id = get_current_user_id();
        if (!babcloud_user_owns_printer($user_id, $printer->ID)) {
            return '<div class="babcloud-error">Error: You do not have permission to access this printer</div>';
        }

        // Check printer status (bridge must be active within last 3 minutes)
        $last_seen = get_post_meta($printer->ID, '_last_seen', true);
        $is_online = false;
        $bridge_active = false;
        $offline_message = '';

        if ($last_seen) {
            $last_seen_time = strtotime($last_seen);
            $now = current_time('timestamp');
            $offline_seconds = $now - $last_seen_time;

            // Consider online if seen within last 2 minutes (visual indicator)
            $is_online = $offline_seconds < 120;

            // Bridge is active (can send commands) if seen within last 3 minutes
            $bridge_active = $offline_seconds < 180;

            if (!$bridge_active) {
                $offline_minutes = ceil($offline_seconds / 60);
                $offline_message = sprintf('PrintHub bridge is offline (last seen %d minutes ago). Commands cannot be sent.', $offline_minutes);
            }
        } else {
            $offline_message = 'PrintHub bridge has never connected. Please configure and start the bridge.';
        }

        $status_class = $is_online ? 'babcloud-status-online' : 'babcloud-status-offline';
        $status_text = $is_online ? 'Online' : 'Offline';

        $nonce = wp_create_nonce('wp_rest');
        $yesterday = date('Y-m-d', strtotime('-1 day'));

        ob_start();
        ?>
        <div class="babcloud-fiscal-tools">
            <input type="hidden" id="babcloud-nonce" value="<?php echo esc_attr($nonce); ?>">

            <!-- Header -->
            <div class="babcloud-fiscal-header">
                <h2>Fiscal PrintHub <span class="babcloud-status <?php echo esc_attr($status_class); ?>"><?php echo esc_html($status_text); ?></span></h2>
                <p>Quick Report Generation</p>

                <?php if (!$bridge_active): ?>
                    <div style="background: rgba(255, 255, 255, 0.2); padding: 12px; border-radius: 8px; margin-top: 12px; border-left: 4px solid white;">
                        <strong>⚠️ Bridge Offline</strong><br>
                        <small><?php echo esc_html($offline_message); ?></small>
                    </div>
                <?php endif; ?>

                <?php if (!$bridge_active): ?>
                    <div style="opacity: 0.5; pointer-events: none;">
                <?php endif; ?>

                <!-- Quick Actions -->
                <div class="babcloud-quick-actions">
                    <!-- Receipt Copy -->
                    <div class="babcloud-quick-action">
                        <h4>Receipt Copy</h4>
                        <div class="babcloud-quick-action-flex">
                            <input type="text" id="check-number-<?php echo $device_id; ?>" placeholder="Doc #">
                            <button onclick="jQuery(this).addClass('babcloud-print-check-btn').attr('data-device-id', '<?php echo $device_id; ?>').click();" class="babcloud-print-check-btn" data-device-id="<?php echo $device_id; ?>">Print Copy</button>
                        </div>
                    </div>

                    <!-- No Sale -->
                    <div class="babcloud-quick-action">
                        <h4>No Sale</h4>
                        <div class="babcloud-quick-action-flex">
                            <input type="text" id="no-sale-reason-<?php echo $device_id; ?>" placeholder="Reason (optional)">
                            <button class="babcloud-no-sale-btn" data-device-id="<?php echo $device_id; ?>">No Sale</button>
                        </div>
                    </div>
                </div>

                <?php if (!$bridge_active): ?>
                    </div>
                <?php endif; ?>
            </div>

            <!-- Main Content -->
            <div class="babcloud-fiscal-content">
                <?php if (!$bridge_active): ?>
                    <div style="opacity: 0.5; pointer-events: none;">
                <?php endif; ?>

                <!-- Today's Reports -->
                <h3 class="babcloud-section-title">Today's Reports</h3>
                <div class="babcloud-grid-2">
                    <!-- Z Report -->
                    <div class="babcloud-card babcloud-card-zreport">
                        <h3>Z Report (Today)</h3>
                        <p>Closes the fiscal day and prints the Z Report. Printer will only print if there are transactions.</p>
                        <button class="babcloud-btn babcloud-btn-primary babcloud-btn-large babcloud-zreport-btn" data-device-id="<?php echo $device_id; ?>">Close Fiscal Day - Z Report</button>
                    </div>

                    <!-- X Report -->
                    <div class="babcloud-card">
                        <h3>X Report (Today)</h3>
                        <p>Current shift status without closing the fiscal day.</p>
                        <button class="babcloud-btn babcloud-btn-secondary babcloud-xreport-btn" data-device-id="<?php echo $device_id; ?>">Print X Report</button>
                    </div>
                </div>

                <!-- Historical Reports -->
                <h3 class="babcloud-section-title">Historical Reports</h3>
                <div class="babcloud-grid-2">
                    <!-- Date Range -->
                    <div class="babcloud-card">
                        <h3>Z Reports by Date Range</h3>
                        <div class="babcloud-form-grid">
                            <div class="babcloud-form-group">
                                <label for="babcloud-start-date-<?php echo $device_id; ?>">From</label>
                                <input type="date" id="babcloud-start-date-<?php echo $device_id; ?>" value="<?php echo $yesterday; ?>" max="<?php echo date('Y-m-d'); ?>">
                            </div>
                            <div class="babcloud-form-group">
                                <label for="babcloud-end-date-<?php echo $device_id; ?>">To</label>
                                <input type="date" id="babcloud-end-date-<?php echo $device_id; ?>" value="<?php echo $yesterday; ?>" max="<?php echo date('Y-m-d'); ?>">
                            </div>
                        </div>
                        <button class="babcloud-btn babcloud-btn-primary babcloud-zreport-date-btn" data-device-id="<?php echo $device_id; ?>">Print Date Range</button>
                    </div>

                    <!-- Number Range -->
                    <div class="babcloud-card">
                        <h3>Z Reports by Number Range</h3>
                        <div class="babcloud-form-grid">
                            <div class="babcloud-form-group">
                                <label for="babcloud-from-z-<?php echo $device_id; ?>">Start #</label>
                                <input type="number" id="babcloud-from-z-<?php echo $device_id; ?>" placeholder="100" min="1">
                            </div>
                            <div class="babcloud-form-group">
                                <label for="babcloud-to-z-<?php echo $device_id; ?>">End #</label>
                                <input type="number" id="babcloud-to-z-<?php echo $device_id; ?>" placeholder="150" min="1">
                            </div>
                        </div>
                        <button class="babcloud-btn babcloud-btn-primary babcloud-zreport-range-btn" data-device-id="<?php echo $device_id; ?>">Print Number Range</button>
                    </div>
                </div>

                <?php if (!$bridge_active): ?>
                    </div>
                <?php endif; ?>
            </div>
        </div>
        <?php
        return ob_get_clean();
    }
}
