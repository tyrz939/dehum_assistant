<?php
/**
 * Uninstall script for Dehumidifier Assistant MVP
 * 
 * This file is executed when the plugin is deleted (not just deactivated).
 * It removes all plugin data from the database to keep the WordPress installation clean.
 * 
 * @package DehumidifierAssistantMVP
 * @version 2.2.0
 */

// If uninstall not called from WordPress, then exit
if (!defined('WP_UNINSTALL_PLUGIN')) {
    exit;
}

// Security check - make sure we're in the right context
if (!current_user_can('activate_plugins')) {
    return;
}

// Get the plugin file path for additional security
$plugin = isset($_REQUEST['plugin']) ? $_REQUEST['plugin'] : '';
if ($plugin !== plugin_basename(__FILE__)) {
    return;
}

/**
 * Clean up database tables
 */
function dehum_mvp_cleanup_database() {
    global $wpdb;
    
    // Drop the conversations table
    $table_name = $wpdb->prefix . 'dehum_conversations';
    $wpdb->query("DROP TABLE IF EXISTS {$table_name}");
    
    // Log the cleanup for debugging (if WP_DEBUG is enabled)
    if (defined('WP_DEBUG') && WP_DEBUG) {
        error_log('Dehum MVP Uninstall: Dropped table ' . $table_name);
    }
}

/**
 * Clean up WordPress options
 */
function dehum_mvp_cleanup_options() {
    // Remove all plugin options
    $options_to_delete = [
        'dehum_mvp_activated_at',
        'dehum_mvp_version',
        'dehum_mvp_db_version',
        'dehum_mvp_n8n_webhook_url'
    ];
    
    foreach ($options_to_delete as $option) {
        delete_option($option);
    }
    
    // Log the cleanup for debugging (if WP_DEBUG is enabled)
    if (defined('WP_DEBUG') && WP_DEBUG) {
        error_log('Dehum MVP Uninstall: Deleted ' . count($options_to_delete) . ' plugin options');
    }
}

/**
 * Clean up transients (rate limiting data)
 */
function dehum_mvp_cleanup_transients() {
    global $wpdb;
    
    // Delete all rate limiting transients
    // These are stored with the pattern: dehum_mvp_rate_limit_[hash]
    $wpdb->query("
        DELETE FROM {$wpdb->options} 
        WHERE option_name LIKE '_transient_dehum_mvp_rate_limit_%' 
        OR option_name LIKE '_transient_timeout_dehum_mvp_rate_limit_%'
    ");
    
    // Log the cleanup for debugging (if WP_DEBUG is enabled)
    if (defined('WP_DEBUG') && WP_DEBUG) {
        error_log('Dehum MVP Uninstall: Cleaned up rate limiting transients');
    }
}

/**
 * Clean up user meta (if any were added in future versions)
 */
function dehum_mvp_cleanup_user_meta() {
    // Currently no user meta is stored, but this is here for future-proofing
    // If you add user preferences or settings in future versions, clean them up here
    
    // Example:
    // delete_metadata('user', 0, 'dehum_mvp_user_preference', '', true);
}

/**
 * Main uninstall routine
 */
function dehum_mvp_uninstall() {
    // Clean up database
    dehum_mvp_cleanup_database();
    
    // Clean up options
    dehum_mvp_cleanup_options();
    
    // Clean up transients
    dehum_mvp_cleanup_transients();
    
    // Clean up user meta
    dehum_mvp_cleanup_user_meta();
    
    // Clear any cached data
    wp_cache_flush();
    
    // Log successful uninstall
    if (defined('WP_DEBUG') && WP_DEBUG) {
        error_log('Dehum MVP: Plugin uninstalled successfully - all data removed');
    }
}

// Execute the uninstall
dehum_mvp_uninstall(); 