<?php
/**
 * Admin page to test shortcodes
 * Accessed via: WordPress Admin > BAB Cloud > Test Shortcodes
 */

if (!defined('ABSPATH')) {
    exit;
}

// Check user permissions
if (!current_user_can('manage_options')) {
    wp_die(__('You do not have sufficient permissions to access this page.'));
}
?>

<div class="wrap">
    <h1><?php echo esc_html(get_admin_page_title()); ?></h1>

    <div class="notice notice-info">
        <p><strong>Device ID:</strong> printer-001 | <strong>Printer:</strong> Chichi Punda POS Printer</p>
    </div>

    <style>
        .shortcode-test-section {
            background: #fff;
            border: 1px solid #ccd0d4;
            border-radius: 4px;
            padding: 20px;
            margin: 20px 0;
        }
        .shortcode-test-section h2 {
            margin-top: 0;
            border-bottom: 1px solid #ccd0d4;
            padding-bottom: 10px;
        }
        .shortcode-code {
            background: #f0f0f1;
            padding: 10px;
            border-left: 4px solid #0073aa;
            margin: 10px 0;
            font-family: monospace;
        }
    </style>

    <!-- X-Report -->
    <div class="shortcode-test-section">
        <h2>1. X-Report (Non-Fiscal)</h2>
        <div class="shortcode-code">[babcloud_xreport device_id="printer-001"]</div>
        <?php echo do_shortcode('[babcloud_xreport device_id="printer-001"]'); ?>
    </div>

    <!-- Print Check -->
    <div class="shortcode-test-section">
        <h2>2. Print Check (Printer Test)</h2>
        <div class="shortcode-code">[babcloud_print_check device_id="printer-001"]</div>
        <?php echo do_shortcode('[babcloud_print_check device_id="printer-001"]'); ?>
    </div>

    <!-- No Sale -->
    <div class="shortcode-test-section">
        <h2>3. No Sale (Open Cash Drawer)</h2>
        <div class="shortcode-code">[babcloud_no_sale device_id="printer-001"]</div>
        <?php echo do_shortcode('[babcloud_no_sale device_id="printer-001"]'); ?>
    </div>

    <!-- Z-Report Range -->
    <div class="shortcode-test-section">
        <h2>4. Z-Report Range</h2>
        <div class="shortcode-code">[babcloud_zreport_range device_id="printer-001"]</div>
        <?php echo do_shortcode('[babcloud_zreport_range device_id="printer-001"]'); ?>
    </div>

    <!-- Z-Report Date -->
    <div class="shortcode-test-section">
        <h2>5. Z-Report by Date</h2>
        <div class="shortcode-code">[babcloud_zreport_date device_id="printer-001"]</div>
        <?php echo do_shortcode('[babcloud_zreport_date device_id="printer-001"]'); ?>
    </div>

    <!-- Z-Report Now -->
    <div class="shortcode-test-section" style="border-color: #d63638;">
        <h2 style="color: #d63638;">⚠️ 6. Z-Report Now (Fiscal Day Close)</h2>
        <p style="color: #d63638;"><strong>WARNING:</strong> This closes the fiscal day. Cannot be undone!</p>
        <div class="shortcode-code">[babcloud_zreport device_id="printer-001"]</div>
        <?php echo do_shortcode('[babcloud_zreport device_id="printer-001"]'); ?>
    </div>

</div>
