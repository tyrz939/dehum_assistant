<?php
/**
 * Plugin Name: Dehumidifier Assistant MVP
 * Plugin URI: https://github.com/your-username/dehum-assistant
 * Description: Minimal viable chat widget that connects to n8n workflow for dehumidifier sizing assistance
 * Version: 1.0.0
 * Author: Your Name
 * License: MIT
 * Text Domain: dehum-assistant-mvp
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Define plugin constants
define('DEHUM_MVP_PLUGIN_URL', plugin_dir_url(__FILE__));
define('DEHUM_MVP_PLUGIN_PATH', plugin_dir_path(__FILE__));
define('DEHUM_MVP_VERSION', '1.0.0');

/**
 * Main Dehumidifier Assistant MVP Class
 */
class DehumidifierAssistantMVP {
    
    public function __construct() {
        add_action('init', [$this, 'init']);
        register_activation_hook(__FILE__, [$this, 'activate']);
        register_deactivation_hook(__FILE__, [$this, 'deactivate']);
    }
    
    public function init() {
        // Enqueue frontend assets
        add_action('wp_enqueue_scripts', [$this, 'enqueue_frontend_assets']);
        
        // Enqueue admin assets
        add_action('admin_enqueue_scripts', [$this, 'enqueue_admin_assets']);
        
        // Add chat widget to footer
        add_action('wp_footer', [$this, 'render_chat_widget']);
        
        // AJAX handlers for chat functionality
        add_action('wp_ajax_dehum_mvp_chat', [$this, 'handle_chat_message']);
        add_action('wp_ajax_nopriv_dehum_mvp_chat', [$this, 'handle_chat_message']);
        
        // AJAX handler for loading session details in admin
        add_action('wp_ajax_dehum_mvp_get_session_details', [$this, 'handle_get_session_details']);
        
        // Admin notices for Step 1.2 testing
        add_action('admin_notices', [$this, 'admin_activation_notice']);
        
        // Step 5.3: Add admin menu for conversation logs
        add_action('admin_menu', [$this, 'add_admin_menu']);
        
        // Step 5.3: Add dashboard widget for conversation stats
        add_action('wp_dashboard_setup', [$this, 'add_dashboard_widget']);
        
        // Load textdomain for translations
        load_plugin_textdomain('dehum-assistant-mvp', false, dirname(plugin_basename(__FILE__)) . '/languages');
    }
    
    public function enqueue_frontend_assets() {
        // Enqueue CSS
        wp_enqueue_style(
            'dehum-mvp-chat',
            DEHUM_MVP_PLUGIN_URL . 'assets/css/chat.css',
            [],
            DEHUM_MVP_VERSION
        );
        
        // Enqueue JavaScript
        wp_enqueue_script(
            'dehum-mvp-chat',
            DEHUM_MVP_PLUGIN_URL . 'assets/js/chat.js',
            ['jquery'],
            DEHUM_MVP_VERSION,
            true
        );
        
        // Localize script for AJAX
        wp_localize_script('dehum-mvp-chat', 'dehumMVP', [
            'ajaxUrl' => admin_url('admin-ajax.php'),
            'nonce' => wp_create_nonce('dehum_mvp_chat_nonce'),
            'strings' => [
                'sendButton' => __('Send', 'dehum-assistant-mvp'),
                'placeholder' => __('Ask about dehumidifier sizing...', 'dehum-assistant-mvp'),
                'error' => __('Sorry, something went wrong. Please try again.', 'dehum-assistant-mvp'),
                'typing' => __('Assistant is typing...', 'dehum-assistant-mvp')
            ]
        ]);
    }
    
    public function enqueue_admin_assets($hook) {
        // Only load on our admin page
        if ($hook !== 'tools_page_dehum-mvp-logs') {
            return;
        }
        
        // Enqueue admin JavaScript
        wp_enqueue_script(
            'dehum-mvp-admin',
            DEHUM_MVP_PLUGIN_URL . 'assets/js/admin.js',
            ['jquery'],
            DEHUM_MVP_VERSION,
            true
        );
        
        // Localize script with admin-specific data
        wp_localize_script('dehum-mvp-admin', 'dehum_admin_vars', [
            'nonce' => wp_create_nonce('dehum_session_details')
        ]);
    }
    
    public function render_chat_widget() {
        // Only show on frontend, not in admin
        if (is_admin()) {
            return;
        }
        
        ?>
        <div id="dehum-mvp-chat-widget">
            <!-- Chat button -->
            <div id="dehum-mvp-chat-button">
                <span>💬</span>
                <span class="chat-text">Dehumidifier Help</span>
            </div>
            
            <!-- Chat modal (hidden initially) -->
            <div id="dehum-mvp-chat-modal" style="display: none;">
                <div class="chat-header">
                    <h3>Dehumidifier Assistant</h3>
                    <div class="chat-header-buttons">
                        <button id="dehum-mvp-clear-chat" class="clear-button" title="Start New Conversation">Clear</button>
                        <button id="dehum-mvp-close-chat">&times;</button>
                    </div>
                </div>
                <div class="chat-messages" id="dehum-mvp-chat-messages">
                    <div class="assistant-message">
                        <div class="message-content">Hello! I'm your Dehumidifier Assistant. Ask me anything about sizing or model selection.</div>
                        <div class="message-time">Now</div>
                    </div>
                </div>
                <div class="chat-input-area">
                    <textarea 
                        id="dehum-mvp-chat-input" 
                        placeholder="Ask about dehumidifier sizing..." 
                        rows="2"
                        maxlength="400"
                    ></textarea>
                    <button id="dehum-mvp-send-button">Send</button>
                </div>
                <div class="chat-footer">
                    <small>AI responses may contain errors - verify important details • <span id="char-count">0</span>/400 characters</small>
                </div>
            </div>
        </div>
        <?php
    }
    
