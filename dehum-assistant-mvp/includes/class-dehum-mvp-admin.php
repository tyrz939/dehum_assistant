<?php
// Prevent direct access
if (!defined('ABSPATH')) exit;

/**
 * Class Dehum_MVP_Admin
 * Handles admin functionality: settings, logs, dashboard.
 */
class Dehum_MVP_Admin {

    private $db;

    public function __construct(Dehum_MVP_Database $db) {
        $this->db = $db;
        $this->init_hooks();
    }

    // Initialize all admin hooks
    private function init_hooks() {
        add_action('admin_init', [$this, 'ensure_database_table']);
        add_action('admin_menu', [$this, 'add_admin_menu']);
        add_action('admin_init', [$this, 'register_settings']);
        add_action('admin_enqueue_scripts', [$this, 'enqueue_assets']);
        add_action('wp_dashboard_setup', [$this, 'add_dashboard_widget']);
        add_action('admin_notices', [$this, 'activation_notice']);
        add_action('admin_notices', [$this, 'rate_reset_notice']);
        add_action('admin_post_dehum_reset_rate', [$this, 'handle_rate_reset']);
        add_action('admin_init', [$this, 'handle_export_download']);
        add_action('wp_ajax_dehum_reset_rate', [$this, 'handle_rate_reset']);
    }

    // Ensure DB table exists
    public function ensure_database_table() {
        $this->db->ensure_table_exists();
    }

    // Enqueue admin assets efficiently
    public function enqueue_assets($hook) {
        if ($hook !== 'tools_page_dehum-mvp-logs' && $hook !== 'index.php') return;

        wp_enqueue_style('dehum-mvp-admin', DEHUM_MVP_PLUGIN_URL . 'assets/css/admin.css', [], DEHUM_MVP_VERSION);

        $local_font = DEHUM_MVP_PLUGIN_PATH . 'assets/fonts/MaterialSymbolsOutlined.woff2';
        $font_url = file_exists($local_font) ? DEHUM_MVP_PLUGIN_URL . 'assets/css/material-symbols.css' : 'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined';
        wp_enqueue_style('dehum-mvp-material-symbols', $font_url, [], DEHUM_MVP_VERSION);

        if ($hook === 'tools_page_dehum-mvp-logs') {
            wp_enqueue_script('dehum-mvp-admin', DEHUM_MVP_PLUGIN_URL . 'assets/js/admin.js', ['jquery'], DEHUM_MVP_VERSION, true);
            wp_localize_script('dehum-mvp-admin', 'dehum_admin_vars', [
                'nonce' => wp_create_nonce(DEHUM_MVP_SESSION_NONCE),
                'delete_nonce' => wp_create_nonce(DEHUM_MVP_DELETE_SESSION_NONCE),
                'rate_nonce' => wp_create_nonce('dehum_reset_rate'),
                'ajaxurl' => admin_url('admin-ajax.php')
            ]);
        }
    }

    // Register settings fields and sections
    public function register_settings() {
        register_setting('dehum_mvp_options_group', 'dehum_mvp_ai_service_url', ['sanitize_callback' => 'esc_url_raw']);
        register_setting('dehum_mvp_options_group', 'dehum_mvp_ai_service_key', ['sanitize_callback' => [$this, 'encrypt_api_key_callback']]);
        register_setting('dehum_mvp_options_group', 'dehum_mvp_chat_icon', ['default' => 'sms']);
        register_setting('dehum_mvp_options_group', 'dehum_mvp_theme_css');
        register_setting('dehum_mvp_options_group', 'dehum_mvp_chat_logged_in_only', ['default' => 0]);

        add_settings_section('dehum_mvp_ai_service_section', __('AI Service', 'dehum-assistant-mvp'), null, 'dehum-mvp-logs');
        add_settings_field('dehum_mvp_ai_service_url', __('URL', 'dehum-assistant-mvp'), [$this, 'ai_service_url_callback'], 'dehum-mvp-logs', 'dehum_mvp_ai_service_section');
        add_settings_field('dehum_mvp_ai_service_key', __('API Key', 'dehum-assistant-mvp'), [$this, 'ai_service_key_callback'], 'dehum-mvp-logs', 'dehum_mvp_ai_service_section');

        add_settings_section('dehum_mvp_appearance_section', __('Appearance', 'dehum-assistant-mvp'), null, 'dehum-mvp-logs');
        add_settings_field('dehum_mvp_chat_icon', __('Chat Icon', 'dehum-assistant-mvp'), [$this, 'chat_icon_callback'], 'dehum-mvp-logs', 'dehum_mvp_appearance_section');
        add_settings_field('dehum_mvp_theme_css', __('Custom CSS Vars', 'dehum-assistant-mvp'), [$this, 'theme_css_callback'], 'dehum-mvp-logs', 'dehum_mvp_appearance_section');

        add_settings_section('dehum_mvp_access_section', __('Access', 'dehum-assistant-mvp'), null, 'dehum-mvp-logs');
        add_settings_field('dehum_mvp_chat_logged_in_only', __('Logged-in Only', 'dehum-assistant-mvp'), [$this, 'chat_access_callback'], 'dehum-mvp-logs', 'dehum_mvp_access_section');
    }

