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
            'nonce'      => wp_create_nonce('dehum_mvp_chat_nonce'),
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
                💬
            </button>
            
            <!-- Chat Modal -->
            <div id="dehum-mvp-chat-modal" class="dehum-chat-modal" aria-hidden="true" role="dialog" aria-labelledby="chat-title">
                <div class="dehum-chat-container">
                    <!-- Header -->
                    <div class="dehum-chat-header">
                        <h3 id="chat-title">Dehumidifier Assistant</h3>
                        <button id="dehum-close-btn" class="dehum-close-btn" aria-label="Close chat">&times;</button>
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