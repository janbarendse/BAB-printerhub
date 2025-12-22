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
     */
    public static function init() {
        add_action('init', array(__CLASS__, 'register'));
        add_action('init', array(__CLASS__, 'register_meta_fields'));
    }

    /**
     * Register the printer post type
     */
    public static function register() {
        $labels = array(
            'name' => __('Printers', 'babcloud'),
            'singular_name' => __('Printer', 'babcloud'),
            'menu_name' => __('Printers', 'babcloud'),
            'add_new' => __('Add New', 'babcloud'),
            'add_new_item' => __('Add New Printer', 'babcloud'),
            'edit_item' => __('Edit Printer', 'babcloud'),
            'new_item' => __('New Printer', 'babcloud'),
            'view_item' => __('View Printer', 'babcloud'),
            'search_items' => __('Search Printers', 'babcloud'),
            'not_found' => __('No printers found', 'babcloud'),
            'not_found_in_trash' => __('No printers found in trash', 'babcloud'),
        );

        $args = array(
            'labels' => $labels,
            'public' => false,
            'show_ui' => true,
            'show_in_menu' => false, // We'll add custom menu
            'show_in_rest' => false,
            'has_archive' => false,
            'hierarchical' => false,
            'supports' => array('title', 'author'),
            'capability_type' => 'post',
            'map_meta_cap' => true,
        );

        register_post_type('babcloud_printer', $args);
    }

    /**
     * Register meta fields for REST API access
     */
    public static function register_meta_fields() {
        $meta_fields = array(
            '_device_id',
            '_device_label',
            '_device_token_hash',
            '_license_key',
            '_license_expiry',
            '_license_valid',
            '_last_seen',
            '_hub_version',
            '_printer_model',
            '_pending_command',
            '_command_status',
            '_command_result',
            '_command_error',
            '_last_zreport_at',
            '_last_xreport_at',
            '_token_generated_at',
        );

        foreach ($meta_fields as $field) {
            register_post_meta('babcloud_printer', $field, array(
                'show_in_rest' => false,
                'single' => true,
                'type' => 'string',
                'auth_callback' => function() {
                    return current_user_can('edit_posts');
                }
            ));
        }
    }
}