    // Encrypt API key (simplified)
    public function encrypt_api_key_callback($api_key) {
        if (!empty($api_key)) {
            $encrypted = $this->encrypt_credential($api_key); // Assume encrypt_credential is defined elsewhere or in AJAX class
            update_option('dehum_mvp_ai_service_key_encrypted', $encrypted);
            wp_cache_delete('alloptions', 'options');
        }
        return '';
    }

    // Add menu with dynamic badge
    public function add_admin_menu() {
        $stats = $this->db->get_stats();
        $menu_title = __('Dehumidifier Logs', 'dehum-assistant-mvp');
        if ($stats['today_messages'] > 0) {
            $menu_title .= ' <span class="awaiting-mod">' . $stats['today_messages'] . '</span>';
        }
        add_management_page(__('Dehumidifier Logs', 'dehum-assistant-mvp'), $menu_title, 'manage_options', 'dehum-mvp-logs', [$this, 'render_logs_page']);
    }

    // Activation notice
    public function activation_notice() {
        if (get_transient('dehum_mvp_activation_notice')) {
            $url = get_option('dehum_mvp_ai_service_url');
            $status = $url ? '<span style="color:green;">✅ Configured</span>' : '<span style="color:red;">❌ Not set</span>';
            echo '<div class="notice notice-success is-dismissible"><p><strong>Dehumidifier Assistant active!</strong> Chat is live. <a href="' . admin_url('tools.php?page=dehum-mvp-logs') . '">View Logs</a><br><small>' . $status . '</small></p></div>';
            delete_transient('dehum_mvp_activation_notice');
        }
    }

    // Dashboard widget
    public function add_dashboard_widget() {
        wp_add_dashboard_widget('dehum_mvp_stats', __('Dehumidifier Activity', 'dehum-assistant-mvp'), [$this, 'render_dashboard_widget']);
    }

    public function render_dashboard_widget() {
        $stats = $this->db->get_stats();
        include DEHUM_MVP_PLUGIN_PATH . 'includes/views/view-dashboard-widget.php';
    }

    // Render logs page
    public function render_logs_page() {
        $this->handle_actions();

        // Handle notices (from transients or actions)
        if ($msg = get_transient('dehum_admin_notice')) {
            echo '<div class="notice notice-success is-dismissible"><p>' . esc_html($msg) . '</p></div>';
            delete_transient('dehum_admin_notice');
        }

        echo '<div class="wrap">';

        echo '<button id="dehum-reset-rate-btn" class="button">Reset Rate Limits</button>';

        $this->render_diagnostic_section();

        $filters = [
            'search' => sanitize_text_field($_GET['search'] ?? ''),
            'date_filter' => sanitize_text_field($_GET['date_filter'] ?? ''),
            'custom_start' => sanitize_text_field($_GET['custom_start'] ?? ''),
            'custom_end' => sanitize_text_field($_GET['custom_end'] ?? ''),
            'ip_filter' => sanitize_text_field($_GET['ip_filter'] ?? ''),
            'per_page' => intval($_GET['per_page'] ?? 20),
            'paged' => intval($_GET['paged'] ?? 1),
        ];

        $sessions = $this->db->get_sessions($filters);
        $total = $this->db->count_sessions($filters);
        $stats = $this->db->get_stats();

        // Calculate pagination
        $total_pages = ceil($total / $filters['per_page']);
        $current_page = $filters['paged'];
        $pagination = paginate_links([
            'base' => add_query_arg(array_merge($_GET, ['paged' => '%#%'])),
            'format' => '',
            'current' => $current_page,
            'total' => $total_pages,
            'prev_text' => '&laquo; Previous',
            'next_text' => 'Next &raquo;',
            'end_size' => 2,
            'mid_size' => 2,
        ]);

        // Prepare view data
        $view_data = compact('sessions', 'total', 'stats', 'filters', 'total_pages', 'current_page', 'pagination');

        extract($view_data);
        include DEHUM_MVP_PLUGIN_PATH . 'includes/views/view-logs-page.php';

        // Close wrapper
        echo '</div>';
    }