    public function handle_chat_message() {
        // Verify nonce for security
        if (!wp_verify_nonce($_POST['nonce'], 'dehum_mvp_chat_nonce')) {
            wp_send_json_error(['message' => 'Security check failed'], 403);
        }
        
        // Step 4.2: Rate limiting check
        $rate_limit_check = $this->check_rate_limit();
        if (!$rate_limit_check['allowed']) {
            wp_send_json_error([
                'message' => $rate_limit_check['message'],
                'rate_limited' => true
            ], 429);
        }
        
        $user_input = sanitize_textarea_field($_POST['message']);
        
        // Basic input validation
        if (empty($user_input) || strlen($user_input) > 400) {
            wp_send_json_error(['message' => 'Invalid message length']);
        }
        
        // Step 5.2: Get or generate session ID for conversation threading
        $session_id = $this->get_or_create_session_id();
        
        // Debug: Log POST data for debugging
        if (defined('WP_DEBUG') && WP_DEBUG) {
            error_log('Dehum MVP: POST data received: ' . print_r($_POST, true));
            error_log("Dehum MVP: Final session ID for this request: {$session_id}");
        }
        
        // Step 3.1: Send to n8n webhook
        $n8n_response = $this->call_n8n_webhook($user_input);
        
        if ($n8n_response && isset($n8n_response['success']) && $n8n_response['success']) {
            // Step 4.2: Increment rate limit counter on successful response
            $this->increment_rate_limit_counter();
            
            // Step 5.2: Log successful conversation to database
            $this->log_conversation($session_id, $user_input, $n8n_response['response']);
            
            // Debug: Log successful response and run session analysis
            if (defined('WP_DEBUG') && WP_DEBUG) {
                error_log("Dehum MVP: Sending successful response with session ID: {$session_id}");
                
                // Run session analysis every 5th message for debugging
                static $debug_counter = 0;
                $debug_counter++;
                if ($debug_counter % 5 == 0) {
                    $this->debug_session_analysis();
                }
            }
            
            wp_send_json_success([
                'response' => $n8n_response['response'],
                'timestamp' => current_time('mysql'),
                'session_id' => $session_id  // Send session ID back to frontend
            ]);
        } else {
            // For n8n failures, we don't log since there's no valid response
            wp_send_json_error([
                'message' => 'Sorry, I\'m having trouble processing your request right now. Please try again in a moment.',
                'original_message' => $user_input
            ]);
        }
    }
    
    /**
     * Step 5.2: Get or create session ID for conversation threading
     * Uses WordPress sessions/transients for basic session management
     */
    private function get_or_create_session_id() {
        // Check if session ID was passed from frontend
        if (!empty($_POST['session_id'])) {
            $existing_session = sanitize_text_field($_POST['session_id']);
            
            // Log for debugging
            if (defined('WP_DEBUG') && WP_DEBUG) {
                error_log("Dehum MVP: Reusing existing session ID: {$existing_session}");
            }
            
            return $existing_session;
        }
        
        // Generate new session ID: timestamp + random string
        $session_id = current_time('Y-m-d_H-i-s') . '_' . wp_generate_password(8, false);
        
        // Log for debugging
        if (defined('WP_DEBUG') && WP_DEBUG) {
            error_log("Dehum MVP: Generated new session ID: {$session_id}");
        }
        
        return $session_id;
    }
    
    /**
     * Step 5.2: Log conversation to database
     * Inserts user message and AI response as single record
     */
    private function log_conversation($session_id, $user_message, $ai_response) {
        global $wpdb;
        
        $table_name = $this->get_conversations_table_name();
        $user_ip = $this->get_user_ip();
        
        // Insert conversation record
        $result = $wpdb->insert(
            $table_name,
            [
                'session_id' => $session_id,
                'message' => $user_message,
                'response' => $ai_response,
                'user_ip' => $user_ip,
                'timestamp' => current_time('mysql')
            ],
            [
                '%s',  // session_id
                '%s',  // message  
                '%s',  // response
                '%s',  // user_ip
                '%s'   // timestamp
            ]
        );
        
        // Log result for debugging
        if (defined('WP_DEBUG') && WP_DEBUG) {
            if ($result === false) {
                error_log('Dehum MVP: Failed to log conversation: ' . $wpdb->last_error);
                error_log('Dehum MVP: Failed query data: ' . print_r([
                    'session_id' => $session_id,
                    'message' => substr($user_message, 0, 50) . '...',
                    'response' => substr($ai_response, 0, 50) . '...',
                    'user_ip' => $user_ip
                ], true));
            } else {
                $inserted_id = $wpdb->insert_id;
                error_log("Dehum MVP: Conversation logged successfully (ID: {$inserted_id}, Session: {$session_id})");
                
                // Verify the session ID was stored correctly
                $stored_session = $wpdb->get_var($wpdb->prepare(
                    "SELECT session_id FROM {$this->get_conversations_table_name()} WHERE id = %d",
                    $inserted_id
                ));
                error_log("Dehum MVP: Verified stored session ID: {$stored_session}");
            }
        }
        
        return $result !== false;
    }
    
    /**
     * Step 4.2: Check rate limiting using WordPress transients
     * Limit: 20 messages per day per IP address
     * NOTE: Rate limiting persists across all chat sessions to prevent abuse
     */
    private function check_rate_limit() {
        $user_ip = $this->get_user_ip();
        $transient_key = 'dehum_mvp_rate_limit_' . md5($user_ip);
        $current_count = get_transient($transient_key);
        
        // First message of the day
        if ($current_count === false) {
            return [
                'allowed' => true,
                'count' => 0,
                'limit' => 20
            ];
        }
        
        // Check if limit exceeded
        if ($current_count >= 20) {
            return [
                'allowed' => false,
                'message' => 'Daily message limit reached (20 messages per day per device). This limit applies across all conversations. Please try again tomorrow.',
                'count' => $current_count,
                'limit' => 20
            ];
        }
        
        return [
            'allowed' => true,
            'count' => $current_count,
            'limit' => 20
        ];
    }
    
