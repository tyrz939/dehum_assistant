<?php
// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Class Dehum_MVP_Ajax
 *
 * Handles all AJAX functionality for the plugin.
 */
class Dehum_MVP_Ajax {

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
        $this->add_ajax_hooks();
    }

    /**
     * Add the WordPress AJAX hooks.
     */
    private function add_ajax_hooks() {
        add_action('wp_ajax_' . DEHUM_MVP_AJAX_CHAT, [$this, 'handle_chat_message']);
        add_action('wp_ajax_nopriv_' . DEHUM_MVP_AJAX_CHAT, [$this, 'handle_chat_message']);
        add_action('wp_ajax_' . DEHUM_MVP_AJAX_SESSION_DETAILS, [$this, 'handle_get_session_details']);
        
        // Add individual session delete handler
        add_action('wp_ajax_dehum_mvp_delete_session', [$this, 'handle_delete_session_ajax']);
        // New session sync handlers
        add_action('wp_ajax_dehum_get_session', [$this, 'handle_get_session']);
        add_action('wp_ajax_dehum_save_session', [$this, 'handle_save_session']);
        add_action('wp_ajax_dehum_get_nonce', [$this, 'handle_get_nonce']);
        
        // New streaming support handlers
        add_action('wp_ajax_dehum_get_ai_service_url', [$this, 'handle_get_ai_service_url']);
        add_action('wp_ajax_nopriv_dehum_get_ai_service_url', [$this, 'handle_get_ai_service_url']);
        add_action('wp_ajax_dehum_get_ai_service_auth', [$this, 'handle_get_ai_service_auth']);
        add_action('wp_ajax_nopriv_dehum_get_ai_service_auth', [$this, 'handle_get_ai_service_auth']);
        add_action('wp_ajax_dehum_mvp_save_conversation', [$this, 'handle_save_conversation']);
        add_action('wp_ajax_nopriv_dehum_mvp_save_conversation', [$this, 'handle_save_conversation']);
        add_action('wp_ajax_dehum_mvp_bulk_delete_sessions', [$this, 'handle_bulk_delete_sessions']);
    }

    /**
     * Handle the incoming chat message from the frontend.
     */
    public function handle_chat_message() {
        // NEW: Access control toggle
        if (get_option('dehum_mvp_chat_logged_in_only') && !is_user_logged_in()) {
            wp_send_json_error(['message' => 'Chat is currently restricted to logged-in users only.'], 403);
        }
        if (!wp_verify_nonce($_POST['nonce'], DEHUM_MVP_CHAT_NONCE)) {
            wp_send_json_error(['message' => 'Security check failed'], 403);
        }

        $rate_limit_check = $this->check_rate_limit();
        if (!$rate_limit_check['allowed']) {
            wp_send_json_error(['message' => $rate_limit_check['message'], 'rate_limited' => true], 429);
        }
        $this->increment_rate_limit_counter();

        $user_input = sanitize_textarea_field($_POST['message']);
        $length_func = function_exists('mb_strlen') ? 'mb_strlen' : 'strlen';
        if (empty($user_input) || $length_func($user_input) > DEHUM_MVP_MESSAGE_MAX_LENGTH) {
            wp_send_json_error(['message' => sprintf('Message exceeds %d characters.', DEHUM_MVP_MESSAGE_MAX_LENGTH)]);
        }

        $session_id = $this->get_or_create_session_id();
        
        $ai_service_url = get_option('dehum_mvp_ai_service_url');
        if (empty($ai_service_url)) {
            wp_send_json_error([
                'message' => 'AI service not configured. Please set it in settings.',
                'original_message' => $user_input
            ]);
            wp_die();
        }

        // Always use Python AI Service
        $response = $this->call_ai_service($user_input, $session_id);

        if ($response && isset($response['success']) && $response['success']) {
            $this->db->log_conversation($session_id, $user_input, $response['response'], $this->get_user_ip());

            wp_send_json_success([
                'response'   => $response['response'],
                'timestamp'  => current_time('mysql'),
                'session_id' => $response['session_id'] ?? $session_id,
                'recommendations' => $response['recommendations'] ?? [],
                'function_calls' => $response['function_calls'] ?? []
            ]);
        } else {
            wp_send_json_error([
                'message' => 'Sorry, I\'m having trouble processing your request right now. Please try again in a moment.',
                'original_message' => $user_input
            ]);
        }
        wp_die();
    }

    /**
     * Handle the admin request to get details for a specific session.
     */
    public function handle_get_session_details() {
        if (!wp_verify_nonce($_POST['nonce'], DEHUM_MVP_SESSION_NONCE)) {
            wp_send_json_error(['message' => 'Security check failed'], 403);
        }

        if (!current_user_can('manage_options')) {
            wp_send_json_error(['message' => 'Insufficient permissions'], 403);
        }

        $session_id = sanitize_text_field($_POST['session_id']);
        if (empty($session_id)) {
            wp_send_json_error(['message' => 'Session ID required']);
        }

        $messages = $this->db->get_session_details($session_id);
        if (empty($messages)) {
            wp_send_json_error(['message' => 'No messages found for this session']);
        }

        $formatted_messages = array_map(function($msg) {
            return [
                'id'        => intval($msg->id),
                'message'   => $msg->message,
                'response'  => $msg->response,
                'timestamp' => date('M j, H:i:s', strtotime($msg->timestamp)),
                'user_ip'   => $msg->user_ip
            ];
        }, $messages);

        wp_send_json_success($formatted_messages);
        wp_die();
    }
    
    /**
     * Get or create a session ID for conversation threading.
     *
     * @return string The session ID.
     */
    private function get_or_create_session_id() {
        if (!empty($_POST['session_id'])) {
            return sanitize_text_field($_POST['session_id']);
        }
        return current_time('Y-m-d_H-i-s') . '_' . wp_generate_password(8, false);
    }

    /**
     * Call the Python AI service with the user's message.
     *
     * @param string $message The user's message.
     * @return array|false The decoded JSON response from the AI service or false on failure.
     */
    private function call_ai_service($message, $session_id = null) {
        $service_url = get_option('dehum_mvp_ai_service_url');
        if (empty($service_url)) {
            error_log('Dehum MVP: AI service URL is not set in settings.');
            return false;
        }

        // Use the regular endpoint for WordPress (wp_remote_post doesn't handle SSE properly)
        $service_url = rtrim($service_url, '/') . '/chat';

        // Reuse provided session ID if supplied to ensure consistent threading
        $session_id = $session_id ?: $this->get_or_create_session_id();
        
        $body = wp_json_encode([
            'message'    => $message,
            'session_id' => $session_id,
            'user_id'    => ($uid = get_current_user_id()) ? (string) $uid : null
        ]);
        
        $headers = ['Content-Type' => 'application/json'];
        
        // Add API key authentication if configured
        $api_key_encrypted = get_option('dehum_mvp_ai_service_key_encrypted');
        if (!empty($api_key_encrypted)) {
            $api_key = $this->decrypt_credential($api_key_encrypted);
            if ($api_key !== false) {
                $headers['Authorization'] = 'Bearer ' . $api_key;
            }
        }

        $args = [
            'body'        => $body,
            'headers'     => $headers,
            'timeout'     => DEHUM_MVP_WEBHOOK_TIMEOUT,
            'data_format' => 'body'
        ];
        
        $max_retries = 3;
        $retry_delay = 1; // seconds
        $response = false;
        
        for ($attempt = 1; $attempt <= $max_retries; $attempt++) {
            $response = wp_remote_post($service_url, $args);
            
            if (!is_wp_error($response) && wp_remote_retrieve_response_code($response) === 200) {
                break; // Success
            }
            
            error_log('Dehum MVP: AI service attempt ' . $attempt . ' failed. Retrying in ' . $retry_delay . ' seconds.');
            sleep($retry_delay);
            $retry_delay *= 2; // Exponential backoff
        }
        
        if (is_wp_error($response)) {
            error_log('Dehum MVP: AI service error: ' . $response->get_error_message());
            return false;
        }
        
        $response_code = wp_remote_retrieve_response_code($response);
        if ($response_code !== 200) {
            error_log('Dehum MVP: AI service HTTP error: ' . $response_code);
            return false;
        }

        $data = json_decode(wp_remote_retrieve_body($response), true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            error_log('Dehum MVP: AI service JSON decode error: ' . json_last_error_msg());
            return false;
        }
        
        // Transform the Python service response to match the expected format
        if (isset($data['message'])) {
            return [
                'success' => true,
                'response' => $data['message'],
                'session_id' => $data['session_id'] ?? $session_id,
                'timestamp' => $data['timestamp'] ?? current_time('mysql'),
                'recommendations' => $data['recommendations'] ?? [],
                'function_calls' => $data['function_calls'] ?? []
            ];
        }
        
        return false;
    }

    /**
     * Check rate limiting for the current user's IP.
     *
     * @return array Status of the rate limit check.
     */
    private function check_rate_limit() {
        $epoch = (int) get_option('dehum_mvp_rate_epoch', 1);
        $user_ip = $this->get_user_ip();
        $transient_key = 'dehum_mvp_rate_limit_' . $epoch . '_' . md5($user_ip);
        $current_count = get_transient($transient_key);

        if ($current_count === false) {
            return ['allowed' => true];
        }

        if ($current_count >= DEHUM_MVP_DAILY_MESSAGE_LIMIT) {
            return [
                'allowed' => false,
                'message' => 'Daily message limit reached. Please try again tomorrow.'
            ];
        }

        return ['allowed' => true];
    }

    /**
     * Increment the rate limit counter for the current user's IP.
     */
    private function increment_rate_limit_counter() {
        $epoch = (int) get_option('dehum_mvp_rate_epoch', 1);
        $user_ip = $this->get_user_ip();
        $transient_key = 'dehum_mvp_rate_limit_' . $epoch . '_' . md5($user_ip);
        $current_count = get_transient($transient_key);

        $new_count = ($current_count === false) ? 1 : $current_count + 1;
        set_transient($transient_key, $new_count, DAY_IN_SECONDS);
    }
    
    /**
     * Get the user's IP address, supporting proxies.
     *
     * @return string The user's IP address.
     */
    private function get_user_ip() {
        $ip_headers = ['HTTP_CF_CONNECTING_IP', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'REMOTE_ADDR'];
        foreach ($ip_headers as $header) {
            if (!empty($_SERVER[$header])) {
                $ip = $_SERVER[$header];
                if (strpos($ip, ',') !== false) {
                    $ip = trim(explode(',', $ip)[0]);
                }
                if (filter_var($ip, FILTER_VALIDATE_IP)) {
                    return $ip;
                }
            }
        }
        return '127.0.0.1';
    }

    /**
     * Encrypt a credential using WordPress salts.
     *
     * @param string $credential The credential to encrypt.
     * @return string The encrypted credential.
     */
    public function encrypt_credential($credential) {
        // Rewritten to use libsodium so encrypt/decrypt are consistent
        if (empty($credential)) {
            return '';
        }
        // Ensure libsodium is available
        if (!function_exists('sodium_crypto_secretbox')) {
            error_log('Dehum MVP: libsodium not available for encryption');
            return '';
        }
        // Fetch or create key
        $key_b64 = get_option('dehum_mvp_encryption_key');
        if (empty($key_b64)) {
            $key_b64 = base64_encode(sodium_crypto_secretbox_keygen());
            update_option('dehum_mvp_encryption_key', $key_b64);
        }
        $key = base64_decode($key_b64);
        $nonce = random_bytes(SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        $cipher = sodium_crypto_secretbox($credential, $nonce, $key);
        // Return base64 of nonce + cipher so decrypt_credential can split
        return base64_encode($nonce . $cipher);
    }

    /**
     * Decrypt a credential using WordPress salts.
     *
     * @param string $encrypted_credential The encrypted credential.
     * @return string|false The decrypted credential or false on failure.
     */
    private function decrypt_credential($encrypted_value) {
        if (empty($encrypted_value)) {
            return '';
        }
        $keys = [
            get_option('dehum_mvp_encryption_key'),
            get_option('dehum_mvp_old_encryption_key') // Previous key for rotation
        ];
        foreach ($keys as $key) {
            if (empty($key)) continue;
            try {
                $decoded = base64_decode($encrypted_value);
                $nonce = mb_substr($decoded, 0, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES, '8bit');
                $ciphertext = mb_substr($decoded, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES, null, '8bit');
                return sodium_crypto_secretbox_open($ciphertext, $nonce, base64_decode($key));
            } catch (Exception $e) {
                // Try next key
            }
        }
        error_log('Dehum MVP: Decryption failed with all keys');
        return '';
    }

    /**
     * Migrate old plain text credentials to encrypted format.
     * Called during plugin initialization if needed.
     */
    public static function migrate_credentials() {
        // Migrate legacy n8n password
        $old_pass = get_option('dehum_mvp_n8n_webhook_pass');
        if (!empty($old_pass) && !get_option('dehum_mvp_n8n_webhook_pass_encrypted')) {
            $ajax_instance = new self(new Dehum_MVP_Database());
            $encrypted_pass = $ajax_instance->encrypt_credential($old_pass);
            
            update_option('dehum_mvp_n8n_webhook_pass_encrypted', $encrypted_pass);
            delete_option('dehum_mvp_n8n_webhook_pass'); // Remove plain text version
        }
        
        // Migrate AI service API key if needed (future use)
        $old_api_key = get_option('dehum_mvp_ai_service_key_plain');
        if (!empty($old_api_key) && !get_option('dehum_mvp_ai_service_key_encrypted')) {
            $ajax_instance = new self(new Dehum_MVP_Database());
            $encrypted_key = $ajax_instance->encrypt_credential($old_api_key);
            
            update_option('dehum_mvp_ai_service_key_encrypted', $encrypted_key);
            delete_option('dehum_mvp_ai_service_key_plain'); // Remove plain text version
        }
    }

    /**
     * Handle AJAX request to delete an individual session.
     */
    public function handle_delete_session_ajax() {
        // Verify nonce and permissions
        if (!wp_verify_nonce($_POST['nonce'], DEHUM_MVP_DELETE_SESSION_NONCE) || !current_user_can('manage_options')) {
            wp_send_json_error(['message' => __('Security check failed.', 'dehum-assistant-mvp')]);
            return;
        }

        if (empty($_POST['session_id'])) {
            wp_send_json_error(['message' => __('Session ID is required.', 'dehum-assistant-mvp')]);
            return;
        }

        $session_id = sanitize_text_field($_POST['session_id']);
        $deleted_count = $this->db->delete_session($session_id);
        
        if ($deleted_count !== false && $deleted_count > 0) {
            wp_send_json_success([
                'message' => sprintf(__('Successfully deleted conversation with %d messages.', 'dehum-assistant-mvp'), $deleted_count),
                'deleted_count' => $deleted_count
            ]);
        } else {
            wp_send_json_error(['message' => __('Failed to delete session or session not found.', 'dehum-assistant-mvp')]);
        }
    }

    public function handle_get_session() {
        error_log('Dehum MVP: handle_get_session called');
        // Verify API key from headers
        $api_key = $this->decrypt_credential(get_option('dehum_mvp_ai_service_key_encrypted'));
        error_log('Dehum MVP: Expected API key: ' . $api_key);
        error_log('Dehum MVP: Received Authorization: ' . ($_SERVER['HTTP_AUTHORIZATION'] ?? 'none'));
        if (empty($_SERVER['HTTP_AUTHORIZATION']) || $_SERVER['HTTP_AUTHORIZATION'] !== 'Bearer ' . $api_key) {
            error_log('Dehum MVP: Authentication failed');
            wp_send_json_error(['message' => 'Authentication failed'], 403);
        }
        // Verify nonce and permissions
        error_log('Dehum MVP: Received nonce: ' . ($_POST['nonce'] ?? 'none'));
        if (!wp_verify_nonce($_POST['nonce'], DEHUM_MVP_CHAT_NONCE)) {
            error_log('Dehum MVP: Nonce verification failed');
            wp_send_json_error(['message' => 'Security check failed'], 403);
        }
        $session_id = sanitize_text_field($_POST['session_id']);
        if (empty($session_id)) {
            wp_send_json_error(['message' => 'Session ID required']);
        }
        $history = $this->db->get_session_details($session_id);
        wp_send_json_success(['history' => $history]);
    }
    public function handle_save_session() {
        error_log('Dehum MVP: handle_save_session called');
        // Verify API key from headers
        $api_key = $this->decrypt_credential(get_option('dehum_mvp_ai_service_key_encrypted'));
        error_log('Dehum MVP: Expected API key: ' . $api_key);
        error_log('Dehum MVP: Received Authorization: ' . ($_SERVER['HTTP_AUTHORIZATION'] ?? 'none'));
        if (empty($_SERVER['HTTP_AUTHORIZATION']) || $_SERVER['HTTP_AUTHORIZATION'] !== 'Bearer ' . $api_key) {
            error_log('Dehum MVP: Authentication failed');
            wp_send_json_error(['message' => 'Authentication failed'], 403);
        }
        // Verify nonce and permissions
        error_log('Dehum MVP: Received nonce: ' . ($_POST['nonce'] ?? 'none'));
        if (!wp_verify_nonce($_POST['nonce'], DEHUM_MVP_CHAT_NONCE)) {
            error_log('Dehum MVP: Nonce verification failed');
            wp_send_json_error(['message' => 'Security check failed'], 403);
        }
        $session_id = sanitize_text_field($_POST['session_id']);
        $history = json_decode($_POST['history'], true); // Expect array of messages
        if (empty($session_id) || !is_array($history)) {
            wp_send_json_error(['message' => 'Invalid data']);
        }
        // Clear existing and insert new (or append)
        $this->db->delete_session($session_id);
        foreach ($history as $msg) {
            $this->db->log_conversation($session_id, $msg['message'], $msg['response'], $msg['user_ip']);
        }
        wp_send_json_success(['message' => 'Session saved']);
    }

    public function handle_get_nonce() {
        $api_key = $this->decrypt_credential(get_option('dehum_mvp_ai_service_key_encrypted'));
        if (empty($_SERVER['HTTP_AUTHORIZATION']) || $_SERVER['HTTP_AUTHORIZATION'] !== 'Bearer ' . $api_key) {
            wp_send_json_error(['message' => 'Authentication failed'], 403);
        }
        $nonce = wp_create_nonce(DEHUM_MVP_CHAT_NONCE);
        wp_send_json_success(['nonce' => $nonce]);
    }

    /**
     * Handle AJAX request to get AI service URL.
     */
    public function handle_get_ai_service_url() {
        $url = get_option('dehum_mvp_ai_service_url');
        wp_send_json_success(['url' => $url]);
    }

    /**
     * Handle AJAX request to get AI service authentication.
     */
    public function handle_get_ai_service_auth() {
        $api_key_encrypted = get_option('dehum_mvp_ai_service_key_encrypted');
        if (empty($api_key_encrypted)) {
            wp_send_json_success(['auth' => '']);
            return;
        }
        
        $decrypted_key = $this->decrypt_credential($api_key_encrypted);
        if ($decrypted_key === false) {
            wp_send_json_error(['message' => 'Failed to decrypt AI service authentication key.']);
            return;
        }
        
        wp_send_json_success(['auth' => 'Bearer ' . $decrypted_key]);
    }

    /**
     * Handle AJAX request to save a conversation.
     */
    public function handle_save_conversation() {
        // NEW: Access control toggle
        if (get_option('dehum_mvp_chat_logged_in_only') && !is_user_logged_in()) {
            wp_send_json_error(['message' => 'Chat is currently restricted to logged-in users only.'], 403);
        }
        
        // Use separate nonce for conversation saving to avoid reuse conflicts
        if (!wp_verify_nonce($_POST['nonce'], 'dehum_mvp_save_conversation')) {
            wp_send_json_error(['message' => 'Security check failed'], 403);
        }

        $user_message = sanitize_textarea_field($_POST['message']);
        // Preserve markdown/HTML formatting in AI responses while maintaining security
        $assistant_response = wp_kses_post($_POST['response']);
        $session_id = sanitize_text_field($_POST['session_id']);
        
        if (empty($user_message) || empty($assistant_response) || empty($session_id)) {
            wp_send_json_error(['message' => 'Missing required data']);
        }

        // Attempt to log the conversation, but always return success to client
        try {
            $result = $this->db->log_conversation($session_id, $user_message, $assistant_response, $this->get_user_ip());
            if (!$result) {
                error_log('Dehum MVP: Conversation save failed - Session: ' . $session_id . 
                         ', User Message Length: ' . strlen($user_message) . 
                         ', Response Length: ' . strlen($assistant_response) . 
                         ', IP: ' . $this->get_user_ip() . 
                         ', DB Error: ' . $GLOBALS['wpdb']->last_error);
            }
        } catch (Exception $e) {
            error_log('Dehum MVP: Conversation save exception - ' . $e->getMessage() . 
                      ', Session: ' . $session_id . 
                      ', Payload: ' . json_encode($_POST));
        }
        
        // Always return success to prevent UX disruption
        wp_send_json_success(['message' => 'Conversation saved']);
    }

    public function handle_bulk_delete_sessions() {
        if (!current_user_can('manage_options') || !wp_verify_nonce($_POST['nonce'], DEHUM_MVP_BULK_NONCE)) {
            wp_send_json_error(['message' => 'Access denied']);
        }
        $ids = array_map('sanitize_text_field', (array) ($_POST['session_ids'] ?? []));
        if (empty($ids)) {
            wp_send_json_error(['message' => 'No sessions selected']);
        }
        $deleted = $this->db->delete_sessions_bulk($ids);
        if ($deleted !== false) {
            wp_send_json_success([
                'message' => sprintf('Deleted %d conversations.', $deleted),
                'session_ids' => $ids
            ]);
        } else {
            wp_send_json_error(['message' => 'Delete failed']);
        }
    }
} 