    // Diagnostic section (optimized output)
    private function render_diagnostic_section() {
        global $wpdb;
        $table = $this->db->get_conversations_table_name();
        $exists = $wpdb->get_var($wpdb->prepare("SHOW TABLES LIKE %s", $table)) === $table;
        $total = $exists ? (int) $wpdb->get_var("SELECT COUNT(*) FROM $table") : 0;
        $recent = $exists ? (int) $wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM $table WHERE timestamp >= %s", date('Y-m-d H:i:s', strtotime('-1 hour')))) : 0;

        $url = get_option('dehum_mvp_ai_service_url');
        $logged_in_only = get_option('dehum_mvp_chat_logged_in_only', 0);
        $has_key = !empty(get_option('dehum_mvp_ai_service_key_encrypted'));

        echo '<div class="notice notice-info"><h3>🔍 Diagnostics</h3><table class="widefat">';
        echo '<tr><td>Table:</td><td>' . ($exists ? '✅ Exists' : '❌ Missing') . ' (' . esc_html($table) . ')</td></tr>';
        echo '<tr><td>Total:</td><td>' . number_format($total) . '</td></tr>';
        echo '<tr><td>Recent (1h):</td><td>' . number_format($recent) . '</td></tr>';
        echo '<tr><td>AI URL:</td><td>' . ($url ? '✅ Set' : '❌ Not set') . '</td></tr>';
        echo '<tr><td>API Key:</td><td>' . ($has_key ? '✅ Set' : '⚠️ Not set') . '</td></tr>';
        echo '<tr><td>Access:</td><td>' . ($logged_in_only ? '⚠️ Logged-in only' : '✅ Open') . '</td></tr>';
        echo '</table>';

        if ($logged_in_only) echo '<p style="color:#d63638;">⚠️ Chat restricted to logged-in users.</p>';
        if (!$exists) echo '<p style="color:#d63638;">❌ Table missing. Reactivate plugin.</p>';
        elseif (!$recent) echo '<p style="color:#d63638;">⚠️ No recent logs. Check console.</p>';
        else echo '<p style="color:#00a32a;">✅ Storage working.</p>';
        echo '</div>';
    }

    // Handle actions (consolidated)
    private function handle_actions() {
        if (isset($_POST['bulk_action'], $_POST['bulk_nonce']) && wp_verify_nonce($_POST['bulk_nonce'], DEHUM_MVP_BULK_NONCE) && current_user_can('manage_options')) {
            $action = sanitize_key($_POST['bulk_action']);
            switch ($action) {
                case 'delete_old':
                    $count = $this->db->delete_old_conversations();
                    $msg = $count !== false ? sprintf('Deleted %d old conversations.', $count) : 'Delete failed.';
                    break;
                case 'delete_selected':
                    $ids = array_map('sanitize_text_field', (array) ($_POST['selected_sessions'] ?? []));
                    $count = $this->db->delete_sessions_bulk($ids);
                    $msg = $count !== false ? sprintf('Deleted %d selected.', count($ids)) : 'Delete failed.';
                    break;
                case 'delete_by_date':
                    $start = sanitize_text_field($_POST['delete_start_date'] ?? '');
                    $end = sanitize_text_field($_POST['delete_end_date'] ?? '');
                    $count = $this->db->delete_by_date_range($start, $end);
                    $msg = $count !== false ? sprintf('Deleted %d from %s to %s.', $count, $start, $end) : 'Delete failed.';
                    break;
                case 'delete_by_ip':
                    $ip = sanitize_text_field($_POST['delete_ip'] ?? '');
                    $count = $this->db->delete_by_ip($ip);
                    $msg = $count !== false ? sprintf('Deleted %d from IP %s.', $count, $ip) : 'Delete failed.';
                    break;
                default:
                    $msg = 'Invalid action.';
            }
            set_transient('dehum_admin_notice', $msg, 30);
            wp_redirect(admin_url('tools.php?page=dehum-mvp-logs'));
            exit;
        }
    }

