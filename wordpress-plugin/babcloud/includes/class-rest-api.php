<?php
/**
 * BABCloud REST API Class
 * Handles all REST API endpoints for device and portal communication
 */

if (!defined('ABSPATH')) {
    exit;
}

class BABCloud_REST_API {

    const NAMESPACE = 'babcloud/v1';

    /**
     * Initialize REST API
     */
    public static function init() {
        add_action('rest_api_init', array(__CLASS__, 'register_routes'));
    }

    /**
     * Register all REST API routes
     */
    public static function register_routes() {
        // Device endpoints (authenticated with device token)

        // 1. Poll for pending commands
        register_rest_route(self::NAMESPACE, '/printer/(?P<device_id>[a-zA-Z0-9_-]+)/commands', array(
            'methods' => 'GET',
            'callback' => array(__CLASS__, 'get_pending_commands'),
            'permission_callback' => array('BABCloud_Auth', 'check_device_permission'),
            'args' => array(
                'device_id' => array(
                    'required' => true,
                    'type' => 'string',
                    'sanitize_callback' => 'sanitize_text_field',
                ),
            ),
        ));

        // 2. Report command completion
        register_rest_route(self::NAMESPACE, '/printer/(?P<device_id>[a-zA-Z0-9_-]+)/commands/complete', array(
            'methods' => 'POST',
            'callback' => array(__CLASS__, 'complete_command'),
            'permission_callback' => array('BABCloud_Auth', 'check_device_permission'),
            'args' => array(
                'device_id' => array(
                    'required' => true,
                    'type' => 'string',
                    'sanitize_callback' => 'sanitize_text_field',
                ),
                'command_id' => array(
                    'required' => false,
                    'type' => 'string',
                ),
                'status' => array(
                    'required' => false,
                    'type' => 'string',
                    'enum' => array('success', 'failed'),
                ),
                'result' => array(
                    'required' => false,
                    'type' => 'object',
                ),
                'error' => array(
                    'required' => false,
                    'type' => 'string',
                ),
            ),
        ));

        // 3. Device heartbeat
        register_rest_route(self::NAMESPACE, '/printer/(?P<device_id>[a-zA-Z0-9_-]+)/heartbeat', array(
            'methods' => 'POST',
            'callback' => array(__CLASS__, 'device_heartbeat'),
            'permission_callback' => array('BABCloud_Auth', 'check_device_permission'),
            'args' => array(
                'device_id' => array(
                    'required' => true,
                    'type' => 'string',
                    'sanitize_callback' => 'sanitize_text_field',
                ),
                'status' => array(
                    'required' => false,
                    'type' => 'string',
                ),
                'hub_version' => array(
                    'required' => false,
                    'type' => 'string',
                ),
                'printer_model' => array(
                    'required' => false,
                    'type' => 'string',
                ),
            ),
        ));

        // 4. License validation
        register_rest_route(self::NAMESPACE, '/printer/(?P<device_id>[a-zA-Z0-9_-]+)/license', array(
            'methods' => 'GET',
            'callback' => array(__CLASS__, 'check_license'),
            'permission_callback' => array('BABCloud_Auth', 'check_device_permission'),
            'args' => array(
                'device_id' => array(
                    'required' => true,
                    'type' => 'string',
                    'sanitize_callback' => 'sanitize_text_field',
                ),
            ),
        ));

        // Portal/User endpoints (authenticated with WordPress session)

        // 5-10. Trigger commands
        $trigger_endpoints = array(
            'zreport' => 'trigger_zreport',
            'xreport' => 'trigger_xreport',
            'print_check' => 'trigger_print_check',
            'zreport_range' => 'trigger_zreport_range',
            'zreport_date' => 'trigger_zreport_date',
            'no_sale' => 'trigger_no_sale',
        );

        foreach ($trigger_endpoints as $endpoint => $callback) {
            register_rest_route(self::NAMESPACE, '/printer/(?P<device_id>[a-zA-Z0-9_-]+)/trigger/' . $endpoint, array(
                'methods' => 'POST',
                'callback' => array(__CLASS__, $callback),
                'permission_callback' => array('BABCloud_Auth', 'check_user_permission'),
                'args' => array(
                    'device_id' => array(
                        'required' => true,
                        'type' => 'string',
                        'sanitize_callback' => 'sanitize_text_field',
                    ),
                ),
            ));
        }

        // 11. Check command status
        register_rest_route(self::NAMESPACE, '/printer/(?P<device_id>[a-zA-Z0-9_-]+)/command/(?P<command_id>[a-zA-Z0-9_-]+)/status', array(
            'methods' => 'GET',
            'callback' => array(__CLASS__, 'get_command_status'),
            'permission_callback' => array('BABCloud_Auth', 'check_user_permission'),
            'args' => array(
                'device_id' => array(
                    'required' => true,
                    'type' => 'string',
                    'sanitize_callback' => 'sanitize_text_field',
                ),
                'command_id' => array(
                    'required' => true,
                    'type' => 'string',
                    'sanitize_callback' => 'sanitize_text_field',
                ),
            ),
        ));

        // 12. Autologin token generation
        register_rest_route(self::NAMESPACE, '/autologin/generate-token', array(
            'methods' => 'POST',
            'callback' => array(__CLASS__, 'generate_autologin_token'),
            'permission_callback' => array(__CLASS__, 'check_app_password_auth'),
        ));
    }