    /**
     * Step 4.2: Increment rate limit counter
     */
    private function increment_rate_limit_counter() {
        $user_ip = $this->get_user_ip();
        $transient_key = 'dehum_mvp_rate_limit_' . md5($user_ip);
        $current_count = get_transient($transient_key);
        
        if ($current_count === false) {
            // Set transient for 24 hours (86400 seconds)
            set_transient($transient_key, 1, 86400);
        } else {
            // Increment existing count
            set_transient($transient_key, $current_count + 1, 86400);
        }
        
        // Log for debugging (optional)
        if (defined('WP_DEBUG') && WP_DEBUG) {
            $new_count = $current_count + 1;
            error_log("Dehum MVP: Rate limit incremented for IP {$user_ip}: {$new_count}/20");
        }
    }
    
    /**
     * Step 4.2: Get user IP address with proxy support
     */
    private function get_user_ip() {
        // Check for various proxy headers
        $ip_headers = [
            'HTTP_CF_CONNECTING_IP',     // Cloudflare
            'HTTP_X_FORWARDED_FOR',      // Standard proxy header
            'HTTP_X_REAL_IP',            // Nginx proxy
            'HTTP_CLIENT_IP',            // Alternative header
            'REMOTE_ADDR'                // Direct connection
        ];
        
        foreach ($ip_headers as $header) {
            if (!empty($_SERVER[$header])) {
                $ip = $_SERVER[$header];
                
                // Handle comma-separated IPs (get first one)
                if (strpos($ip, ',') !== false) {
                    $ip = trim(explode(',', $ip)[0]);
                }
                
                // Validate IP address
                if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) {
                    return $ip;
                }
            }
        }
        
