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
    }

    /**
     * Handle the incoming chat message from the frontend.
     */
    public function handle_chat_message() {
        if (!wp_verify_nonce($_POST['nonce'], DEHUM_MVP_CHAT_NONCE)) {
            wp_send_json_error(['message' => 'Security check failed'], 403);
        }

        $rate_limit_check = $this->check_rate_limit();
        if (!$rate_limit_check['allowed']) {
            wp_send_json_error(['message' => $rate_limit_check['message'], 'rate_limited' => true], 429);
        }

        $user_input = sanitize_textarea_field($_POST['message']);
        if (empty($user_input) || strlen($user_input) > DEHUM_MVP_MESSAGE_MAX_LENGTH) {
            wp_send_json_error(['message' => 'Invalid message length']);
        }

        $session_id = $this->get_or_create_session_id();
        $n8n_response = $this->call_n8n_webhook($user_input);

        if ($n8n_response && isset($n8n_response['success']) && $n8n_response['success']) {
            $this->increment_rate_limit_counter();
            $this->db->log_conversation($session_id, $user_input, $n8n_response['response'], $this->get_user_ip());

            wp_send_json_success([
                'response'   => $n8n_response['response'],
                'timestamp'  => current_time('mysql'),
                'session_id' => $session_id
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
     * Call the n8n webhook with the user's message.
     *
     * @param string $message The user's message.
     * @return array|false The decoded JSON response from n8n or false on failure.
     */
    private function call_n8n_webhook($message) {
        $webhook_url = get_option('dehum_mvp_n8n_webhook_url');
        if (empty($webhook_url)) {
            error_log('Dehum MVP: n8n webhook URL is not set in settings.');
            return false;
        }

        $body = wp_json_encode(['message' => $message]);
        $headers = ['Content-Type' => 'application/json'];
        
        $user = get_option('dehum_mvp_n8n_webhook_user');
        $pass_encrypted = get_option('dehum_mvp_n8n_webhook_pass_encrypted');
        if (!empty($user) && !empty($pass_encrypted)) {
            // Decrypt the password for use
            $pass = $this->decrypt_credential($pass_encrypted);
            if ($pass !== false) {
                $headers['Authorization'] = 'Basic ' . base64_encode($user . ':' . $pass);
            }
        }

        $args = [
            'body'        => $body,
            'headers'     => $headers,
            'timeout'     => DEHUM_MVP_WEBHOOK_TIMEOUT,
            'data_format' => 'body'
        ];
        
        $response = wp_remote_post($webhook_url, $args);
        
        if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200) {
             error_log('Dehum MVP: n8n webhook error: ' . (is_wp_error($response) ? $response->get_error_message() : wp_remote_retrieve_response_code($response)));
            return false;
        }

        $data = json_decode(wp_remote_retrieve_body($response), true);
        return json_last_error() === JSON_ERROR_NONE ? $data : false;
    }

    /**
     * Check rate limiting for the current user's IP.
     *
     * @return array Status of the rate limit check.
     */
    private function check_rate_limit() {
        $user_ip = $this->get_user_ip();
        $transient_key = 'dehum_mvp_rate_limit_' . md5($user_ip);
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
        $user_ip = $this->get_user_ip();
        $transient_key = 'dehum_mvp_rate_limit_' . md5($user_ip);
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
        if (empty($credential)) {
            return '';
        }
        
        // Use WordPress auth key as encryption key
        $key = defined('AUTH_KEY') ? AUTH_KEY : 'dehum_mvp_fallback_key';
        $iv = openssl_random_pseudo_bytes(16);
        $encrypted = openssl_encrypt($credential, 'AES-256-CBC', $key, 0, $iv);
        
        // Combine IV and encrypted data, then base64 encode
        return base64_encode($iv . $encrypted);
    }

    /**
     * Decrypt a credential using WordPress salts.
     *
     * @param string $encrypted_credential The encrypted credential.
     * @return string|false The decrypted credential or false on failure.
     */
    private function decrypt_credential($encrypted_credential) {
        if (empty($encrypted_credential)) {
            return false;
        }
        
        $key = defined('AUTH_KEY') ? AUTH_KEY : 'dehum_mvp_fallback_key';
        $data = base64_decode($encrypted_credential);
        
        if (strlen($data) < 16) {
            return false;
        }
        
        $iv = substr($data, 0, 16);
        $encrypted = substr($data, 16);
        
        return openssl_decrypt($encrypted, 'AES-256-CBC', $key, 0, $iv);
    }

    /**
     * Migrate old plain text password to encrypted format.
     * Called during plugin initialization if needed.
     */
    public static function migrate_credentials() {
        $old_pass = get_option('dehum_mvp_n8n_webhook_pass');
        if (!empty($old_pass) && !get_option('dehum_mvp_n8n_webhook_pass_encrypted')) {
            $ajax_instance = new self(new Dehum_MVP_Database());
            $encrypted_pass = $ajax_instance->encrypt_credential($old_pass);
            
            update_option('dehum_mvp_n8n_webhook_pass_encrypted', $encrypted_pass);
            delete_option('dehum_mvp_n8n_webhook_pass'); // Remove plain text version
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
} 