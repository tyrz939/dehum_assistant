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
        
        // Run maintenance tasks
        $this->run_maintenance_tasks();
        
        // Admin components must be loaded immediately to catch early hooks like 'admin_menu'.
        if (is_admin()) {
            $this->admin = new Dehum_MVP_Admin($this->database);
        }

        // Other components can be loaded on the 'init' hook.
        add_action('init', [$this, 'init_classes']);

        // Ensure translations are available as early as possible
        add_action('plugins_loaded', [$this, 'load_textdomain']);
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
    }

    /**
     * Load plugin translations.
     * Runs on plugins_loaded for early availability.
     */
    public function load_textdomain() {
        load_plugin_textdomain('dehum-assistant-mvp', false, dirname(plugin_basename(DEHUM_MVP_PLUGIN_PATH)) . '/languages');
    }

    /**
     * Plugin activation hook.
     */
    public static function activate() {
        // Validate constants are available, fallback to file-based path
        $plugin_path = defined('DEHUM_MVP_PLUGIN_PATH') ? DEHUM_MVP_PLUGIN_PATH : plugin_dir_path(dirname(__FILE__));
        $db_file = $plugin_path . 'includes/class-dehum-mvp-database.php';
        
        if (!file_exists($db_file)) {
            wp_die('Dehumidifier Assistant: Required database class file not found during activation.');
        }
        
        require_once $db_file;
        
        $db = new Dehum_MVP_Database();
        $db->ensure_table_exists();

        set_transient('dehum_mvp_activation_notice', true, DEHUM_MVP_ACTIVATION_NOTICE_DURATION);
        update_option('dehum_mvp_version', defined('DEHUM_MVP_VERSION') ? DEHUM_MVP_VERSION : '2.3.0');
        flush_rewrite_rules();
    }

    /**
     * Plugin deactivation hook.
     */
    public static function deactivate() {
        flush_rewrite_rules();
    }

    /**
     * Run maintenance tasks like credential migration and database upgrades.
     */
    private function run_maintenance_tasks() {
        // Migrate credentials if needed
        Dehum_MVP_Ajax::migrate_credentials();
        
        // Check for database upgrades
        $this->database->ensure_table_exists();
    }
} 