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

        // Enqueue chat widget CSS
        wp_enqueue_style(
            'dehum-mvp-chat',
            DEHUM_MVP_PLUGIN_URL . 'assets/css/chat.css',
            [],
            DEHUM_MVP_VERSION
        );

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
            'siteUrl'    => home_url()
        ]);
    }

    /**
     * Render the chat widget HTML in the footer.
     */
    public function render_chat_widget() {
        if (is_admin()) {
            return;
        }
        
        ?>
        <div id="dehum-mvp-chat-widget">
            <!-- Chat Button -->
            <button id="dehum-mvp-chat-button" class="dehum-chat-button" aria-label="Open Dehumidifier Assistant">
                <span class="dehum-button-content">
                    <span class="dehum-ai-icon">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                            <path d="M12 1C5.925 1 1 5.925 1 12s4.925 11 11 11 11-4.925 11-11S18.075 1 12 1zM8.5 6c.825 0 1.5.675 1.5 1.5S9.325 9 8.5 9 7 8.325 7 7.5 7.675 6 8.5 6zm7 0c.825 0 1.5.675 1.5 1.5S16.325 9 15.5 9 14 8.325 14 7.5 14.675 6 15.5 6zM12 18c-2.5 0-4.5-1.5-5.5-3.5h2c.5 1 1.5 1.5 3.5 1.5s3-.5 3.5-1.5h2c-1 2-3 3.5-5.5 3.5z"/>
                        </svg>
                    </span>
                    <span class="dehum-ai-text">AI</span>
                </span>
            </button>
            
            <!-- Chat Modal -->
            <div id="dehum-mvp-chat-modal" class="dehum-chat-modal" aria-hidden="true" role="dialog" aria-labelledby="chat-title">
                <div class="dehum-chat-container">
                    <!-- Header -->
                    <div class="dehum-chat-header">
                        <h3 id="chat-title">Dehumidifier Assistant</h3>
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
                            <strong>Hi! I'm your dehumidifier assistant.</strong><br>
                            I can help you choose the right dehumidifier, calculate sizing, and answer technical questions. What would you like to know?
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
                            <button id="dehum-send-btn" class="dehum-send-btn" aria-label="Send message">
                                Send
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <?php
    }
} 