    /**
     * Check Application Password authentication
     */
    public static function check_app_password_auth($request) {
        // WordPress automatically validates Application Passwords
        // via Basic Auth when is_user_logged_in() is called
        return is_user_logged_in();
    }

    /**
     * Generate single-use autologin token
     */
    public static function generate_autologin_token($request) {
        $user = wp_get_current_user();

        if (!$user || $user->ID === 0) {
            return new WP_Error(
                'not_authenticated',
                __('You must be logged in to generate an autologin token', 'babcloud'),
                array('status' => 401)
            );
        }

        // Generate random token
        $token = bin2hex(random_bytes(32));

        // Store token as transient (expires in 60 seconds)
        $transient_key = 'babcloud_autologin_' . $token;
        set_transient($transient_key, $user->ID, 60);

        return new WP_REST_Response(array(
            'success' => true,
            'token' => $token,
            'expires_in' => 60
        ), 200);
    }

    /**
     * Get pending commands for a device
     */
    public static function get_pending_commands($request) {
        $printer = $request->get_param('_printer_object');

        // Get pending command from meta
        $pending_command = get_post_meta($printer->ID, 'pending_command', true);

        if (empty($pending_command)) {
            return new WP_REST_Response(array(
                'has_command' => false,
            ), 200);
        }

        // Decode JSON command
        $command = json_decode($pending_command, true);

        if (!$command) {
            return new WP_REST_Response(array(
                'has_command' => false,
            ), 200);
        }

        return new WP_REST_Response(array(
            'has_command' => true,
            'command' => $command,
        ), 200);
    }

    /**
     * Complete a command
     */
    public static function complete_command($request) {
        $printer = $request->get_param('_printer_object');

        // Simple approach like clear-pending-command.php - just clear it
        // Clear pending command
        delete_post_meta($printer->ID, 'pending_command');
        update_post_meta($printer->ID, 'command_status', 'completed');

        return new WP_REST_Response(array(
            'success' => true,
            'message' => __('Command completion recorded', 'babcloud'),
        ), 200);
    }

    /**
     * Device heartbeat
     */
    public static function device_heartbeat($request) {
        $printer = $request->get_param('_printer_object');

        // Get params from JSON body
        $body = $request->get_json_params();
        if (empty($body)) {
            $body = $request->get_body_params();
        }

        $status = isset($body['status']) ? $body['status'] : $request->get_param('status');
        $hub_version = isset($body['hub_version']) ? $body['hub_version'] : $request->get_param('hub_version');
        $printer_model = isset($body['printer_model']) ? $body['printer_model'] : $request->get_param('printer_model');

        // Validate required parameters
        if (empty($status)) {
            return new WP_Error(
                'missing_status',
                __('status parameter is required', 'babcloud'),
                array('status' => 400)
            );
        }

        // Update last_seen timestamp
        update_post_meta($printer->ID, 'last_seen', current_time('mysql'));

        // Update hub version if provided
        if ($hub_version) {
            update_post_meta($printer->ID, 'hub_version', sanitize_text_field($hub_version));
        }

        // Update printer model if provided
        if ($printer_model) {
            update_post_meta($printer->ID, 'printer_model', sanitize_text_field($printer_model));
        }

        // Check license validity
        $license_expiry = get_post_meta($printer->ID, 'license_expiry', true);
        $license_valid = true;
        $days_remaining = null;

        if ($license_expiry) {
            $expiry_date = strtotime($license_expiry);
            $now = current_time('timestamp');

            if ($expiry_date < $now) {
                $license_valid = false;
            } else {
                $days_remaining = floor(($expiry_date - $now) / (60 * 60 * 24));
            }
        }

        update_post_meta($printer->ID, 'license_valid', $license_valid ? '1' : '0');

        return new WP_REST_Response(array(
            'acknowledged' => true,
            'license_valid' => $license_valid,
            'license_expiry' => $license_expiry,
            'days_remaining' => $days_remaining,
        ), 200);
    }

