<?php
/**
 * Plugin Name: Dehumidifier Assistant MVP
 * Plugin URI: https://github.com/your-username/dehum-assistant
 * Description: Complete dehumidifier assistant with responsive chat widget, n8n AI integration, admin interface, and conversation logging
 * Version: 2.3.0
 * Author: Your Name
 * License: MIT
 * Text Domain: dehum-assistant-mvp
 * 
 * ====================================================================
 * COMPLETE FRONTEND + BACKEND SOLUTION
 * ====================================================================
 * 
 * What's INCLUDED:
 * ✅ Responsive frontend chat widget (mobile fullscreen, desktop floating)
 * ✅ n8n webhook integration & AI processing
 * ✅ Admin interface (Tools → Dehumidifier Logs) 
 * ✅ Conversation database logging & session management
 * ✅ Rate limiting & security features
 * ✅ AJAX handlers for full chat functionality
 * ✅ Export, search, pagination, bulk actions
 * ✅ Mobile-first responsive design
 * ✅ Accessibility features (ARIA labels, keyboard navigation)
 * 
 * FEATURES:
 * 🎯 Mobile: Full-screen chat experience
 * 🎯 Desktop: Floating 350x500px widget  
 * 🎯 Smart positioning and animations
 * 🎯 Session persistence and conversation threading
 * ====================================================================
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Define Plugin Constants
define('DEHUM_MVP_VERSION', '2.3.0');
define('DEHUM_MVP_PLUGIN_PATH', plugin_dir_path(__FILE__));
define('DEHUM_MVP_PLUGIN_URL', plugin_dir_url(__FILE__));
define('DEHUM_MVP_DAILY_MESSAGE_LIMIT', 50);

// Include the main plugin class
require_once DEHUM_MVP_PLUGIN_PATH . 'includes/class-dehum-mvp-main.php';

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
    return Dehum_MVP_Main::instance();
}
run_dehum_mvp(); 