<?php
// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Class Dehum_MVP_Frontend
 *
 * Handles all frontend-facing logic, including asset enqueuing
 * and rendering the chat widget.
 */
class Dehum_MVP_Frontend {

    /**
     * Constructor. Adds the necessary hooks for frontend functionality.
     */
    public function __construct() {
        add_action('wp_enqueue_scripts', [$this, 'enqueue_assets']);
        add_action('wp_footer', [$this, 'render_chat_widget']);
        
        // Combine duplicate AJAX actions for better maintainability
        add_action('wp_ajax_dehum_get_welcome_message', [$this, 'ajax_get_welcome_message']);
        add_action('wp_ajax_nopriv_dehum_get_welcome_message', [$this, 'ajax_get_welcome_message']);
        
        // Add hooks for extensibility
        do_action('dehum_mvp_frontend_init', $this);
    }

    /**
     * Get the welcome message content - centralized for easy editing
     * Allows filtering for customization
     */
    public function get_welcome_message() {
        $default_message = '<strong>Welcome! I\'m your dehumidifier sizing assistant.</strong><br>' .
               'I can help you with:<br>' .
               '• <strong>Sizing recommendations</strong> - Provide space details (length × width × height in meters), current humidity (RH%), and target humidity (RH%)<br>' .
               '• <strong>Product specifications</strong> - Ask about features, technical details, or performance data<br>' .
               '• <strong>Installation & maintenance</strong> - Questions about setup, operation, or troubleshooting<br><br>' .
               'Is this for a pool room or regular space? What can I help you with today?';
        
        /**
         * Filter the welcome message content
         * 
         * @param string $message The default welcome message
         */
        return apply_filters('dehum_mvp_welcome_message', $default_message);
    }

    /**
     * Check rate limiting for AJAX requests
     */
    private function check_rate_limit($action = 'default') {
        $transient_key = 'dehum_rate_limit_' . $action . '_' . $this->get_user_identifier();
        $requests = get_transient($transient_key);
        
        if ($requests === false) {
            $requests = 0;
        }
        
        // Allow 10 requests per minute
        $limit = apply_filters('dehum_mvp_rate_limit', 10, $action);
        
        if ($requests >= $limit) {
            return false;
        }
        
        // Increment counter
        set_transient($transient_key, $requests + 1, 60);
        return true;
    }

    /**
     * Get unique identifier for rate limiting
     */
    private function get_user_identifier() {
        if (is_user_logged_in()) {
            return 'user_' . get_current_user_id();
        }
        
        // Use IP address for anonymous users
        $ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
        if (isset($_SERVER['HTTP_X_FORWARDED_FOR'])) {
            $ip = explode(',', $_SERVER['HTTP_X_FORWARDED_FOR'])[0];
        }
        
        return 'ip_' . md5($ip . NONCE_SALT);
    }

    /**
     * AJAX handler to get welcome message
     */
    public function ajax_get_welcome_message() {
        // Check rate limiting first
        if (!$this->check_rate_limit('welcome_message')) {
            wp_send_json_error([
                'message' => 'Too many requests. Please wait a moment.',
                'code' => 'rate_limit_exceeded'
            ], 429);
            return;
        }

        // Verify nonce for security
        if (!wp_verify_nonce($_POST['nonce'] ?? '', DEHUM_MVP_CHAT_NONCE)) {
            wp_send_json_error([
                'message' => 'Security check failed',
                'code' => 'invalid_nonce'
            ], 403);
            return;
        }

        try {
            $message = $this->get_welcome_message();
            
            // Hook for additional processing
            do_action('dehum_mvp_before_welcome_response', $message);
            
            wp_send_json_success(['message' => $message]);
        } catch (Exception $e) {
            error_log('Dehum MVP Welcome Message Error: ' . $e->getMessage());
            wp_send_json_error([
                'message' => 'Failed to load welcome message',
                'code' => 'welcome_message_error'
            ], 500);
        }
    }

