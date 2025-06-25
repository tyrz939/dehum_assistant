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
        
        // Add chat widget to footer
        add_action('wp_footer', [$this, 'render_chat_widget']);
        
        // AJAX handlers for chat functionality
        add_action('wp_ajax_dehum_mvp_chat', [$this, 'handle_chat_message']);
        add_action('wp_ajax_nopriv_dehum_mvp_chat', [$this, 'handle_chat_message']);
        
        // Admin notices for Step 1.2 testing
        add_action('admin_notices', [$this, 'admin_activation_notice']);
        
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
                    <button id="dehum-mvp-close-chat">&times;</button>
                </div>
                <div class="chat-messages" id="dehum-mvp-chat-messages">
                    <div class="assistant-message">
                        Hello! I'm your Dehumidifier Assistant. Ask me anything about sizing or model selection.
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
                    <small>Powered by AI • <span id="char-count">0</span>/400 characters</small>
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
        
        $user_input = sanitize_textarea_field($_POST['message']);
        
        // Basic input validation
        if (empty($user_input) || strlen($user_input) > 400) {
            wp_send_json_error(['message' => 'Invalid message length']);
        }
        
        // Step 3.1: Send to n8n webhook
        $n8n_response = $this->call_n8n_webhook($user_input);
        
        if ($n8n_response && isset($n8n_response['success']) && $n8n_response['success']) {
            wp_send_json_success([
                'response' => $n8n_response['response'],
                'timestamp' => current_time('mysql')
            ]);
        } else {
            // Fallback for n8n failures - return original message for retry
            wp_send_json_error([
                'message' => 'Sorry, I\'m having trouble processing your request right now. Please try again in a moment.',
                'original_message' => $user_input
            ]);
        }
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
            ?>
            <div class="notice notice-success is-dismissible">
                <p>
                    <strong>✅ Dehumidifier Assistant MVP</strong> is active! 
                    Visit your website frontend to see the chat button. 
                    <a href="<?php echo home_url(); ?>" target="_blank">Test it now →</a>
                </p>
            </div>
            <?php
        }
    }
    
    public function activate() {
        // Plugin activation tasks
        // TODO: Create database table (Step 5.1)
        
        // Add activation timestamp for testing
        update_option('dehum_mvp_activated_at', current_time('mysql'));
        update_option('dehum_mvp_version', DEHUM_MVP_VERSION);
        
        // Log successful activation for debugging
        if (defined('WP_DEBUG') && WP_DEBUG) {
            error_log('Dehumidifier Assistant MVP: Plugin activated successfully at ' . current_time('mysql'));
        }
        
        flush_rewrite_rules();
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