    /**
     * Check license validity
     */
    public static function check_license($request) {
        $printer = $request->get_param('_printer_object');

        $license_expiry = get_post_meta($printer->ID, 'license_expiry', true);
        $license_valid = true;
        $days_remaining = null;

        if ($license_expiry) {
            $expiry_date = strtotime($license_expiry);
            $now = current_time('timestamp');

            if ($expiry_date < $now) {
                $license_valid = false;
            } else {
                $days_remaining = floor(($expiry_date - $now) / (60 * 60 * 24));
            }
        }

        return new WP_REST_Response(array(
            'valid' => $license_valid,
            'expiry' => $license_expiry,
            'days_remaining' => $days_remaining,
        ), 200);
    }

    /**
     * Helper function to create a command
     */
    private static function create_command($printer, $command_type, $params = array()) {
        // Check if PrintHub bridge is online (heartbeat within last 3 minutes)
        $last_seen = get_post_meta($printer->ID, 'last_seen', true);

        if (empty($last_seen)) {
            return new WP_Error(
                'bridge_offline',
                __('PrintHub bridge has never connected. Please ensure the bridge is running and configured correctly.', 'babcloud'),
                array('status' => 503)
            );
        }

        $last_seen_time = strtotime($last_seen);
        $now = current_time('timestamp');
        $offline_seconds = $now - $last_seen_time;

        // Require bridge to be active within last 3 minutes (180 seconds)
        if ($offline_seconds > 180) {
            $offline_minutes = ceil($offline_seconds / 60);
            return new WP_Error(
                'bridge_offline',
                sprintf(
                    __('PrintHub bridge is offline (last seen %d minutes ago). Please ensure the bridge is running before sending commands.', 'babcloud'),
                    $offline_minutes
                ),
                array('status' => 503)
            );
        }

        // Check if there's already a pending command
        $existing_command = get_post_meta($printer->ID, 'pending_command', true);

        if (!empty($existing_command)) {
            // Decode the existing command to check its timestamp
            $command_data = json_decode($existing_command, true);

            if ($command_data && isset($command_data['timestamp'])) {
                $command_time = strtotime($command_data['timestamp']);
                $now = current_time('timestamp');
                $age_seconds = $now - $command_time;

                // Auto-clear commands older than 2 minutes (120 seconds)
                if ($age_seconds > 120) {
                    // Command has timed out - clear it
                    delete_post_meta($printer->ID, 'pending_command');
                    update_post_meta($printer->ID, 'command_status', 'timeout');
                    update_post_meta($printer->ID, 'command_error', 'Command timed out after 2 minutes without completion');

                    error_log("BABCloud: Cleared timed-out command (age: {$age_seconds}s) for printer {$printer->ID}");
                    // Continue to create new command below
                } else {
                    // Command is still fresh - reject new command
                    $remaining = 120 - $age_seconds;
                    return new WP_Error(
                        'command_pending',
                        sprintf(
                            __('A command is already pending. Please wait %d seconds for it to complete or timeout.', 'babcloud'),
                            $remaining
                        ),
                        array('status' => 409)
                    );
                }
            } else {
                // Invalid command format - clear it
                delete_post_meta($printer->ID, 'pending_command');
            }
        }

        // Generate command_id
        $command_id = time() . '-' . bin2hex(random_bytes(8));

        // Create command object
        $command = array(
            'command_id' => $command_id,
            'command_type' => $command_type,
            'params' => $params,
            'timestamp' => current_time('c'),
        );

        // Store command as pending
        update_post_meta($printer->ID, 'pending_command', json_encode($command));
        update_post_meta($printer->ID, 'command_status', 'pending');
        delete_post_meta($printer->ID, 'command_result');
        delete_post_meta($printer->ID, 'command_error');

        return array(
            'success' => true,
            'command_id' => $command_id,
            'message' => __('Command queued successfully', 'babcloud'),
        );
    }

