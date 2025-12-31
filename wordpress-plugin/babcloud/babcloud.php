<?php
/**
 * Plugin Name: BAB Cloud PrintHub
 * Plugin URI: https://babcloud.linux
 * Description: WordPress plugin for managing fiscal printers with REST API integration for BAB PrintHub devices
 * Version: 1.5.2
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
    // Note: Voxel already manages the 'printer' CPT, no need to register
    // Just flush rewrite rules to ensure REST API routes work
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

    // Disable Voxel frontend forms for printer CPT (read-only access)
    add_filter('voxel/post-types/printer/can-create-post', '__return_false');
    add_filter('voxel/post-types/printer/can-edit-post', function($can_edit, $post) {
        // Only admins can edit via Voxel
        return current_user_can('manage_options');
    }, 10, 2);
}
add_action('plugins_loaded', 'babcloud_init');

/**
 * Handle autologin via token
 */
function babcloud_handle_autologin() {
    if (isset($_GET['autologin_token'])) {
        $token = sanitize_text_field($_GET['autologin_token']);
        $transient_key = 'babcloud_autologin_' . $token;

        // Get user ID from transient
        $user_id = get_transient($transient_key);

        if ($user_id) {
            // Delete transient (single use)
            delete_transient($transient_key);

            // Log user in
            wp_set_current_user($user_id);
            wp_set_auth_cookie($user_id, false);

            // Redirect to my-printers without token in URL
            wp_redirect('/my-printers');
            exit;
        } else {
            // Token invalid or expired - redirect to login
            wp_redirect('/my-printers');
            exit;
        }
    }
}
add_action('init', 'babcloud_handle_autologin');

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
        'post_type' => 'printer',
        'posts_per_page' => 1,
        'meta_query' => array(
            array(
                'key' => 'device_id',
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

    if (!$printer || $printer->post_type !== 'printer') {
        return false;
    }

    // Admins can access all printers
    if (user_can($user_id, 'manage_options')) {
        return true;
    }

    // Check if user is the author
    return ($printer->post_author == $user_id);
}
