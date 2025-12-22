<?php
/**
 * BABCloud Authentication Class
 * Handles device token generation and validation
 */

if (!defined('ABSPATH')) {
    exit;
}

class BABCloud_Auth {

    /**
     * Initialize the authentication system
     */
    public static function init() {
        // No hooks needed yet, all methods are called directly
    }

    /**
     * Generate a new device token
     *
     * @param int $printer_id The printer post ID
     * @return string The generated token (64-char hex)
     */
    public static function generate_device_token($printer_id) {
        // Generate 32 random bytes = 64 hex characters
        $token = bin2hex(random_bytes(32));

        // Hash the token for storage
        $hash = hash('sha256', $token);

        // Store hash in printer meta
        update_post_meta($printer_id, '_device_token_hash', $hash);

        // Store generation timestamp
        update_post_meta($printer_id, '_token_generated_at', current_time('mysql'));

        // Return the token (this is the ONLY time it's visible)
        return $token;
    }

    /**
     * Validate a device token
     *
     * @param string $device_id The device ID
     * @param string $provided_token The token to validate
     * @return WP_Post|false The printer post object if valid, false otherwise
     */
    public static function validate_device_token($device_id, $provided_token) {
        // Get printer by device_id
        $printer = babcloud_get_printer_by_device_id($device_id);

        if (!$printer) {
            return false;
        }

        // Get stored token hash
        $stored_hash = get_post_meta($printer->ID, '_device_token_hash', true);

        if (empty($stored_hash)) {
            return false;
        }

        // Hash the provided token
        $provided_hash = hash('sha256', $provided_token);

        // Constant-time comparison to prevent timing attacks
        if (hash_equals($stored_hash, $provided_hash)) {
            return $printer;
        }

        return false;
    }

    /**
     * Regenerate device token
     *
     * @param int $printer_id The printer post ID
     * @return string The new token
     */
    public static function regenerate_device_token($printer_id) {
        // Delete old token
        delete_post_meta($printer_id, '_device_token_hash');
        delete_post_meta($printer_id, '_token_generated_at');

        // Generate new token
        return self::generate_device_token($printer_id);
    }

    /**
     * REST API permission callback for device endpoints
     *
     * @param WP_REST_Request $request The REST request
     * @return bool|WP_Error True if authorized, WP_Error otherwise
     */
    public static function check_device_permission($request) {
        // Get device_id from URL parameter
        $device_id = $request->get_param('device_id');

        if (empty($device_id)) {
            return new WP_Error(
                'missing_device_id',
                __('Device ID is required', 'babcloud'),
                array('status' => 400)
            );
        }

        // Get token from header
        $token = $request->get_header('X-Device-Token');

        if (empty($token)) {
            return new WP_Error(
                'missing_token',
                __('Device token is required', 'babcloud'),
                array('status' => 401)
            );
        }

        // Validate token
        $printer = self::validate_device_token($device_id, $token);

        if (!$printer) {
            return new WP_Error(
                'invalid_token',
                __('Invalid device token or device not found', 'babcloud'),
                array('status' => 401)
            );
        }

        // Rate limiting disabled for local development
        // TODO: Re-enable for production with appropriate limits
        // $rate_limit_key = 'babcloud_rate_limit_' . $device_id;
        // $request_count = get_transient($rate_limit_key);
        // if ($request_count !== false && $request_count >= 10) {
        //     return new WP_Error('rate_limit_exceeded', __('Rate limit exceeded.', 'babcloud'), array('status' => 429));
        // }
        // set_transient($rate_limit_key, ($request_count ?: 0) + 1, 5);

        // Store printer object in request for later use
        $request->set_param('_printer_object', $printer);

        return true;
    }

    /**
     * REST API permission callback for user endpoints (portal/shortcodes)
     *
     * @param WP_REST_Request $request The REST request
     * @return bool|WP_Error True if authorized, WP_Error otherwise
     */
    public static function check_user_permission($request) {
        // Check if user is logged in
        if (!is_user_logged_in()) {
            return new WP_Error(
                'not_logged_in',
                __('You must be logged in to perform this action', 'babcloud'),
                array('status' => 401)
            );
        }

        // Get device_id from URL parameter
        $device_id = $request->get_param('device_id');

        if (empty($device_id)) {
            return new WP_Error(
                'missing_device_id',
                __('Device ID is required', 'babcloud'),
                array('status' => 400)
            );
        }

        // Get printer by device_id
        $printer = babcloud_get_printer_by_device_id($device_id);

        if (!$printer) {
            return new WP_Error(
                'printer_not_found',
                __('Printer not found', 'babcloud'),
                array('status' => 404)
            );
        }

        // Check if user owns the printer
        $user_id = get_current_user_id();

        if (!babcloud_user_owns_printer($user_id, $printer->ID)) {
            return new WP_Error(
                'unauthorized',
                __('You do not have permission to access this printer', 'babcloud'),
                array('status' => 403)
            );
        }

        // Store printer object in request for later use
        $request->set_param('_printer_object', $printer);

        return true;
    }
}
