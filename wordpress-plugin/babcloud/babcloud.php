<?php
/**
 * Plugin Name: BAB Cloud PrintHub
 * Plugin URI: https://babcloud.linux
 * Description: WordPress plugin for managing fiscal printers with REST API integration for BAB PrintHub devices
 * Version: 2.0.0
 * Author: BAB Cloud
 * Author URI: https://babcloud.linux
 * License: GPL v2 or later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain: babcloud
 * Domain Path: /languages
 */

// Exit if accessed directly
if (!defined('ABSPATH')) {
    exit;
}

// Plugin constants
define('BABCLOUD_VERSION', '2.0.0');
define('BABCLOUD_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('BABCLOUD_PLUGIN_URL', plugin_dir_url(__FILE__));
define('BABCLOUD_PLUGIN_FILE', __FILE__);

/**
 * Plugin activation hook
 */
function babcloud_activate() {
    // Register CPT
    require_once BABCLOUD_PLUGIN_DIR . 'includes/class-cpt-printer.php';
    BABCloud_CPT_Printer::register();

    // Flush rewrite rules
    flush_rewrite_rules();

    // Create default capabilities if needed
    $admin_role = get_role('administrator');
    if ($admin_role) {
        $admin_role->add_cap('manage_printers');
        $admin_role->add_cap('edit_printers');
        $admin_role->add_cap('delete_printers');
    }
}
register_activation_hook(__FILE__, 'babcloud_activate');

/**
 * Plugin deactivation hook
 */
function babcloud_deactivate() {
    // Flush rewrite rules
    flush_rewrite_rules();
}
register_deactivation_hook(__FILE__, 'babcloud_deactivate');

/**
 * Initialize plugin
 */
function babcloud_init() {
    // Load text domain for translations
    load_plugin_textdomain('babcloud', false, dirname(plugin_basename(__FILE__)) . '/languages');

    // Load includes
    require_once BABCLOUD_PLUGIN_DIR . 'includes/class-cpt-printer.php';
    require_once BABCLOUD_PLUGIN_DIR . 'includes/class-auth.php';
    require_once BABCLOUD_PLUGIN_DIR . 'includes/class-rest-api.php';
    require_once BABCLOUD_PLUGIN_DIR . 'includes/class-shortcodes.php';
    require_once BABCLOUD_PLUGIN_DIR . 'includes/class-admin-ui.php';

    // Initialize components
    BABCloud_CPT_Printer::init();
    BABCloud_Auth::init();
    BABCloud_REST_API::init();
    BABCloud_Shortcodes::init();
    BABCloud_Admin_UI::init();
}
add_action('plugins_loaded', 'babcloud_init');

/**
 * Add settings link on plugin page
 */
function babcloud_add_settings_link($links) {
    $settings_link = '<a href="' . admin_url('admin.php?page=babcloud-printers') . '">' . __('Settings', 'babcloud') . '</a>';
    array_unshift($links, $settings_link);
    return $links;
}
add_filter('plugin_action_links_' . plugin_basename(__FILE__), 'babcloud_add_settings_link');

/**
 * Helper function to get printer by device_id
 */
function babcloud_get_printer_by_device_id($device_id) {
    $args = array(
        'post_type' => 'babcloud_printer',
        'posts_per_page' => 1,
        'meta_query' => array(
            array(
                'key' => '_device_id',
                'value' => sanitize_text_field($device_id),
                'compare' => '='
            )
        )
    );

    $query = new WP_Query($args);

    if ($query->have_posts()) {
        return $query->posts[0];
    }

    return null;
}

/**
 * Helper function to check if user owns printer
 */
function babcloud_user_owns_printer($user_id, $printer_id) {
    $printer = get_post($printer_id);

    if (!$printer || $printer->post_type !== 'babcloud_printer') {
        return false;
    }

    // Admins can access all printers
    if (user_can($user_id, 'manage_options')) {
        return true;
    }

    // Check if user is the author
    return ($printer->post_author == $user_id);
}
