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
        // Main settings/logs page
        add_action('admin_menu', [$this, 'add_admin_menu']);
        add_action('admin_init', [$this, 'register_settings']);
        
        // Admin assets
        add_action('admin_enqueue_scripts', [$this, 'enqueue_assets']);
        
        // Dashboard widget
        add_action('wp_dashboard_setup', [$this, 'add_dashboard_widget']);
        
        // Admin notices
        add_action('admin_notices', [$this, 'admin_activation_notice']);
        add_action('admin_notices', [$this, 'rate_reset_notice']);

        // Form/action handlers
        add_action('admin_post_dehum_mvp_rotate_key', [$this, 'handle_rotate_key']);
        add_action('admin_post_dehum_reset_rate', [$this, 'handle_rate_reset']);
        add_action('admin_init', [$this, 'handle_export_download']);
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

        // Prefer local icon font; fallback to Google CDN if the woff2 file is missing
        $local_font = DEHUM_MVP_PLUGIN_PATH . 'assets/fonts/MaterialSymbolsOutlined.woff2';
        if (file_exists($local_font)) {
            wp_enqueue_style(
                'dehum-mvp-material-symbols',
                DEHUM_MVP_PLUGIN_URL . 'assets/css/material-symbols.css',
                [],
                DEHUM_MVP_VERSION
            );
        } else {
            // Fallback – restores icon immediately until site owner adds local font file
            wp_enqueue_style(
                'dehum-mvp-material-symbols',
                'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined',
                [],
                null
            );
        }

        // Inject same theme variables for admin area
        $theme_css = ':root {
  --background: #ffffff;
  --foreground: #1e1e1e;
  --card: #ffffff;
  --card-foreground: #1e1e1e;
  --primary: #4054B2;
  --secondary: #4054B2;
  --primary-foreground: #ffffff;
  --accent: #f3f4f6;
  --accent-foreground: #1e1e1e;
}';
        wp_add_inline_style('dehum-mvp-admin', $theme_css);

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
        // New Python AI Service settings
        register_setting('dehum_mvp_options_group', 'dehum_mvp_ai_service_url', ['type' => 'string', 'sanitize_callback' => 'esc_url_raw']);
        register_setting('dehum_mvp_options_group', 'dehum_mvp_ai_service_key', ['type' => 'string', 'sanitize_callback' => [$this, 'encrypt_api_key_callback']]);
        
        // Appearance settings
        register_setting('dehum_mvp_options_group', 'dehum_mvp_chat_icon', ['type'=>'string','sanitize_callback'=>'sanitize_text_field', 'default'=>'sms']);
        register_setting('dehum_mvp_options_group', 'dehum_mvp_theme_css', ['type'=>'string','sanitize_callback'=>'wp_kses_post']);

        // NEW: Access control setting
        register_setting('dehum_mvp_options_group', 'dehum_mvp_chat_logged_in_only', ['type' => 'boolean', 'sanitize_callback' => 'intval', 'default' => 0]);
        
        // Legacy n8n settings (kept for backward compatibility)
        register_setting('dehum_mvp_options_group', 'dehum_mvp_n8n_webhook_url', ['type' => 'string', 'sanitize_callback' => 'esc_url_raw']);
        register_setting('dehum_mvp_options_group', 'dehum_mvp_n8n_webhook_user', ['type' => 'string']);
        register_setting('dehum_mvp_options_group', 'dehum_mvp_n8n_webhook_pass', ['type' => 'string', 'sanitize_callback' => [$this, 'encrypt_password_callback']]);

        // Add settings sections and fields
        add_settings_section(
            'dehum_mvp_ai_service_section',
            __('AI Service Settings', 'dehum-assistant-mvp'),
            null,
            'dehum-mvp-logs'
        );

        add_settings_field(
            'dehum_mvp_ai_service_url',
            __('Python AI Service URL', 'dehum-assistant-mvp'),
            [$this, 'ai_service_url_callback'],
            'dehum-mvp-logs',
            'dehum_mvp_ai_service_section'
        );

        add_settings_field(
            'dehum_mvp_ai_service_key',
            __('AI Service API Key', 'dehum-assistant-mvp'),
            [$this, 'ai_service_key_callback'],
            'dehum-mvp-logs',
            'dehum_mvp_ai_service_section'
        );

        add_settings_section(
            'dehum_mvp_appearance_section',
            __('Appearance', 'dehum-assistant-mvp'),
            null,
            'dehum-mvp-logs'
        );

        add_settings_field(
            'dehum_mvp_chat_icon',
            __('Chat Icon (Material Symbol name)', 'dehum-assistant-mvp'),
            [$this, 'chat_icon_callback'],
            'dehum-mvp-logs',
            'dehum_mvp_appearance_section'
        );

        add_settings_field(
            'dehum_mvp_theme_css',
            __('Custom Theme CSS Variables', 'dehum-assistant-mvp'),
            [$this, 'theme_css_callback'],
            'dehum-mvp-logs',
            'dehum_mvp_appearance_section'
        );

        add_settings_section(
            'dehum_mvp_access_section',
            __('Chat Access', 'dehum-assistant-mvp'),
            null,
            'dehum-mvp-logs'
        );

        add_settings_field(
            'dehum_mvp_chat_logged_in_only',
            __('Restrict chat to logged-in users only', 'dehum-assistant-mvp'),
            [$this, 'chat_access_callback'],
            'dehum-mvp-logs',
            'dehum_mvp_access_section'
        );

        add_settings_section(
            'dehum_mvp_legacy_section',
            __('Legacy n8n Settings', 'dehum-assistant-mvp'),
            [$this, 'legacy_section_callback'],
            'dehum-mvp-logs'
        );

        add_settings_field(
            'dehum_mvp_n8n_webhook_url',
            __('n8n Webhook URL', 'dehum-assistant-mvp'),
            [$this, 'n8n_webhook_url_callback'],
            'dehum-mvp-logs',
            'dehum_mvp_legacy_section'
        );

        add_settings_field(
            'dehum_mvp_n8n_webhook_user',
            __('n8n Webhook Username', 'dehum-assistant-mvp'),
            [$this, 'n8n_webhook_user_callback'],
            'dehum-mvp-logs',
            'dehum_mvp_legacy_section'
        );

        add_settings_field(
            'dehum_mvp_n8n_webhook_pass',
            __('n8n Webhook Password', 'dehum-assistant-mvp'),
            [$this, 'n8n_webhook_pass_callback'],
            'dehum-mvp-logs',
            'dehum_mvp_legacy_section'
        );
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
     * Sanitize and encrypt the AI service API key.
     *
     * @param string $api_key The plain text API key.
     * @return string Empty string (we store encrypted version separately).
     */
    public function encrypt_api_key_callback($api_key) {
        if (!empty($api_key)) {
            // Create AJAX instance to access encryption method
            $ajax = new Dehum_MVP_Ajax($this->db);
            $encrypted = $ajax->encrypt_credential($api_key);
            update_option('dehum_mvp_ai_service_key_encrypted', $encrypted);
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
            $ai_service_url = get_option('dehum_mvp_ai_service_url');
            $legacy_webhook_url = get_option('dehum_mvp_n8n_webhook_url');
            
            // Check which service is configured
            if (!empty($ai_service_url)) {
                $service_status = '<span style="color:green;">✅ Python AI Service is configured.</span>';
            } elseif (!empty($legacy_webhook_url)) {
                $service_status = '<span style="color:orange;">⚠️ Legacy n8n webhook detected. Consider upgrading to Python AI Service.</span>';
            } else {
                $service_status = '<span style="color:red;">❌ Action Required: AI Service URL is not set.</span>';
            }

            ?>
            <div class="notice notice-success is-dismissible">
                <p>
                    <strong>Dehumidifier Assistant MVP is active!</strong>
                    The chat widget is now live on your site's frontend.
                    <a href="<?php echo admin_url('tools.php?page=dehum-mvp-logs'); ?>">View Conversation Logs</a>
                    <br><small><?php echo $service_status; ?></small>
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

        echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" style="margin-bottom:15px;">';
        wp_nonce_field( 'dehum_reset_rate', 'dehum_reset_rate_nonce' );
        echo '<input type="hidden" name="action" value="dehum_reset_rate">';
        echo '<button type="submit" class="button">' . __( 'Reset Rate Limits', 'dehum-assistant-mvp' ) . '</button>';
        echo '</form>';

        // Add diagnostic section
        $this->render_diagnostic_section();

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

        $data = [
            'is_sodium_available' => function_exists('sodium_crypto_secretbox')
        ];

        // Pass data to the view
        extract($data);
        require_once DEHUM_MVP_PLUGIN_PATH . 'includes/views/view-logs-page.php';
    }

    /**
     * Render diagnostic section to help debug conversation storage issues.
     */
    private function render_diagnostic_section() {
        global $wpdb;
        $table_name = $this->db->get_conversations_table_name();
        
        // Check if table exists
        $table_exists = $wpdb->get_var($wpdb->prepare("SHOW TABLES LIKE %s", $table_name)) === $table_name;
        
        // Get table stats
        $total_conversations = $table_exists ? $wpdb->get_var("SELECT COUNT(*) FROM $table_name") : 0;
        $recent_conversations = $table_exists ? $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM $table_name WHERE timestamp >= %s", 
            date('Y-m-d H:i:s', strtotime('-1 hour'))
        )) : 0;
        
        // Check settings
        $ai_service_url = get_option('dehum_mvp_ai_service_url');
        $logged_in_only = get_option('dehum_mvp_chat_logged_in_only', 0);
        $has_api_key = !empty(get_option('dehum_mvp_ai_service_key_encrypted'));
        
        echo '<div class="notice notice-info" style="margin-bottom: 20px;">';
        echo '<h3>' . __('🔍 Conversation Storage Diagnostics', 'dehum-assistant-mvp') . '</h3>';
        
        echo '<table class="widefat">';
        echo '<tr><td><strong>Database Table:</strong></td><td>' . ($table_exists ? '✅ Exists' : '❌ Missing') . ' (' . esc_html($table_name) . ')</td></tr>';
        echo '<tr><td><strong>Total Conversations:</strong></td><td>' . number_format($total_conversations) . '</td></tr>';
        echo '<tr><td><strong>Recent (1 hour):</strong></td><td>' . number_format($recent_conversations) . '</td></tr>';
        echo '<tr><td><strong>AI Service URL:</strong></td><td>' . (!empty($ai_service_url) ? '✅ Configured' : '❌ Not set') . '</td></tr>';
        echo '<tr><td><strong>API Key:</strong></td><td>' . ($has_api_key ? '✅ Set' : '⚠️ Not set (optional)') . '</td></tr>';
        echo '<tr><td><strong>Access Control:</strong></td><td>' . ($logged_in_only ? '⚠️ Logged-in users only' : '✅ Open to all users') . '</td></tr>';
        echo '</table>';
        
        if ($logged_in_only) {
            echo '<p style="color: #d63638;"><strong>⚠️ Warning:</strong> Chat is restricted to logged-in users only. Anonymous users cannot save conversations.</p>';
        }
        
        if (!$table_exists) {
            echo '<p style="color: #d63638;"><strong>❌ Critical:</strong> Conversations table is missing. Try deactivating and reactivating the plugin.</p>';
        } elseif ($recent_conversations === 0) {
            echo '<p style="color: #d63638;"><strong>⚠️ Issue:</strong> No conversations recorded in the last hour. Check browser console for JavaScript errors when testing chat.</p>';
        } else {
            echo '<p style="color: #00a32a;"><strong>✅ Status:</strong> Conversation storage appears to be working normally.</p>';
        }
        
        echo '</div>';
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

    /* =====================================================
     *  RATE-LIMIT RESET HANDLER
     * ===================================================== */

    /**
     * Handle the global rate-limit reset request (admin-post).
     */
    public function handle_rate_reset() {
        if ( ! current_user_can( 'manage_options' ) ) {
            wp_die( 'Insufficient permissions.' );
        }

        // Verify nonce
        if ( ! isset( $_POST['dehum_reset_rate_nonce'] ) || ! wp_verify_nonce( $_POST['dehum_reset_rate_nonce'], 'dehum_reset_rate' ) ) {
            wp_die( 'Security check failed.' );
        }

        global $wpdb;
        // Delete any transients that store rate info (prefix: dehum_mvp_rate_limit_)
        $wpdb->query( "DELETE FROM {$wpdb->options} WHERE option_name LIKE '_transient_dehum_mvp_rate_limit_%' OR option_name LIKE '_transient_timeout_dehum_mvp_rate_limit_%'" );

        set_transient( 'dehum_rate_reset_notice', __( 'Assistant rate-limit counters have been reset.', 'dehum-assistant-mvp' ), 30 );

        wp_safe_redirect( wp_get_referer() ? wp_get_referer() : admin_url('tools.php?page=dehum-mvp-logs') );
        exit;
    }

    /**
     * Display admin notice after a successful reset.
     */
    public function rate_reset_notice() {
        if ( $msg = get_transient( 'dehum_rate_reset_notice' ) ) {
            echo '<div class="notice notice-success is-dismissible"><p>' . esc_html( $msg ) . '</p></div>';
            delete_transient( 'dehum_rate_reset_notice' );
        }
    }

    public function handle_rotate_key() {
        if (!function_exists('sodium_crypto_secretbox_keygen')) {
            set_transient('dehum_admin_error', 'Key rotation requires the libsodium PHP extension, which is not installed.', 30);
            wp_redirect(admin_url('tools.php?page=dehum-mvp-logs'));
            wp_die();
            exit;
        }

        check_admin_referer('dehum_mvp_rotate_key');
        if (!current_user_can('manage_options')) {
            wp_die('Unauthorized');
        }
        $old_key = get_option('dehum_mvp_encryption_key');
        $new_key = base64_encode(sodium_crypto_secretbox_keygen());
        update_option('dehum_mvp_old_encryption_key', $old_key);
        update_option('dehum_mvp_encryption_key', $new_key);
        
        set_transient('dehum_admin_success', 'Encryption key rotated successfully.', 30);
        wp_redirect(admin_url('tools.php?page=dehum-mvp-logs'));
        exit;
    }

    public function ai_service_url_callback() {
        $value = get_option('dehum_mvp_ai_service_url');
        echo '<input type="url" id="dehum_mvp_ai_service_url" name="dehum_mvp_ai_service_url" value="' . esc_attr($value) . '" class="regular-text" placeholder="http://localhost:8000" />';
        echo '<p class="description">';
        echo __('Enter the URL of your Python AI service (without /chat endpoint).', 'dehum-assistant-mvp');
        echo '<br><strong>' . __('Recommended:', 'dehum-assistant-mvp') . '</strong> <code>http://localhost:8000</code> ' . __('for local development', 'dehum-assistant-mvp');
        echo '</p>';
    }

    public function ai_service_key_callback() {
        $has_api_key = !empty(get_option('dehum_mvp_ai_service_key_encrypted'));
        echo '<input type="password" id="dehum_mvp_ai_service_key" name="dehum_mvp_ai_service_key" value="" class="regular-text" placeholder="' . ($has_api_key ? esc_attr__('API key is set (enter new key to change)', 'dehum-assistant-mvp') : esc_attr__('Optional API key for authentication', 'dehum-assistant-mvp')) . '" />';
        echo '<p class="description">';
        echo __('Optional API key for authenticating with your AI service.', 'dehum-assistant-mvp');
        if ($has_api_key) {
            echo '<br><em>' . __('API key is encrypted and stored securely. Leave blank to keep current key.', 'dehum-assistant-mvp') . '</em>';
        }
        echo '</p>';
    }

    public function chat_icon_callback() {
        $value = get_option('dehum_mvp_chat_icon', 'sms');
        echo '<input type="text" id="dehum_mvp_chat_icon" name="dehum_mvp_chat_icon" value="' . esc_attr($value) . '" class="regular-text" />';
        echo '<p class="description">' . __('Enter a Google Material Symbol name, e.g., sms, chat, forum.', 'dehum-assistant-mvp') . '</p>';
    }

    public function theme_css_callback() {
        $value = get_option('dehum_mvp_theme_css');
        echo '<textarea id="dehum_mvp_theme_css" name="dehum_mvp_theme_css" rows="8" cols="60" class="large-text code">' . esc_textarea($value) . '</textarea>';
        echo '<p class="description">' . __('Paste custom :root { ... } CSS to override default colors.', 'dehum-assistant-mvp') . '</p>';
    }

    public function chat_access_callback() {
        $value = get_option('dehum_mvp_chat_logged_in_only', 0);
        echo '<label><input type="checkbox" name="dehum_mvp_chat_logged_in_only" value="1" ' . checked($value, 1, false) . ' /> ' . __('Only logged-in users can use the chat (testing mode)', 'dehum-assistant-mvp') . '</label>';
    }

    public function legacy_section_callback() {
        echo '<p style="color: #666; font-style: italic;">' . __('These settings are kept for backward compatibility. New installations should use the Python AI Service above.', 'dehum-assistant-mvp') . '</p>';
    }

    public function n8n_webhook_url_callback() {
        $value = get_option('dehum_mvp_n8n_webhook_url');
        echo '<input type="url" id="dehum_mvp_n8n_webhook_url" name="dehum_mvp_n8n_webhook_url" value="' . esc_attr($value) . '" class="regular-text" placeholder="https://your-n8n-instance.com/webhook/..." />';
        echo '<p class="description">' . __('Enter the full webhook URL for your n8n workflow.', 'dehum-assistant-mvp') . '</p>';
    }

    public function n8n_webhook_user_callback() {
        $value = get_option('dehum_mvp_n8n_webhook_user');
        echo '<input type="text" id="dehum_mvp_n8n_webhook_user" name="dehum_mvp_n8n_webhook_user" value="' . esc_attr($value) . '" class="regular-text" placeholder="' . esc_attr__('Username', 'dehum-assistant-mvp') . '" />';
        echo '<p class="description">' . __('The Basic Auth username for your n8n webhook.', 'dehum-assistant-mvp') . '</p>';
    }

    public function n8n_webhook_pass_callback() {
        $has_password = !empty(get_option('dehum_mvp_n8n_webhook_pass_encrypted'));
        echo '<input type="password" id="dehum_mvp_n8n_webhook_pass" name="dehum_mvp_n8n_webhook_pass" value="" class="regular-text" placeholder="' . ($has_password ? esc_attr__('Password is set (enter new password to change)', 'dehum-assistant-mvp') : esc_attr__('Password', 'dehum-assistant-mvp')) . '" />';
        echo '<p class="description">';
        echo __('The Basic Auth password for your n8n webhook.', 'dehum-assistant-mvp');
        if ($has_password) {
            echo '<br><em>' . __('Password is encrypted and stored securely. Leave blank to keep current password.', 'dehum-assistant-mvp') . '</em>';
        }
        echo '</p>';
    }
} 