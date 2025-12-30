<?php
/**
 * BABCloud Custom Post Type - Printer
 * Handles printer CPT registration and meta fields
 */

if (!defined('ABSPATH')) {
    exit;
}

class BABCloud_CPT_Printer {

    /**
     * Initialize CPT
     * Note: We use the existing Voxel-managed 'printer' CPT, not creating our own
     */
    public static function init() {
        // Do NOT register the post type - Voxel already manages 'printer' CPT
        add_action('init', array(__CLASS__, 'register_meta_fields'));
        add_action('pre_get_posts', array(__CLASS__, 'filter_printer_queries'));
    }

    /**
     * Register meta fields for REST API access
     * Note: Field names WITHOUT underscore prefix to match Voxel field names
     */
    public static function register_meta_fields() {
        $meta_fields = array(
            'device_id',
            'device_label',
            'device_token_hash',
            'license_key',
            'license_expiry',
            'license_valid',
            'cloud_only',
            'cloud_grace_hours',
            'last_seen',
            'hub_version',
            'printer_model',
            'pending_command',
            'command_status',
            'command_result',
            'command_error',
            'last_zreport_at',
            'last_xreport_at',
            'token_generated_at',
        );

        foreach ($meta_fields as $field) {
            register_post_meta('printer', $field, array(
                'show_in_rest' => false,
                'single' => true,
                'type' => 'string',
                'auth_callback' => function() {
                    return current_user_can('edit_posts');
                }
            ));
        }
    }

    /**
     * Filter queries to show only user's own printers (for Voxel frontend access)
     * Admins see all printers, regular users see only their own
     */
    public static function filter_printer_queries($query) {
        // Only on frontend and for printer queries
        if (is_admin() || !$query->is_main_query()) {
            return;
        }

        if ($query->get('post_type') !== 'printer') {
            return;
        }

        // Admins can see all
        if (current_user_can('manage_options')) {
            return;
        }

        // Non-logged in users see nothing
        if (!is_user_logged_in()) {
            $query->set('post__in', array(0)); // Force no results
            return;
        }

        // Filter by current user as author
        $query->set('author', get_current_user_id());
    }
}
