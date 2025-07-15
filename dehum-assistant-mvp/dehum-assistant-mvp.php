<?php
/**
 * Plugin Name: Dehumidifier Assistant MVP
 * Plugin URI: https://github.com/your-username/dehum-assistant
 * Description: Complete dehumidifier assistant with responsive chat widget, Python AI service integration, admin interface, and conversation logging
 * Version: 2.4.1
 * Author: Your Name
 * License: MIT
 * Text Domain: dehum-assistant-mvp
 * 
 * GitHub Plugin URI: tyrz939/dehum_assistant
 * GitHub Branch: main
 * Requires WP: 5.0
 * Tested up to: 6.4
 * Requires PHP: 7.4
 * 
 * ====================================================================
 * COMPLETE FRONTEND + BACKEND SOLUTION
 * ====================================================================
 * 
 * What's INCLUDED:
 * ✅ Responsive frontend chat widget (mobile fullscreen, desktop floating)
 * ✅ Python AI service integration with OpenAI function calling
 * ✅ Backward compatible n8n webhook support (legacy)
 * ✅ Admin interface (Tools → Dehumidifier Logs) 
 * ✅ Conversation database logging & session management
 * ✅ Rate limiting & security features
 * ✅ AJAX handlers for full chat functionality
 * ✅ Export, search, pagination, bulk actions
 * ✅ Mobile-first responsive design
 * ✅ Accessibility features (ARIA labels, keyboard navigation)
 * ✅ GitHub Updater support for automatic updates
 * ✅ Encrypted credential storage for API keys
 * 
 * FEATURES:
 * 🎯 Mobile: Full-screen chat experience
 * 🎯 Desktop: Floating 480x700px widget  
 * 🎯 Smart positioning and animations
 * 🎯 Session persistence and conversation threading
 * 🎯 Professional admin interface with natural conversation flow
 * 🎯 Automatic updates from GitHub repository
 * ====================================================================
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Plugin Constants
define('DEHUM_MVP_VERSION', '2.4.1');
define('DEHUM_MVP_PLUGIN_PATH', plugin_dir_path(__FILE__));
define('DEHUM_MVP_PLUGIN_URL', plugin_dir_url(__FILE__));

// Rate limiting and security constants
define('DEHUM_MVP_DAILY_MESSAGE_LIMIT', 50);
define('DEHUM_MVP_MESSAGE_MAX_LENGTH', 1200);
define('DEHUM_MVP_WEBHOOK_TIMEOUT', 30);
define('DEHUM_MVP_ACTIVATION_NOTICE_DURATION', 30);

// Database and cleanup constants
define('DEHUM_MVP_OLD_CONVERSATIONS_DAYS', 90);
define('DEHUM_MVP_DEFAULT_PER_PAGE', 20);

// AJAX action constants
define('DEHUM_MVP_AJAX_CHAT', 'dehum_mvp_chat');
define('DEHUM_MVP_AJAX_SESSION_DETAILS', 'dehum_mvp_get_session_details');

// Nonce action constants
define('DEHUM_MVP_CHAT_NONCE', 'dehum_mvp_chat_nonce');
define('DEHUM_MVP_SESSION_NONCE', 'dehum_session_details');
define('DEHUM_MVP_DELETE_SESSION_NONCE', 'dehum_delete_session');
define('DEHUM_MVP_BULK_NONCE', 'dehum_bulk_actions');
define('DEHUM_MVP_EXPORT_NONCE', 'dehum_export');

// Include the main plugin class
require_once DEHUM_MVP_PLUGIN_PATH . 'includes/class-dehum-mvp-main.php';

// Include the updater class
require_once DEHUM_MVP_PLUGIN_PATH . 'includes/class-dehum-mvp-updater.php';

/**
 * Register activation and deactivation hooks.
 */
register_activation_hook(__FILE__, ['Dehum_MVP_Main', 'activate']);
register_deactivation_hook(__FILE__, ['Dehum_MVP_Main', 'deactivate']);

/**
 * Begins execution of the plugin.
 *
 * Since everything within the plugin is registered via hooks,
 * kicking off the plugin from this point in the file does
 * not affect the page life cycle.
 *
 * @since    2.3.0
 */
function run_dehum_mvp() {
    // Initialize main plugin
    $main = Dehum_MVP_Main::instance();
    
    // Initialize updater for tyrz939/dehum_assistant repository
    new Dehum_MVP_Updater(__FILE__, 'tyrz939/dehum_assistant');
    
    return $main;
}
run_dehum_mvp(); 
