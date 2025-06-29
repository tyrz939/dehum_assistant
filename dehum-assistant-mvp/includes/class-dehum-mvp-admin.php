<?php
// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Class Dehum_MVP_Admin
 *
 * Handles all admin-area functionality for the plugin, including
 * settings, logs page, and dashboard widgets.
 */
class Dehum_MVP_Admin {

    /**
     * @var Dehum_MVP_Database
     */
    private $db;

    /**
     * Constructor.
     *
     * @param Dehum_MVP_Database $db The database handler instance.
     */
    public function __construct(Dehum_MVP_Database $db) {
        $this->db = $db;
        $this->add_admin_hooks();
    }

    /**
     * Add the WordPress admin hooks.
     */
    private function add_admin_hooks() {
        add_action('admin_enqueue_scripts', [$this, 'enqueue_assets']);
        add_action('admin_init', [$this, 'register_settings']);
        add_action('admin_menu', [$this, 'add_admin_menu']);
        add_action('admin_notices', [$this, 'admin_activation_notice']);
        add_action('wp_dashboard_setup', [$this, 'add_dashboard_widget']);
    }

    /**
     * Enqueue admin assets (CSS and JavaScript).
     *
     * @param string $hook The current admin page hook.
     */
    public function enqueue_assets($hook) {
        if ($hook !== 'tools_page_dehum-mvp-logs' && $hook !== 'index.php') {
            return;
        }

        wp_enqueue_style(
            'dehum-mvp-admin',
            DEHUM_MVP_PLUGIN_URL . 'assets/css/admin.css',
            [],
            DEHUM_MVP_VERSION
        );

        if ($hook === 'tools_page_dehum-mvp-logs') {
            wp_enqueue_script(
                'dehum-mvp-admin',
                DEHUM_MVP_PLUGIN_URL . 'assets/js/admin.js',
                ['jquery'],
                DEHUM_MVP_VERSION,
                true
            );

            wp_localize_script('dehum-mvp-admin', 'dehum_admin_vars', [
                'nonce' => wp_create_nonce(DEHUM_MVP_SESSION_NONCE)
            ]);
        }
    }
    
    /**
     * Register plugin settings.
     */
    public function register_settings() {
        register_setting('dehum_mvp_options_group', 'dehum_mvp_n8n_webhook_url', ['type' => 'string', 'sanitize_callback' => 'esc_url_raw']);
        register_setting('dehum_mvp_options_group', 'dehum_mvp_n8n_webhook_user', ['type' => 'string']);
        register_setting('dehum_mvp_options_group', 'dehum_mvp_n8n_webhook_pass', ['type' => 'string', 'sanitize_callback' => [$this, 'encrypt_password_callback']]);
    }

    /**
     * Sanitize and encrypt the webhook password.
     *
     * @param string $password The plain text password.
     * @return string Empty string (we store encrypted version separately).
     */
    public function encrypt_password_callback($password) {
        if (!empty($password)) {
            // Create AJAX instance to access encryption method
            $ajax = new Dehum_MVP_Ajax($this->db);
            $encrypted = $ajax->encrypt_credential($password);
            update_option('dehum_mvp_n8n_webhook_pass_encrypted', $encrypted);
        }
        // Always return empty string to prevent storing plain text
        return '';
    }
    
    /**
     * Add the admin menu item for the logs page.
     */
    public function add_admin_menu() {
        $stats = $this->db->get_stats();
        $today_count = $stats['today_messages'];
        
        $menu_title = __('Dehumidifier Logs', 'dehum-assistant-mvp');
        if ($today_count > 0) {
            $menu_title .= ' <span class="awaiting-mod"><span class="pending-count">' . number_format_i18n($today_count) . '</span></span>';
        }

        add_management_page(
            __('Dehumidifier Logs', 'dehum-assistant-mvp'),
            $menu_title,
            'manage_options',
            'dehum-mvp-logs',
            [$this, 'render_logs_page']
        );
    }
    
    /**
     * Display the admin notice on plugin activation.
     */
    public function admin_activation_notice() {
        if (get_transient('dehum_mvp_activation_notice')) {
            $webhook_url = get_option('dehum_mvp_n8n_webhook_url');
            $webhook_status = empty($webhook_url) 
                ? '<span style="color:red;">Action Required: n8n Webhook URL is not set.</span>' 
                : '<span style="color:green;">n8n Webhook URL is configured.</span>';

            ?>
            <div class="notice notice-success is-dismissible">
                <p>
                    <strong>Dehumidifier Assistant MVP is active!</strong>
                    The chat widget is now live on your site's frontend.
                    <a href="<?php echo admin_url('tools.php?page=dehum-mvp-logs'); ?>">View Conversation Logs</a>
                    <br><small><?php echo $webhook_status; ?></small>
                </p>
            </div>
            <?php
            delete_transient('dehum_mvp_activation_notice');
        }
    }

    /**
     * Add the dashboard widget.
     */
    public function add_dashboard_widget() {
        wp_add_dashboard_widget(
            'dehum_mvp_stats',
            __('Dehumidifier Assistant Activity', 'dehum-assistant-mvp'),
            [$this, 'render_dashboard_widget']
        );
    }

    /**
     * Render the content for the dashboard widget.
     */
    public function render_dashboard_widget() {
        $stats = $this->db->get_stats();
        require_once DEHUM_MVP_PLUGIN_PATH . 'includes/views/view-dashboard-widget.php';
    }

    /**
     * Render the main admin logs and settings page.
     */
    public function render_logs_page() {
        // Handle bulk actions and exports before rendering the page
        $this->handle_actions();

        $filters = [
            'search'       => isset($_GET['search']) ? sanitize_text_field($_GET['search']) : '',
            'date_filter'  => isset($_GET['date_filter']) ? sanitize_text_field($_GET['date_filter']) : '',
            'custom_start' => isset($_GET['custom_start']) ? sanitize_text_field($_GET['custom_start']) : '',
            'custom_end'   => isset($_GET['custom_end']) ? sanitize_text_field($_GET['custom_end']) : '',
            'per_page'     => isset($_GET['per_page']) ? intval($_GET['per_page']) : 20,
            'paged'        => isset($_GET['paged']) ? intval($_GET['paged']) : 1,
        ];

        $sessions = $this->db->get_sessions($filters);
        $total_sessions = $this->db->count_sessions($filters);
        $all_stats = $this->db->get_stats();

        require_once DEHUM_MVP_PLUGIN_PATH . 'includes/views/view-logs-page.php';
    }

    /**
     * Handle bulk actions and exports.
     */
    private function handle_actions() {
        // Handle bulk delete
        if (isset($_POST['bulk_action'], $_POST['bulk_nonce']) && wp_verify_nonce($_POST['bulk_nonce'], DEHUM_MVP_BULK_NONCE)) {
            if ($_POST['bulk_action'] === 'delete_old') {
                $deleted_count = $this->db->delete_old_conversations();
                // Add admin notice for feedback
            }
        }
        
        // Handle export
        if (isset($_GET['action'], $_GET['export_nonce']) && $_GET['action'] === 'export' && wp_verify_nonce($_GET['export_nonce'], DEHUM_MVP_EXPORT_NONCE)) {
            $this->db->export_conversations($_GET);
        }
    }
} 