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
        add_action('admin_init', [$this, 'handle_export_download']);
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
                'nonce' => wp_create_nonce(DEHUM_MVP_SESSION_NONCE),
                'delete_nonce' => wp_create_nonce(DEHUM_MVP_DELETE_SESSION_NONCE),
                'ajaxurl' => admin_url('admin-ajax.php')
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
            'ip_filter'    => isset($_GET['ip_filter']) ? sanitize_text_field($_GET['ip_filter']) : '',
            'per_page'     => isset($_GET['per_page']) ? intval($_GET['per_page']) : 20,
            'paged'        => isset($_GET['paged']) ? intval($_GET['paged']) : 1,
        ];

        $sessions = $this->db->get_sessions($filters);
        $total_sessions = $this->db->count_sessions($filters);
        $all_stats = $this->db->get_stats();

        require_once DEHUM_MVP_PLUGIN_PATH . 'includes/views/view-logs-page.php';
    }

    /**
     * Handle CSV export download on admin_init.
     */
    public function handle_export_download() {
        // Only handle export if we're on the right page and have the right parameters
        if (!isset($_GET['page']) || $_GET['page'] !== 'dehum-mvp-logs') {
            return;
        }
        
        if (!isset($_GET['action']) || $_GET['action'] !== 'export') {
            return;
        }
        
        if (!isset($_GET['export_nonce']) || !wp_verify_nonce($_GET['export_nonce'], DEHUM_MVP_EXPORT_NONCE)) {
            wp_die('Security check failed.');
        }
        
        if (!current_user_can('manage_options')) {
            wp_die('Insufficient permissions.');
        }
        
        // Remove pagination and action params from filters
        $export_filters = $_GET;
        unset($export_filters['action'], $export_filters['export_nonce'], $export_filters['paged'], $export_filters['page']);
        
        $this->export_conversations_direct($export_filters);
    }

    /**
     * Export conversations directly with proper headers.
     */
    private function export_conversations_direct($filters = []) {
        global $wpdb;
        $table_name = $this->db->get_conversations_table_name();
        
        list($where_clause, $where_params) = $this->db->build_where_clause($filters);
        
        $query = "SELECT * FROM $table_name $where_clause ORDER BY timestamp DESC";

        if (!empty($where_params)) {
            $conversations = $wpdb->get_results($wpdb->prepare($query, $where_params));
        } else {
            $conversations = $wpdb->get_results($query);
        }

        // Generate filename
        $filename = 'dehumidifier-conversations-' . date('Y-m-d-H-i-s') . '.csv';
        
        // Set headers for download - must be done before any output
        status_header(200);
        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="' . $filename . '"');
        header('Cache-Control: no-cache, must-revalidate');
        header('Expires: 0');
        header('Pragma: no-cache');
        
        // Disable WordPress's default headers
        remove_action('wp_head', 'wp_generator');
        
        // Output UTF-8 BOM for Excel
        echo chr(239) . chr(187) . chr(191);
        
        // Output CSV headers
        $headers = [
            'Session ID', 
            'Date/Time', 
            'User Message', 
            'AI Response', 
            'User IP',
            'Message Length',
            'Response Length'
        ];
        
        echo '"' . implode('","', $headers) . '"' . "\r\n";
        
        // Output data rows
        foreach ($conversations as $conv) {
            $row = [
                $conv->session_id,
                $conv->timestamp,
                str_replace('"', '""', $conv->message), // Escape quotes
                str_replace('"', '""', $conv->response), // Escape quotes
                $conv->user_ip,
                strlen($conv->message),
                strlen($conv->response)
            ];
            
            echo '"' . implode('","', $row) . '"' . "\r\n";
        }
        
        // Clean exit
        exit;
    }

    /**
     * Handle bulk actions and exports.
     */
    private function handle_actions() {
        // Handle individual session delete via AJAX (handled in AJAX class)
        
        // Handle bulk actions
        if (isset($_POST['bulk_action'], $_POST['bulk_nonce']) && wp_verify_nonce($_POST['bulk_nonce'], DEHUM_MVP_BULK_NONCE)) {
            $action = $_POST['bulk_action'];
            $success_message = '';
            $error_message = '';
            
            switch ($action) {
                case 'delete_old':
                    $deleted_count = $this->db->delete_old_conversations();
                    if ($deleted_count !== false) {
                        $success_message = sprintf(__('Successfully deleted %d old conversations.', 'dehum-assistant-mvp'), $deleted_count);
                    } else {
                        $error_message = __('Failed to delete old conversations.', 'dehum-assistant-mvp');
                    }
                    break;
                    
                case 'delete_selected':
                    if (isset($_POST['selected_sessions']) && is_array($_POST['selected_sessions'])) {
                        $session_ids = array_map('sanitize_text_field', $_POST['selected_sessions']);
                        $deleted_count = $this->db->delete_sessions_bulk($session_ids);
                        if ($deleted_count !== false) {
                            $success_message = sprintf(__('Successfully deleted %d selected conversations.', 'dehum-assistant-mvp'), count($session_ids));
                        } else {
                            $error_message = __('Failed to delete selected conversations.', 'dehum-assistant-mvp');
                        }
                    }
                    break;
                    
                case 'delete_by_date':
                    if (isset($_POST['delete_start_date'], $_POST['delete_end_date'])) {
                        $start_date = sanitize_text_field($_POST['delete_start_date']);
                        $end_date = sanitize_text_field($_POST['delete_end_date']);
                        if ($start_date && $end_date) {
                            $deleted_count = $this->db->delete_by_date_range($start_date, $end_date);
                            if ($deleted_count !== false) {
                                $success_message = sprintf(__('Successfully deleted %d conversations from %s to %s.', 'dehum-assistant-mvp'), $deleted_count, $start_date, $end_date);
                            } else {
                                $error_message = __('Failed to delete conversations by date range.', 'dehum-assistant-mvp');
                            }
                        }
                    }
                    break;
                    
                case 'delete_by_ip':
                    if (isset($_POST['delete_ip'])) {
                        $ip_address = sanitize_text_field($_POST['delete_ip']);
                        if ($ip_address) {
                            $deleted_count = $this->db->delete_by_ip($ip_address);
                            if ($deleted_count !== false) {
                                $success_message = sprintf(__('Successfully deleted %d conversations from IP %s.', 'dehum-assistant-mvp'), $deleted_count, $ip_address);
                            } else {
                                $error_message = __('Failed to delete conversations by IP address.', 'dehum-assistant-mvp');
                            }
                        }
                    }
                    break;
            }
            
            // Store messages in transients for display
            if ($success_message) {
                set_transient('dehum_admin_success', $success_message, 30);
            }
            if ($error_message) {
                set_transient('dehum_admin_error', $error_message, 30);
            }
            
            // Redirect to prevent resubmission
            wp_redirect(admin_url('tools.php?page=dehum-mvp-logs'));
            exit;
        }
        
        // Export is now handled in admin_init hook
    }
} 