        // Fallback to REMOTE_ADDR even if it's private (for local development)
        return $_SERVER['REMOTE_ADDR'] ?? '127.0.0.1';
    }
    
    /**
     * Call n8n webhook with user message
     * Step 3.1: WordPress -> n8n integration
     */
    private function call_n8n_webhook($message) {
        $webhook_url = 'http://host.docker.internal:5678/webhook/dehum-chat';
        
        $body = wp_json_encode([
            'message' => $message
        ]);
        
        $args = [
            'body' => $body,
            'headers' => [
                'Content-Type' => 'application/json',
            ],
            'timeout' => 30, // 30 second timeout for AI processing
            'data_format' => 'body'
        ];
        
        // Make the request with retry logic
        $response = null;
        $max_retries = 3;
        
        for ($i = 0; $i < $max_retries; $i++) {
            $response = wp_remote_post($webhook_url, $args);
            
            if (!is_wp_error($response) && wp_remote_retrieve_response_code($response) === 200) {
                break; // Success!
            }
            
            // Wait before retry (exponential backoff)
            if ($i < $max_retries - 1) {
                sleep(pow(2, $i)); // 1s, 2s, 4s delays
            }
        }
        
        // Handle response - Enhanced debugging
        if (is_wp_error($response)) {
            $error_msg = $response->get_error_message();
            error_log('Dehum MVP: n8n webhook error - ' . $error_msg);
            error_log('Dehum MVP: Attempting to connect to - ' . $webhook_url);
            return false;
        }
        
        $response_code = wp_remote_retrieve_response_code($response);
        $response_body = wp_remote_retrieve_body($response);
        
        if ($response_code !== 200) {
            error_log("Dehum MVP: n8n webhook returned HTTP $response_code");
            error_log("Dehum MVP: Response body: " . $response_body);
            error_log("Dehum MVP: Full response: " . print_r($response, true));
            return false;
        }
        
        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);
        
        if (json_last_error() !== JSON_ERROR_NONE) {
            error_log('Dehum MVP: Invalid JSON from n8n webhook');
            return false;
        }
        
        return $data;
    }
    
    public function admin_activation_notice() {
        // Only show for 24 hours after activation for Step 1.2 testing
        $activated_at = get_option('dehum_mvp_activated_at');
        if (!$activated_at) return;
        
        $activated_time = strtotime($activated_at);
        $current_time = time();
        
        // Show notice for 24 hours after activation
        if (($current_time - $activated_time) < 86400) {
            // Step 4.2: Add rate limit status for testing
            $user_ip = $this->get_user_ip();
            $transient_key = 'dehum_mvp_rate_limit_' . md5($user_ip);
            $current_count = get_transient($transient_key);
            $rate_limit_info = $current_count !== false ? " (Rate limit: {$current_count}/20 messages used today)" : " (Rate limit: 0/20 messages used today)";
            
            // Step 5.1: Add database table status for testing
            global $wpdb;
            $table_name = $this->get_conversations_table_name();
            $table_exists = $wpdb->get_var("SHOW TABLES LIKE '$table_name'") === $table_name;
            
            if ($table_exists) {
                $conversation_count = $wpdb->get_var("SELECT COUNT(*) FROM $table_name");
                $session_count = $wpdb->get_var("SELECT COUNT(DISTINCT session_id) FROM $table_name");
                $latest_conversation = $wpdb->get_var("SELECT MAX(timestamp) FROM $table_name");
                
                if ($conversation_count > 0) {
                    $db_info = " | Database: {$conversation_count} messages in {$session_count} sessions (latest: " . 
                               ($latest_conversation ? date('H:i:s', strtotime($latest_conversation)) : 'none') . ")";
                } else {
                    $db_info = " | Database: Table ready, 0 conversations logged";
                }
            } else {
                $db_info = " | Database: Table not found!";
            }
            
            ?>
            <div class="notice notice-success is-dismissible">
                <p>
                    <strong>✅ Dehumidifier Assistant MVP</strong> is active! 
                    Visit your website frontend to see the chat button. 
                    <a href="<?php echo home_url(); ?>" target="_blank">Test it now →</a>
                    <br><small><?php echo $rate_limit_info . $db_info; ?></small>
                </p>
            </div>
            <?php
        }
    }
    
    /**
     * AJAX handler to get full session conversation details
     */
    public function handle_get_session_details() {
        // Verify nonce for security
        if (!wp_verify_nonce($_POST['nonce'], 'dehum_session_details')) {
            wp_send_json_error(['message' => 'Security check failed'], 403);
        }
        
        // Check user permissions
        if (!current_user_can('manage_options')) {
            wp_send_json_error(['message' => 'Insufficient permissions'], 403);
        }
        
        $session_id = sanitize_text_field($_POST['session_id']);
        
        if (empty($session_id)) {
            wp_send_json_error(['message' => 'Session ID required']);
        }
        
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        // Get all messages for this session
        $messages = $wpdb->get_results($wpdb->prepare(
            "SELECT id, message, response, timestamp, user_ip 
             FROM $table_name 
             WHERE session_id = %s 
             ORDER BY timestamp ASC",
            $session_id
        ));
        
        if (empty($messages)) {
            wp_send_json_error(['message' => 'No messages found for this session']);
        }
        
        // Format messages for display
        $formatted_messages = [];
        foreach ($messages as $msg) {
            $formatted_messages[] = [
                'id' => intval($msg->id),
                'message' => $msg->message,
                'response' => $msg->response,
                'timestamp' => date('M j, H:i:s', strtotime($msg->timestamp)),
                'user_ip' => $msg->user_ip
            ];
        }
        
        wp_send_json_success($formatted_messages);
    }
    
    /**
     * Debug function to analyze session behavior (add to WP admin bar for quick access)
     */
    private function debug_session_analysis() {
        if (!defined('WP_DEBUG') || !WP_DEBUG) return;
        
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        error_log('=== Dehum MVP Session Analysis ===');
        
        // Get recent sessions
        $recent_sessions = $wpdb->get_results("
            SELECT session_id, COUNT(*) as message_count, MIN(timestamp) as started, MAX(timestamp) as last_activity
            FROM $table_name 
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            GROUP BY session_id 
            ORDER BY last_activity DESC 
            LIMIT 10
        ");
        
        error_log('Recent sessions (last hour):');
        foreach ($recent_sessions as $session) {
            error_log("Session {$session->session_id}: {$session->message_count} messages, started {$session->started}, last activity {$session->last_activity}");
        }
        
        // Check for session threading issues
        $single_message_sessions = $wpdb->get_var("
            SELECT COUNT(*) FROM (
                SELECT session_id FROM $table_name 
                GROUP BY session_id 
                HAVING COUNT(*) = 1
            ) as single_sessions
        ");
        
        $multi_message_sessions = $wpdb->get_var("
            SELECT COUNT(*) FROM (
                SELECT session_id FROM $table_name 
                GROUP BY session_id 
                HAVING COUNT(*) > 1
            ) as multi_sessions
        ");
        
        error_log("Session threading analysis:");
        error_log("- Single message sessions: $single_message_sessions");
        error_log("- Multi-message sessions: $multi_message_sessions");
        
        if ($single_message_sessions > $multi_message_sessions * 2) {
            error_log("WARNING: High ratio of single-message sessions suggests session threading issues!");
        }
        
        error_log('=== End Session Analysis ===');
    }
    
    /**
     * Step 5.3: Add admin menu for conversation logs
     */
    public function add_admin_menu() {
        // Get today's conversation count for notification badge
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        $today_count = $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM $table_name WHERE DATE(timestamp) = %s", 
            current_time('Y-m-d')
        ));
        
        // Add notification badge if there are conversations today
        $menu_title = 'Dehumidifier Logs';
        if ($today_count > 0) {
            $menu_title .= ' <span class="awaiting-mod count-' . $today_count . '"><span class="pending-count">' . number_format($today_count) . '</span></span>';
        }
        
        add_management_page(
            'Dehumidifier Logs',              // Page title
            $menu_title,                      // Menu title with badge
            'manage_options',                 // Capability
            'dehum-mvp-logs',                 // Menu slug
            [$this, 'admin_logs_page']        // Callback function
        );
        

    }
    
    /**
     * Step 5.3: Admin page for viewing conversation logs
     */
    public function admin_logs_page() {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        // Handle bulk actions
        if (isset($_POST['bulk_action']) && isset($_POST['bulk_nonce']) && wp_verify_nonce($_POST['bulk_nonce'], 'dehum_bulk_actions')) {
            $this->handle_bulk_actions();
        }
        
        // Handle export
        if (isset($_GET['action']) && $_GET['action'] === 'export' && isset($_GET['export_nonce']) && wp_verify_nonce($_GET['export_nonce'], 'dehum_export')) {
            $this->export_conversations();
            return;
        }
        
        // Get filter parameters
        $search = isset($_GET['search']) ? sanitize_text_field($_GET['search']) : '';
        $date_filter = isset($_GET['date_filter']) ? sanitize_text_field($_GET['date_filter']) : '';
        $custom_start = isset($_GET['custom_start']) ? sanitize_text_field($_GET['custom_start']) : '';
        $custom_end = isset($_GET['custom_end']) ? sanitize_text_field($_GET['custom_end']) : '';
        $per_page = isset($_GET['per_page']) ? intval($_GET['per_page']) : 20;
        $paged = isset($_GET['paged']) ? intval($_GET['paged']) : 1;
        
        // Build WHERE clause for filters
        $where_conditions = [];
        $where_params = [];
        
        // Search filter - use FULLTEXT search for better performance
        if (!empty($search)) {
            // For simple searches, use FULLTEXT (faster for large datasets)
            if (strlen($search) >= 3 && !preg_match('/[*%_]/', $search)) {
                $where_conditions[] = "MATCH (message, response) AGAINST (%s IN NATURAL LANGUAGE MODE)";
                $where_params[] = $search;
            } else {
                // Fallback to LIKE for short searches or wildcards
                $where_conditions[] = "(message LIKE %s OR response LIKE %s)";
                $where_params[] = '%' . $wpdb->esc_like($search) . '%';
                $where_params[] = '%' . $wpdb->esc_like($search) . '%';
            }
        }
        
        // Date filter
        if (!empty($date_filter)) {
            switch ($date_filter) {
                case '7_days':
                    $where_conditions[] = "timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)";
                    break;
                case '30_days':
                    $where_conditions[] = "timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)";
                    break;
                case '90_days':
                    $where_conditions[] = "timestamp >= DATE_SUB(NOW(), INTERVAL 90 DAY)";
                    break;
                case 'custom':
                    if (!empty($custom_start)) {
                        $where_conditions[] = "DATE(timestamp) >= %s";
                        $where_params[] = $custom_start;
                    }
                    if (!empty($custom_end)) {
                        $where_conditions[] = "DATE(timestamp) <= %s";
                        $where_params[] = $custom_end;
                    }
                    break;
            }
        }
        
        $where_clause = !empty($where_conditions) ? 'WHERE ' . implode(' AND ', $where_conditions) : '';
        
        // Get total count for pagination
        $count_query = "SELECT COUNT(DISTINCT session_id) FROM $table_name $where_clause";
        if (!empty($where_params)) {
            $total_sessions = $wpdb->get_var($wpdb->prepare($count_query, $where_params));
        } else {
            $total_sessions = $wpdb->get_var($count_query);
        }
        
        // Calculate pagination
        $total_pages = ceil($total_sessions / $per_page);
        $offset = ($paged - 1) * $per_page;
        
        // Get session summary data with filters and pagination
        $session_query = "
            SELECT 
                session_id,
                COUNT(*) as message_count,
                MIN(timestamp) as first_message,
                MAX(timestamp) as last_message,
                user_ip,
                MIN(message) as first_question
            FROM $table_name 
            $where_clause
            GROUP BY session_id 
            ORDER BY last_message DESC 
            LIMIT %d OFFSET %d
        ";
        
        $query_params = array_merge($where_params, [$per_page, $offset]);
        $sessions = $wpdb->get_results($wpdb->prepare($session_query, $query_params));
        
        // Get total stats (unfiltered for header)
        $total_sessions_all = $wpdb->get_var("SELECT COUNT(DISTINCT session_id) FROM $table_name");
        $total_messages = $wpdb->get_var("SELECT COUNT(*) FROM $table_name");
        ?>
        
        <div class="wrap">
            <h1>💬 Chat Conversations</h1>
            
            <!-- Stats Summary -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <div style="display: flex; gap: 30px; align-items: center; flex-wrap: wrap;">
                    <div>
                        <div style="font-size: 24px; font-weight: bold;"><?php echo number_format($total_sessions_all); ?></div>
                        <div style="opacity: 0.9;">Total Sessions</div>
                    </div>
                    <div>
                        <div style="font-size: 24px; font-weight: bold;"><?php echo number_format($total_messages); ?></div>
                        <div style="opacity: 0.9;">Total Messages</div>
                    </div>
                    <div>
                        <div style="font-size: 24px; font-weight: bold;"><?php echo $total_sessions_all > 0 ? round($total_messages / $total_sessions_all, 1) : 0; ?></div>
                        <div style="opacity: 0.9;">Avg per Session</div>
                    </div>
                    <?php if ($total_sessions != $total_sessions_all): ?>
                    <div style="margin-left: auto;">
                        <div style="font-size: 18px; font-weight: bold;"><?php echo number_format($total_sessions); ?></div>
                        <div style="opacity: 0.9;">Filtered Results</div>
                    </div>
                    <?php endif; ?>
                </div>
            </div>

            <!-- Filters and Actions -->
            <div class="dehum-filters" style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #ddd;">
                <form method="GET" action="">
                    <input type="hidden" name="page" value="dehum-mvp-logs">
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 15px; align-items: end; margin-bottom: 15px;">
                        <!-- Search -->
                        <div>
                            <label style="display: block; font-weight: 500; margin-bottom: 5px;">Search Conversations</label>
                            <input type="text" name="search" value="<?php echo esc_attr($search); ?>" 
                                   placeholder="Search messages..." 
                                   style="width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px;">
                        </div>
                        
                        <!-- Date Filter -->
                        <div>
                            <label style="display: block; font-weight: 500; margin-bottom: 5px;">Date Range</label>
                            <select name="date_filter" style="width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px;"
                                    onchange="toggleCustomDates(this.value)">
                                <option value="">All Time</option>
                                <option value="7_days" <?php selected($date_filter, '7_days'); ?>>Last 7 Days</option>
                                <option value="30_days" <?php selected($date_filter, '30_days'); ?>>Last 30 Days</option>
                                <option value="90_days" <?php selected($date_filter, '90_days'); ?>>Last 90 Days</option>
                                <option value="custom" <?php selected($date_filter, 'custom'); ?>>Custom Range</option>
                            </select>
                        </div>
                        
                        <!-- Per Page -->
                        <div>
                            <label style="display: block; font-weight: 500; margin-bottom: 5px;">Per Page</label>
                            <select name="per_page" style="width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px;">
                                <option value="10" <?php selected($per_page, 10); ?>>10</option>
                                <option value="20" <?php selected($per_page, 20); ?>>20</option>
                                <option value="50" <?php selected($per_page, 50); ?>>50</option>
                                <option value="100" <?php selected($per_page, 100); ?>>100</option>
                            </select>
                        </div>
                        
                        <!-- Filter Button -->
                        <div>
                            <button type="submit" class="button button-primary">Filter</button>
                        </div>
                    </div>
                    
                    <!-- Custom Date Range -->
                    <div id="custom-dates" style="display: <?php echo $date_filter === 'custom' ? 'block' : 'none'; ?>; margin-bottom: 15px;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                            <div>
                                <label style="display: block; font-weight: 500; margin-bottom: 5px;">Start Date</label>
                                <input type="date" name="custom_start" value="<?php echo esc_attr($custom_start); ?>" 
                                       style="width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px;">
                            </div>
                            <div>
                                <label style="display: block; font-weight: 500; margin-bottom: 5px;">End Date</label>
                                <input type="date" name="custom_end" value="<?php echo esc_attr($custom_end); ?>" 
                                       style="width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px;">
                            </div>
                        </div>
                    </div>
                </form>
                
                <!-- Actions -->
                <div style="display: flex; gap: 10px; justify-content: space-between; align-items: center; padding-top: 15px; border-top: 1px solid #eee;">
                    <div>
                        <?php if ($total_sessions > 0): ?>
                            <a href="<?php echo wp_nonce_url(add_query_arg(['action' => 'export'] + $_GET), 'dehum_export', 'export_nonce'); ?>" 
                               class="button">📊 Export CSV</a>
                        <?php endif; ?>
                    </div>
                    
                    <div>
                        <form method="POST" style="display: inline;" onsubmit="return confirm('Are you sure you want to delete conversations older than 90 days?');">
                            <?php wp_nonce_field('dehum_bulk_actions', 'bulk_nonce'); ?>
                            <input type="hidden" name="bulk_action" value="delete_old">
                            <button type="submit" class="button button-secondary">🗑️ Delete Old (90+ days)</button>
                        </form>
                    </div>
                </div>
            </div>

            <?php if (empty($sessions)): ?>
                <div style="text-align: center; padding: 60px 20px; background: #f8f9fa; border-radius: 8px; color: #6c757d;">
                    <div style="font-size: 48px; margin-bottom: 20px;">💬</div>
                    <h3>No conversations yet</h3>
                    <p>Chat conversations will appear here once users start using the widget.</p>
                </div>
            <?php else: ?>
                
                <!-- Conversations List -->
                <div id="conversations-list">
                    <?php foreach ($sessions as $session): ?>
                        <div class="conversation-card" data-session="<?php echo esc_attr($session->session_id); ?>">
                            <div class="card-header">
                                <div class="conversation-info">
                                    <div class="conversation-preview">
                                        <?php echo esc_html(wp_trim_words($session->first_question, 12)); ?>
                                    </div>
                                    <div class="conversation-meta">
                                        <span class="message-count"><?php echo intval($session->message_count); ?> messages</span>
                                        <span class="time-ago"><?php echo human_time_diff(strtotime($session->last_message), current_time('timestamp')); ?> ago</span>
                                        <?php if ($session->user_ip): ?>
                                            <span class="user-ip"><?php echo esc_html($session->user_ip); ?></span>
                                        <?php endif; ?>
                                    </div>
                                </div>
                                <div class="expand-icon">
                                    <span class="dashicons dashicons-arrow-down-alt2"></span>
                                </div>
                            </div>
                            
                            <div class="card-content" id="content-<?php echo esc_attr($session->session_id); ?>" style="display: none;">
                                <div class="loading-state">
                                    <div class="loading-spinner"></div>
                                    <span>Loading conversation...</span>
                                </div>
                            </div>
                        </div>
                    <?php endforeach; ?>
                </div>
                
                <!-- Pagination -->
                <?php if ($total_pages > 1): ?>
                    <div class="dehum-pagination" style="margin-top: 30px; text-align: center;">
                        <?php
                        $pagination_args = array_merge($_GET, ['page' => 'dehum-mvp-logs']);
                        
                        // Previous page
                        if ($paged > 1) {
                            $prev_args = array_merge($pagination_args, ['paged' => $paged - 1]);
                            echo '<a href="' . esc_url(add_query_arg($prev_args, admin_url('tools.php'))) . '" class="button">← Previous</a> ';
                        }
                        
                        // Page numbers
                        $start_page = max(1, $paged - 2);
                        $end_page = min($total_pages, $paged + 2);
                        
                        if ($start_page > 1) {
                            $first_args = array_merge($pagination_args, ['paged' => 1]);
                            echo '<a href="' . esc_url(add_query_arg($first_args, admin_url('tools.php'))) . '" class="button">1</a> ';
                            if ($start_page > 2) echo '<span style="margin: 0 5px;">...</span> ';
                        }
                        
                        for ($i = $start_page; $i <= $end_page; $i++) {
                            if ($i == $paged) {
                                echo '<span class="button button-primary" style="margin: 0 2px;">' . $i . '</span> ';
                            } else {
                                $page_args = array_merge($pagination_args, ['paged' => $i]);
                                echo '<a href="' . esc_url(add_query_arg($page_args, admin_url('tools.php'))) . '" class="button" style="margin: 0 2px;">' . $i . '</a> ';
                            }
                        }
                        
                        if ($end_page < $total_pages) {
                            if ($end_page < $total_pages - 1) echo '<span style="margin: 0 5px;">...</span> ';
                            $last_args = array_merge($pagination_args, ['paged' => $total_pages]);
                            echo '<a href="' . esc_url(add_query_arg($last_args, admin_url('tools.php'))) . '" class="button">' . $total_pages . '</a> ';
                        }
                        
                        // Next page
                        if ($paged < $total_pages) {
                            $next_args = array_merge($pagination_args, ['paged' => $paged + 1]);
                            echo ' <a href="' . esc_url(add_query_arg($next_args, admin_url('tools.php'))) . '" class="button">Next →</a>';
                        }
                        ?>
                        
                        <div style="margin-top: 10px; color: #666; font-size: 13px;">
                            Showing <?php echo (($paged - 1) * $per_page) + 1; ?> - <?php echo min($paged * $per_page, $total_sessions); ?> 
                            of <?php echo number_format($total_sessions); ?> sessions
                        </div>
                    </div>
                <?php endif; ?>
                
            <?php endif; ?>
        </div>

        <style>
        /* Modern Card Styling */
        #conversations-list {
            margin-top: 20px;
        }

        .conversation-card {
            background: white;
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            margin-bottom: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            transition: all 0.2s ease;
        }

        .conversation-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border-color: #c3c4c7;
        }

        .card-header {
            padding: 16px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background-color 0.2s ease;
        }

        .card-header:hover {
            background-color: #f8f9fa;
        }

        .conversation-info {
            flex: 1;
        }

        .conversation-preview {
            font-size: 15px;
            font-weight: 500;
            color: #1d2327;
            margin-bottom: 6px;
            line-height: 1.4;
        }

        .conversation-meta {
            display: flex;
            gap: 12px;
            font-size: 13px;
            color: #646970;
        }

        .message-count {
            background: #2271b1;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 500;
        }

        .user-ip {
            font-family: monospace;
            background: #f6f7f7;
            padding: 2px 6px;
            border-radius: 4px;
        }

        .expand-icon {
            color: #646970;
            transition: transform 0.2s ease;
        }

        .expand-icon.expanded {
            transform: rotate(180deg);
        }

        .card-content {
            border-top: 1px solid #f0f0f1;
            background: #fafafa;
        }

        .loading-state {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 30px;
            gap: 12px;
            color: #646970;
        }

        .loading-spinner {
            width: 20px;
            height: 20px;
            border: 2px solid #f0f0f1;
            border-top: 2px solid #2271b1;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .chat-messages {
            padding: 20px;
            max-height: 400px;
            overflow-y: auto;
        }

        .chat-message {
            margin-bottom: 16px;
            display: flex;
            flex-direction: column;
        }

        .message-user {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
        }

        .message-assistant {
            background: #f1f8e9;
            border-left: 4px solid #4caf50;
            padding: 12px 16px;
            border-radius: 8px;
        }

        .message-header {
            font-size: 12px;
            color: #646970;
            margin-bottom: 6px;
            font-weight: 500;
        }

        .message-text {
            line-height: 1.5;
            color: #1d2327;
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            .conversation-meta {
                flex-direction: column;
                gap: 6px;
            }
            
            .card-header {
                padding: 12px 16px;
            }
            
            .dehum-filters > form > div:first-child {
                grid-template-columns: 1fr;
                gap: 10px;
            }
        }
        </style>

        <script>
        function toggleCustomDates(value) {
            const customDates = document.getElementById('custom-dates');
            customDates.style.display = value === 'custom' ? 'block' : 'none';
        }
        </script>


        
        <?php
    }
    
    /**
     * Handle bulk actions for conversation management
     */
    private function handle_bulk_actions() {
        $action = sanitize_text_field($_POST['bulk_action']);
        
        switch ($action) {
            case 'delete_old':
                $this->delete_old_conversations();
                break;
        }
    }
    
    /**
     * Delete conversations older than 90 days
     */
    private function delete_old_conversations() {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        $deleted = $wpdb->query("
            DELETE FROM $table_name 
            WHERE timestamp < DATE_SUB(NOW(), INTERVAL 90 DAY)
        ");
        
        if ($deleted !== false) {
            add_action('admin_notices', function() use ($deleted) {
                echo '<div class="notice notice-success is-dismissible"><p>Deleted ' . number_format($deleted) . ' old conversation messages.</p></div>';
            });
        } else {
            add_action('admin_notices', function() {
                echo '<div class="notice notice-error is-dismissible"><p>Error deleting old conversations.</p></div>';
            });
        }
    }
    
    /**
     * Export conversations to CSV
     */
    private function export_conversations() {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        // Get current filters
        $search = isset($_GET['search']) ? sanitize_text_field($_GET['search']) : '';
        $date_filter = isset($_GET['date_filter']) ? sanitize_text_field($_GET['date_filter']) : '';
        $custom_start = isset($_GET['custom_start']) ? sanitize_text_field($_GET['custom_start']) : '';
        $custom_end = isset($_GET['custom_end']) ? sanitize_text_field($_GET['custom_end']) : '';
        
        // Build WHERE clause (same as in admin_logs_page)
        $where_conditions = [];
        $where_params = [];
        
        if (!empty($search)) {
            // Use same search logic as admin page
            if (strlen($search) >= 3 && !preg_match('/[*%_]/', $search)) {
                $where_conditions[] = "MATCH (message, response) AGAINST (%s IN NATURAL LANGUAGE MODE)";
                $where_params[] = $search;
            } else {
                $where_conditions[] = "(message LIKE %s OR response LIKE %s)";
                $where_params[] = '%' . $wpdb->esc_like($search) . '%';
                $where_params[] = '%' . $wpdb->esc_like($search) . '%';
            }
        }
        
        if (!empty($date_filter)) {
            switch ($date_filter) {
                case '7_days':
                    $where_conditions[] = "timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)";
                    break;
                case '30_days':
                    $where_conditions[] = "timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)";
                    break;
                case '90_days':
                    $where_conditions[] = "timestamp >= DATE_SUB(NOW(), INTERVAL 90 DAY)";
                    break;
                case 'custom':
                    if (!empty($custom_start)) {
                        $where_conditions[] = "DATE(timestamp) >= %s";
                        $where_params[] = $custom_start;
                    }
                    if (!empty($custom_end)) {
                        $where_conditions[] = "DATE(timestamp) <= %s";
                        $where_params[] = $custom_end;
                    }
                    break;
            }
        }
        
        $where_clause = !empty($where_conditions) ? 'WHERE ' . implode(' AND ', $where_conditions) : '';
        
        // Get conversation data
        $query = "
            SELECT 
                session_id,
                message,
                response,
                user_ip,
                timestamp
            FROM $table_name 
            $where_clause
            ORDER BY timestamp DESC
        ";
        
        if (!empty($where_params)) {
            $conversations = $wpdb->get_results($wpdb->prepare($query, $where_params));
        } else {
            $conversations = $wpdb->get_results($query);
        }
        
        // Generate filename
        $filename = 'dehumidifier-conversations-' . date('Y-m-d-H-i-s') . '.csv';
        
        // Set headers for CSV download
        header('Content-Type: text/csv');
        header('Content-Disposition: attachment; filename="' . $filename . '"');
        header('Pragma: no-cache');
        header('Expires: 0');
        
        // Create file pointer
        $output = fopen('php://output', 'w');
        
        // CSV headers
        fputcsv($output, [
            'Session ID',
            'Date/Time', 
            'User Message',
            'AI Response',
            'User IP',
            'Message Length',
            'Response Length'
        ]);
        
        // CSV data
        foreach ($conversations as $conv) {
            fputcsv($output, [
                $conv->session_id,
                $conv->timestamp,
                $conv->message,
                $conv->response,
                $conv->user_ip,
                strlen($conv->message),
                strlen($conv->response)
            ]);
        }
        
        fclose($output);
        exit;
    }
    
    /**
     * Step 5.3: Add dashboard widget for conversation stats
     */
    public function add_dashboard_widget() {
        wp_add_dashboard_widget(
            'dehum_mvp_stats',
            'Dehumidifier Assistant Activity',
            [$this, 'dashboard_widget_content']
        );
    }
    
    /**
     * Step 5.3: Dashboard widget content
     */
    public function dashboard_widget_content() {
        global $wpdb;
        
        $table_name = $this->get_conversations_table_name();
        
        // Get stats
        $total_conversations = $wpdb->get_var("SELECT COUNT(*) FROM $table_name");
        $total_sessions = $wpdb->get_var("SELECT COUNT(DISTINCT session_id) FROM $table_name");
        $today_conversations = $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM $table_name WHERE DATE(timestamp) = %s", 
            current_time('Y-m-d')
        ));
        $this_week_conversations = $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM $table_name WHERE timestamp >= %s", 
            date('Y-m-d', strtotime('monday this week'))
        ));
        
        // Get recent session
        $latest_conversation = $wpdb->get_row(
            "SELECT * FROM $table_name ORDER BY timestamp DESC LIMIT 1"
        );
        
        ?>
        <div class="dehum-dashboard-stats">
            <div class="stats-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                <div>
                    <h4 style="margin: 0 0 5px 0;">Total Activity</h4>
                    <p style="margin: 0; font-size: 24px; font-weight: bold; color: #0073aa;">
                        <?php echo number_format($total_conversations); ?>
                    </p>
                    <small style="color: #666;">messages in <?php echo number_format($total_sessions); ?> sessions</small>
                </div>
                <div>
                    <h4 style="margin: 0 0 5px 0;">Recent Activity</h4>
                    <p style="margin: 0; font-size: 18px; font-weight: bold;">
                        Today: <?php echo number_format($today_conversations); ?> messages
                    </p>
                    <small style="color: #666;">This week: <?php echo number_format($this_week_conversations); ?> messages</small>
                </div>
            </div>
            
            <?php if ($latest_conversation): ?>
                <div style="background: #f9f9f9; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                    <h4 style="margin: 0 0 5px 0;">Latest Conversation</h4>
                    <p style="margin: 0 0 5px 0; font-size: 13px;">
                        <strong>User:</strong> <?php echo esc_html(wp_trim_words($latest_conversation->message, 12)); ?>
                    </p>
                    <p style="margin: 0 0 5px 0; font-size: 13px;">
                        <strong>Assistant:</strong> <?php echo esc_html(wp_trim_words($latest_conversation->response, 12)); ?>
                    </p>
                    <small style="color: #666;">
                        <?php echo esc_html(human_time_diff(strtotime($latest_conversation->timestamp), current_time('timestamp'))); ?> ago
                    </small>
                </div>
            <?php endif; ?>
            
            <p style="text-align: center; margin: 0;">
                <a href="<?php echo admin_url('tools.php?page=dehum-mvp-logs'); ?>" class="button button-primary">
                    View All Conversations
                </a>
            </p>
        </div>
        <?php
    }
    
    public function activate() {
        // Step 5.1: Create database table for conversation logging
        $this->create_conversations_table();
        
        // Add activation timestamp for testing
        update_option('dehum_mvp_activated_at', current_time('mysql'));
        update_option('dehum_mvp_version', DEHUM_MVP_VERSION);
        
        // Log successful activation for debugging
        if (defined('WP_DEBUG') && WP_DEBUG) {
            error_log('Dehumidifier Assistant MVP: Plugin activated successfully at ' . current_time('mysql'));
        }
        
        flush_rewrite_rules();
    }
    
    /**
     * Step 5.1: Create conversations table
     * Schema: id, session_id, message, response, timestamp
     */
    private function create_conversations_table() {
        global $wpdb;
        
        $table_name = $wpdb->prefix . 'dehum_conversations';
        
        // Create table SQL with proper WordPress schema
        $charset_collate = $wpdb->get_charset_collate();
        
        $sql = "CREATE TABLE $table_name (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
            session_id varchar(255) NOT NULL,
            message text NOT NULL,
            response text NOT NULL,
            user_ip varchar(45) DEFAULT NULL,
            timestamp datetime DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY session_id (session_id),
            KEY timestamp (timestamp),
            KEY user_ip (user_ip),
            FULLTEXT KEY search_content (message, response)
        ) $charset_collate;";
        
        // Include WordPress upgrade functions
        require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
        
        // Create/update table using dbDelta (WordPress standard)
        $result = dbDelta($sql);
        
        // Log table creation result
        if (defined('WP_DEBUG') && WP_DEBUG) {
            error_log('Dehum MVP: Database table creation result: ' . print_r($result, true));
            
            // Verify table exists
            $table_exists = $wpdb->get_var("SHOW TABLES LIKE '$table_name'") === $table_name;
            error_log('Dehum MVP: Table exists after creation: ' . ($table_exists ? 'YES' : 'NO'));
        }
        
        // Store database version for future migrations
        update_option('dehum_mvp_db_version', '1.0');
    }
    
    /**
     * Step 5.1: Get conversations table name
     * Helper function for consistent table naming
     */
    private function get_conversations_table_name() {
        global $wpdb;
        return $wpdb->prefix . 'dehum_conversations';
    }
    
    public function deactivate() {
        // Plugin deactivation tasks
        
        // Log deactivation for debugging
        if (defined('WP_DEBUG') && WP_DEBUG) {
            error_log('Dehumidifier Assistant MVP: Plugin deactivated at ' . current_time('mysql'));
        }
        
        // Note: We keep activation timestamp for troubleshooting
        // Only delete on uninstall, not deactivation
        
        flush_rewrite_rules();
    }
}

// Initialize the plugin
new DehumidifierAssistantMVP(); 