    /**
     * Trigger Z-Report
     */
    public static function trigger_zreport($request) {
        $printer = $request->get_param('_printer_object');
        $result = self::create_command($printer, 'zreport');

        if (is_wp_error($result)) {
            return $result;
        }

        return new WP_REST_Response($result, 200);
    }

    /**
     * Trigger X-Report
     */
    public static function trigger_xreport($request) {
        $printer = $request->get_param('_printer_object');
        $result = self::create_command($printer, 'xreport');

        if (is_wp_error($result)) {
            return $result;
        }

        return new WP_REST_Response($result, 200);
    }

    /**
     * Trigger Print Check
     */
    public static function trigger_print_check($request) {
        $printer = $request->get_param('_printer_object');

        // Get params from JSON body
        $body = $request->get_json_params();
        $params = array();

        if (!empty($body) && isset($body['document_number'])) {
            $params['document_number'] = sanitize_text_field($body['document_number']);
        }

        $result = self::create_command($printer, 'print_check', $params);

        if (is_wp_error($result)) {
            return $result;
        }

        return new WP_REST_Response($result, 200);
    }

    /**
     * Trigger Z-Report Range
     */
    public static function trigger_zreport_range($request) {
        $printer = $request->get_param('_printer_object');
        $from_z = $request->get_param('from_z');
        $to_z = $request->get_param('to_z');

        if (empty($from_z) || empty($to_z)) {
            return new WP_Error(
                'missing_params',
                __('from_z and to_z parameters are required', 'babcloud'),
                array('status' => 400)
            );
        }

        $result = self::create_command($printer, 'zreport_range', array(
            'from_z' => intval($from_z),
            'to_z' => intval($to_z),
        ));

        if (is_wp_error($result)) {
            return $result;
        }

        return new WP_REST_Response($result, 200);
    }

    /**
     * Trigger Z-Report by Date
     */
    public static function trigger_zreport_date($request) {
        $printer = $request->get_param('_printer_object');

        // Get params from JSON body
        $body = $request->get_json_params();
        if (empty($body)) {
            $body = $request->get_body_params();
        }

        $start_date = isset($body['start_date']) ? $body['start_date'] : $request->get_param('start_date');
        $end_date = isset($body['end_date']) ? $body['end_date'] : $request->get_param('end_date');

        if (empty($start_date)) {
            return new WP_Error(
                'missing_params',
                __('start_date parameter is required (format: YYYY-MM-DD)', 'babcloud'),
                array('status' => 400)
            );
        }

        $params = array('start_date' => sanitize_text_field($start_date));

        if (!empty($end_date)) {
            $params['end_date'] = sanitize_text_field($end_date);
        }

        $result = self::create_command($printer, 'zreport_date', $params);

        if (is_wp_error($result)) {
            return $result;
        }

        return new WP_REST_Response($result, 200);
    }

    /**
     * Trigger No Sale (open cash drawer)
     */
    public static function trigger_no_sale($request) {
        $printer = $request->get_param('_printer_object');

        // Get params from JSON body
        $body = $request->get_json_params();
        $params = array();

        if (!empty($body) && isset($body['reason'])) {
            $params['reason'] = sanitize_text_field($body['reason']);
        }

        $result = self::create_command($printer, 'no_sale', $params);

        if (is_wp_error($result)) {
            return $result;
        }

        return new WP_REST_Response($result, 200);
    }

    /**
     * Get command status
     */
    public static function get_command_status($request) {
        $printer = $request->get_param('_printer_object');
        $command_id = $request->get_param('command_id');

        // Get pending command
        $pending_command = get_post_meta($printer->ID, 'pending_command', true);

        if (!empty($pending_command)) {
            $command = json_decode($pending_command, true);

            if ($command && $command['command_id'] === $command_id) {
                return new WP_REST_Response(array(
                    'status' => 'pending',
                    'result' => null,
                    'error' => null,
                ), 200);
            }
        }

        // Check completed/failed status
        $status = get_post_meta($printer->ID, 'command_status', true);
        $result = get_post_meta($printer->ID, 'command_result', true);
        $error = get_post_meta($printer->ID, 'command_error', true);

        if ($result) {
            $result = json_decode($result, true);
        }

        return new WP_REST_Response(array(
            'status' => $status ?: 'unknown',
            'result' => $result,
            'error' => $error,
        ), 200);
    }
}