    // Rate reset handler
    public function handle_rate_reset() {
        error_log('Rate reset called: User=' . get_current_user_id() . ', Nonce=' . ($_POST['nonce'] ?? 'none'));
        if (!current_user_can('manage_options') || !wp_verify_nonce($_POST['nonce'] ?? '', 'dehum_reset_rate')) {
            error_log('Rate reset failed: Nonce invalid or insufficient perms');
            if (wp_doing_ajax()) {
                wp_send_json_error(['message' => 'Access denied']);
            } else {
                wp_die('Access denied');
            }
        }
        global $wpdb;
        $epoch = (int) get_option('dehum_mvp_rate_epoch', 1);
        $epoch++;
        update_option('dehum_mvp_rate_epoch', $epoch);
        wp_cache_flush();
        error_log('Rate reset: bumped epoch to ' . $epoch);
        $msg = sprintf(__('Rate limits reset. Epoch: %d', 'dehum-assistant-mvp'), $epoch);

        if (wp_doing_ajax()) {
            wp_send_json_success(['message' => $msg]);
        } else {
            set_transient('dehum_rate_reset_notice', $msg, 30);
            wp_safe_redirect(wp_get_referer() ?: admin_url('tools.php?page=dehum-mvp-logs'));
            exit;
        }
    }

    public function rate_reset_notice() {
        if ($msg = get_transient('dehum_rate_reset_notice')) {
            echo '<div class="notice notice-success is-dismissible"><p>' . esc_html($msg) . '</p></div>';
            delete_transient('dehum_rate_reset_notice');
        }
    }

    // Export handler (optimized)
    public function handle_export_download() {
        if (($_GET['page'] ?? '') !== 'dehum-mvp-logs' || ($_GET['action'] ?? '') !== 'export' || !wp_verify_nonce($_GET['export_nonce'] ?? '', DEHUM_MVP_EXPORT_NONCE) || !current_user_can('manage_options')) return;

        $filters = $_GET;
        unset($filters['page'], $filters['action'], $filters['export_nonce'], $filters['paged']);

        $this->export_conversations($filters);
    }

    // Export CSV (lean headers and output)
    private function export_conversations($filters) {
        global $wpdb;
        $table = $this->db->get_conversations_table_name();
        [$where, $params] = $this->db->build_where_clause($filters);
        $query = "SELECT * FROM $table $where ORDER BY timestamp DESC";
        $rows = !empty($params) ? $wpdb->get_results($wpdb->prepare($query, $params)) : $wpdb->get_results($query);

        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="dehum-conversations-' . date('Y-m-d-H-i-s') . '.csv"');
        header('Cache-Control: no-cache');
        header('Expires: 0');
        header('Pragma: no-cache');

        echo "\xEF\xBB\xBF"; // UTF-8 BOM
        echo '"Session ID","Date/Time","User Message","AI Response","User IP","Msg Len","Resp Len"' . "\r\n";

        foreach ($rows as $row) {
            echo '"' . str_replace('"', '""', $row->session_id) . '","' . $row->timestamp . '","' . str_replace('"', '""', $row->message) . '","' . str_replace('"', '""', $row->response) . '","' . $row->user_ip . '","' . strlen($row->message) . '","' . strlen($row->response) . '"' . "\r\n";
        }
        exit;
    }

    // Settings callbacks (unchanged but here for completeness)
    public function ai_service_url_callback() {
        $value = get_option('dehum_mvp_ai_service_url');
        echo '<input type="url" name="dehum_mvp_ai_service_url" value="' . esc_attr($value) . '" class="regular-text" placeholder="http://localhost:8000" />';
        echo '<p class="description">Enter Python AI service URL (no /chat).</p>';
    }

    public function ai_service_key_callback() {
        $has_key = !empty(get_option('dehum_mvp_ai_service_key_encrypted'));
        $placeholder = $has_key ? 'Key set (enter new to change)' : 'Optional API key';
        echo '<input type="password" name="dehum_mvp_ai_service_key" value="" class="regular-text" placeholder="' . esc_attr__($placeholder, 'dehum-assistant-mvp') . '" />';
        echo '<p class="description">Optional auth key (encrypted).</p>';
    }

    public function chat_icon_callback() {
        $value = get_option('dehum_mvp_chat_icon', 'sms');
        echo '<input type="text" name="dehum_mvp_chat_icon" value="' . esc_attr($value) . '" class="regular-text" />';
        echo '<p class="description">Material Symbol name (e.g., sms).</p>';
    }

    public function theme_css_callback() {
        $value = get_option('dehum_mvp_theme_css');
        echo '<textarea name="dehum_mvp_theme_css" rows="8" class="large-text code">' . esc_textarea($value) . '</textarea>';
        echo '<p class="description">Custom :root CSS variables.</p>';
    }

    public function chat_access_callback() {
        $value = get_option('dehum_mvp_chat_logged_in_only', 0);
        echo '<label><input type="checkbox" name="dehum_mvp_chat_logged_in_only" value="1" ' . checked(1, $value, false) . ' /> Testing mode: logged-in only</label>';
    }
} 