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

        // Inject theme CSS variables and button override
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
}
.dehum-chat-button{background: var(--primary); color: var(--primary-foreground);}';

        wp_add_inline_style('dehum-mvp-chat', $theme_css);

        // Enqueue chat widget JavaScript
        wp_enqueue_script(
            'dehum-mvp-chat',
            DEHUM_MVP_PLUGIN_URL . 'assets/js/chat.js',
            ['jquery'],
            DEHUM_MVP_VERSION,
            true
        );

        // Localize script with frontend-specific data
        wp_localize_script('dehum-mvp-chat', 'dehumMVP', [
            'ajaxUrl'    => admin_url('admin-ajax.php'),
            'nonce'      => wp_create_nonce(DEHUM_MVP_CHAT_NONCE),
            'isLoggedIn' => is_user_logged_in(),
            'siteUrl'    => home_url(),
            'maxLen'     => DEHUM_MVP_MESSAGE_MAX_LENGTH,
        ]);
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
        
        ?>
        <div id="dehum-mvp-chat-widget">
            <!-- Chat Button -->
            <button id="dehum-mvp-chat-button" class="dehum-chat-button" aria-label="Open chat">
                <span class="material-symbols-outlined" style="font-size:32px;line-height:1;">sms</span>
            </button>
            
            <!-- Chat Modal -->
            <div id="dehum-mvp-chat-modal" class="dehum-chat-modal" aria-hidden="true" role="dialog" aria-labelledby="chat-title">
                <div class="dehum-chat-container">
                    <!-- Header -->
                    <div class="dehum-chat-header">
                        <h3 id="chat-title">Dehumidifier Sizing Assistant (ALPHA TEST)</h3>
                        <div class="dehum-header-actions">
                            <button id="dehum-clear-btn" class="dehum-clear-btn" aria-label="Clear conversation" title="Clear conversation and start fresh">
                                🗑️
                            </button>
                            <button id="dehum-close-btn" class="dehum-close-btn" aria-label="Close chat">&times;</button>
                        </div>
                    </div>
                    
                    <!-- Messages -->
                    <div id="dehum-chat-messages" class="dehum-chat-messages">
                        <div class="dehum-welcome">
                            <strong>Welcome! I'm your dehumidifier sizing assistant.</strong><br>
                            To get started, is this for a pool room or a regular space?<br>
                            Please provide the size of the space (length × width × height in meters, or total m³), your current room humidity (RH%), and your target humidity (RH%).<br>
                            I'll calculate the ideal dehumidifier size for you!
                        </div>
                    </div>
                    
                    <!-- Input -->
                    <div class="dehum-chat-input">
                        <div class="dehum-input-area">
                            <textarea 
                                id="dehum-chat-input" 
                                placeholder="Ask about dehumidifiers..." 
                                rows="1"
                                aria-label="Type your message"
                            ></textarea>
                            <span id="dehum-char-count" class="dehum-char-count">0/<?php echo DEHUM_MVP_MESSAGE_MAX_LENGTH; ?></span>
                            <button id="dehum-send-btn" class="dehum-send-btn" aria-label="Send message">
                                Send
                            </button>
                        </div>
                    </div>
                    <div class="dehum-disclaimer" style="font-size: 0.7em; text-align: center; margin-top: 10px; color: #666;">Disclaimer: AI can be wrong. Please verify important information.</div>
                </div>
            </div>
        </div>
        <?php
    }
} 