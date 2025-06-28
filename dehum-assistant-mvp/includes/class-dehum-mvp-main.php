<?php
// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Main Controller Class for Dehumidifier Assistant MVP.
 *
 * Orchestrates the loading of all other classes and fires the
 * primary plugin hooks.
 */
final class Dehum_MVP_Main {

    /**
     * The single instance of the class.
     * @var Dehum_MVP_Main
     */
    private static $instance = null;

    /**
     * @var Dehum_MVP_Database
     */
    public $database;

    /**
     * @var Dehum_MVP_Admin
     */
    public $admin;

    /**
     * @var Dehum_MVP_Frontend
     */
    public $frontend;

    /**
     * @var Dehum_MVP_Ajax
     */
    public $ajax;

    /**
     * Main Manager Instance.
     *
     * Ensures only one instance of the manager is loaded or can be loaded.
     *
     * @static
     * @return Dehum_MVP_Main - Main instance.
     */
    public static function instance() {
        if (is_null(self::$instance)) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    /**
     * Constructor.
     */
    private function __construct() {
        $this->includes();
        
        // Core components that must be loaded immediately
        $this->database = new Dehum_MVP_Database();
        $this->ajax = new Dehum_MVP_Ajax($this->database);  // Always load AJAX handlers
        
        // Admin components must be loaded immediately to catch early hooks like 'admin_menu'.
        if (is_admin()) {
            $this->admin = new Dehum_MVP_Admin($this->database);
        }

        // Other components can be loaded on the 'init' hook.
        add_action('init', [$this, 'init_classes']);
    }

    /**
     * Include required files.
     */
    private function includes() {
        require_once DEHUM_MVP_PLUGIN_PATH . 'includes/class-dehum-mvp-database.php';
        require_once DEHUM_MVP_PLUGIN_PATH . 'includes/class-dehum-mvp-admin.php';
        require_once DEHUM_MVP_PLUGIN_PATH . 'includes/class-dehum-mvp-frontend.php';
        require_once DEHUM_MVP_PLUGIN_PATH . 'includes/class-dehum-mvp-ajax.php';
    }

    /**
     * Initialize the classes on the 'init' hook.
     */
    public function init_classes() {
        $this->frontend = new Dehum_MVP_Frontend();
        
        // General purpose init hook for things like textdomain
        load_plugin_textdomain('dehum-assistant-mvp', false, dirname(plugin_basename(DEHUM_MVP_PLUGIN_PATH)) . '/languages');
    }

    /**
     * Plugin activation hook.
     */
    public static function activate() {
        // We can't use constants here as they are not defined during activation.
        // We must build the path from this file's location.
        require_once plugin_dir_path(__FILE__) . 'class-dehum-mvp-database.php';
        
        $db = new Dehum_MVP_Database();
        $db->create_conversations_table();

        set_transient('dehum_mvp_activation_notice', true, 30);
        update_option('dehum_mvp_version', '2.3.0'); // Hardcode version on activation
        flush_rewrite_rules();
    }

    /**
     * Plugin deactivation hook.
     */
    public static function deactivate() {
        flush_rewrite_rules();
    }
} 