    /**
     * Enqueue frontend assets (CSS and JavaScript).
     */
    public function enqueue_assets() {
        if (is_admin()) {
            return;
        }
        
        // Respect access control: skip loading for anonymous users when chat is restricted
        if (get_option('dehum_mvp_chat_logged_in_only') && !is_user_logged_in()) {
            return;
        }

        // Allow filtering whether to load assets
        if (!apply_filters('dehum_mvp_should_load_assets', true)) {
            return;
        }

        // Enqueue chat widget CSS
        wp_enqueue_style(
            'dehum-mvp-chat',
            DEHUM_MVP_PLUGIN_URL . 'assets/css/chat.css',
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
            wp_enqueue_style(
                'dehum-mvp-material-symbols',
                'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined',
                [],
                null
            );
        }

        // Inject theme CSS variables and button override with filtering
        $default_theme_vars = [
            '--background' => '#ffffff',
            '--foreground' => '#1e1e1e',
            '--card' => '#ffffff',
            '--card-foreground' => '#1e1e1e',
            '--primary' => '#4054B2',
            '--secondary' => '#4054B2',
            '--primary-foreground' => '#ffffff',
            '--accent' => '#f3f4f6',
            '--accent-foreground' => '#1e1e1e',
        ];

        // Allow themes to customize colors
        $theme_vars = apply_filters('dehum_mvp_theme_variables', $default_theme_vars);
        
        $css_vars = '';
        foreach ($theme_vars as $var => $value) {
            $css_vars .= esc_attr($var) . ': ' . esc_attr($value) . ';';
        }

        $theme_css = ':root {' . $css_vars . '}' . 
                    '.dehum-chat-button{background: var(--primary); color: var(--primary-foreground);}';

        // Allow additional custom CSS
        $custom_css = apply_filters('dehum_mvp_custom_css', '');
        if ($custom_css) {
            $theme_css .= wp_strip_all_tags($custom_css);
        }

        wp_add_inline_style('dehum-mvp-chat', $theme_css);

        // Enqueue chat widget JavaScript
        wp_enqueue_script(
            'dehum-mvp-chat',
            DEHUM_MVP_PLUGIN_URL . 'assets/js/chat.js',
            ['jquery'],
            DEHUM_MVP_VERSION,
            true
        );

        // Get widget configuration for JavaScript
        $widget_config = apply_filters('dehum_mvp_widget_config', [
            'enable_copy_buttons' => true,
            'copy_button_aria_label' => 'Copy message',
            'copy_button_title' => 'Copy to clipboard'
        ]);

        // Localize script with frontend-specific data
        $script_data = [
            'ajaxUrl'    => admin_url('admin-ajax.php'),
            'nonce'      => wp_create_nonce(DEHUM_MVP_CHAT_NONCE),
            'isLoggedIn' => is_user_logged_in(),
            'siteUrl'    => home_url(),
            'maxLen'     => DEHUM_MVP_MESSAGE_MAX_LENGTH,
            'copyButtons' => [
                'enabled' => $widget_config['enable_copy_buttons'],
                'ariaLabel' => $widget_config['copy_button_aria_label'],
                'title' => $widget_config['copy_button_title']
            ]
        ];

        // Allow filtering of script data
        $script_data = apply_filters('dehum_mvp_script_data', $script_data);

        wp_localize_script('dehum-mvp-chat', 'dehumMVP', $script_data);
        
        // Hook after assets enqueued
        do_action('dehum_mvp_assets_enqueued');
    }

    /**
     * Render the chat widget HTML in the footer.
     */
    public function render_chat_widget() {
        if (is_admin()) {
            return;
        }
        if (get_option('dehum_mvp_chat_logged_in_only') && !is_user_logged_in()) {
            return;
        }

        // Allow filtering whether to render widget
        if (!apply_filters('dehum_mvp_should_render_widget', true)) {
            return;
        }
        
        // Get configurable content with defaults
        $config = apply_filters('dehum_mvp_widget_config', [
            'title' => 'Dehumidifier Sizing Assistant (ALPHA TEST) v0.2',
            'button_aria_label' => 'Open chat',
            'clear_aria_label' => 'Clear conversation',
            'clear_title' => 'Clear conversation and start fresh',
            'close_aria_label' => 'Close chat',
            'input_placeholder' => 'Ask about dehumidifiers...',
            'input_aria_label' => 'Type your message',
            'send_aria_label' => 'Send message',
            'disclaimer' => 'Disclaimer: AI can be wrong. Please verify important information.',
            'enable_copy_buttons' => true, // Enable copy buttons on assistant messages
            'copy_button_aria_label' => 'Copy message',
            'copy_button_title' => 'Copy to clipboard'
        ]);
        
        ?>
        <div id="dehum-mvp-chat-widget">
            <!-- Chat Button -->
            <button id="dehum-mvp-chat-button" class="dehum-chat-button" aria-label="<?php echo esc_attr($config['button_aria_label']); ?>">
                <span class="material-symbols-outlined" style="font-size:32px;line-height:1;">sms</span>
            </button>
            
            <!-- Chat Modal -->
            <div id="dehum-mvp-chat-modal" class="dehum-chat-modal" aria-hidden="true" role="dialog" aria-labelledby="chat-title">
                <div class="dehum-chat-container">
                    <!-- Header -->
                    <div class="dehum-chat-header">
                        <h3 id="chat-title"><?php echo esc_html($config['title']); ?></h3>
                        <div class="dehum-header-actions">
                            <button id="dehum-clear-btn" class="dehum-clear-btn" aria-label="<?php echo esc_attr($config['clear_aria_label']); ?>" title="<?php echo esc_attr($config['clear_title']); ?>">
                                🗑️
                            </button>
                            <button id="dehum-close-btn" class="dehum-close-btn" aria-label="<?php echo esc_attr($config['close_aria_label']); ?>">&times;</button>
                        </div>
                    </div>
                    
                    <!-- Messages -->
                    <div id="dehum-chat-messages" class="dehum-chat-messages" role="log" aria-live="polite" aria-label="Chat messages">
                        <!-- Welcome message will be added by JavaScript -->
                    </div>
                    
                    <!-- Input -->
                    <div class="dehum-chat-input">
                        <div class="dehum-input-area">
                            <textarea 
                                id="dehum-chat-input" 
                                placeholder="<?php echo esc_attr($config['input_placeholder']); ?>" 
                                rows="1"
                                aria-label="<?php echo esc_attr($config['input_aria_label']); ?>"
                            ></textarea>
                            <span id="dehum-char-count" class="dehum-char-count">0/<?php echo esc_html(DEHUM_MVP_MESSAGE_MAX_LENGTH); ?></span>
                            <button id="dehum-send-btn" class="dehum-send-btn" aria-label="<?php echo esc_attr($config['send_aria_label']); ?>">
                                Send
                            </button>
                        </div>
                    </div>
                    <div class="dehum-disclaimer" style="font-size: 0.7em; text-align: center; margin-top: 10px; color: #666;"><?php echo esc_html($config['disclaimer']); ?></div>
                </div>
            </div>
        </div>
        <?php
        
        // Hook after widget rendered
        do_action('dehum_mvp_widget_rendered');
    }
} 