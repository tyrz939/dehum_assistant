<?php
/**
 * Dehumidifier Assistant - WordPress Integration
 * 
 * A complete WordPress integration for the Dehumidifier Assistant chat.
 * Features:
 * - Configurable settings via WordPress admin
 * - Professional floating chat button with modal popup
 * - Mobile responsive design
 * - Analytics integration
 * - Security best practices
 */

class DehumidifierChatIntegration {
    
    // Constants
    const OPTION_PREFIX = 'dehum_chat_';
    const DEFAULT_SERVER_URL = 'http://localhost:5001';
    const DEFAULT_TITLE = 'Dehumidifier Assistant';
    const DEFAULT_SUBTITLE = 'Get expert sizing advice';
    const Z_INDEX = 999999;
    const AUTO_SHOW_DELAY = 5000; // 5 seconds
    
    public function __construct() {
        add_action('wp_footer', [$this, 'render_chat_widget']);
        add_action('wp_enqueue_scripts', [$this, 'enqueue_scripts']);
        add_action('wp_ajax_dehum_chat_analytics', [$this, 'handle_analytics']);
        add_action('wp_ajax_nopriv_dehum_chat_analytics', [$this, 'handle_analytics']);
        
        if (is_admin()) {
            add_action('admin_menu', [$this, 'add_admin_menu']);
            add_action('admin_init', [$this, 'register_settings']);
        }
    }
    
    /**
     * Get configuration values with defaults
     */
    private function get_config($key, $default = '') {
        return get_option(self::OPTION_PREFIX . $key, $default);
    }
    
    private function get_chat_server_url() {
        return $this->get_config('server_url', self::DEFAULT_SERVER_URL);
    }
    
    private function get_chat_title() {
        return $this->get_config('title', self::DEFAULT_TITLE);
    }
    
    private function get_chat_subtitle() {
        return $this->get_config('subtitle', self::DEFAULT_SUBTITLE);
    }
    
    /**
     * Determine if chat should show on current page
     */
    private function should_show_chat() {
        // Don't show if disabled
        if (!$this->get_config('enabled', true)) return false;
        
        // Don't show on admin pages
        if (is_admin()) return false;
        
        // Get page targeting settings
        $show_on_pages = $this->get_config('show_on_pages', true);
        $show_on_posts = $this->get_config('show_on_posts', true);
        $show_on_home = $this->get_config('show_on_home', true);
        $excluded_pages = $this->get_config('excluded_pages', 'login,register,checkout');
        
        // Check exclusions
        if ($excluded_pages) {
            $excluded = array_map('trim', explode(',', $excluded_pages));
            if (is_page($excluded)) return false;
        }
        
        // Check inclusions
        if ($show_on_pages && is_page()) return true;
        if ($show_on_posts && is_single()) return true;
        if ($show_on_home && (is_home() || is_front_page())) return true;
        
        return false;
    }
    
    /**
     * Register admin settings
     */
    public function register_settings() {
        register_setting('dehum_chat_settings', self::OPTION_PREFIX . 'enabled');
        register_setting('dehum_chat_settings', self::OPTION_PREFIX . 'server_url');
        register_setting('dehum_chat_settings', self::OPTION_PREFIX . 'title');
        register_setting('dehum_chat_settings', self::OPTION_PREFIX . 'subtitle');
        register_setting('dehum_chat_settings', self::OPTION_PREFIX . 'show_on_pages');
        register_setting('dehum_chat_settings', self::OPTION_PREFIX . 'show_on_posts');
        register_setting('dehum_chat_settings', self::OPTION_PREFIX . 'show_on_home');
        register_setting('dehum_chat_settings', self::OPTION_PREFIX . 'excluded_pages');
    }
    
    /**
     * Enqueue scripts and styles
     */
    public function enqueue_scripts() {
        if (!$this->should_show_chat()) return;
        
        wp_enqueue_script('jquery');
        
        // Enqueue styles properly
        wp_add_inline_style('wp-block-library', $this->get_chat_styles());
    }
    
    /**
     * Render the chat widget HTML
     */
    public function render_chat_widget() {
        if (!$this->should_show_chat()) return;
        
        $server_url = $this->get_chat_server_url();
        $title = $this->get_chat_title();
        $subtitle = $this->get_chat_subtitle();
        
        ?>
        <!-- Dehumidifier Chat Widget -->
        <div id="dehum-chat-widget">
            <div id="dehum-chat-button" onclick="DehumChat.toggle()">
                <div class="chat-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/>
                    </svg>
                </div>
                <div class="chat-text">
                    <div class="chat-title"><?php echo esc_html($title); ?></div>
                    <div class="chat-subtitle"><?php echo esc_html($subtitle); ?></div>
                </div>
                <div class="close-icon" style="display: none;">×</div>
            </div>
            
            <div id="dehum-chat-overlay" style="display: none;" onclick="DehumChat.close(event)">
                <div class="chat-modal" onclick="event.stopPropagation()">
                    <div class="chat-header">
                        <h3><?php echo esc_html($title); ?></h3>
                        <button class="close-btn" onclick="DehumChat.close()">&times;</button>
                    </div>
                    <div class="chat-content">
                        <iframe 
                            id="dehum-chat-iframe" 
                            src="<?php echo esc_url($server_url . '/popup'); ?>"
                            frameborder="0"
                            allow="microphone">
                        </iframe>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
        window.DehumChat = {
            isOpen: false,
            serverUrl: <?php echo json_encode($server_url); ?>,
            
            toggle() { this.isOpen ? this.close() : this.open(); },
            
            open() {
                this.isOpen = true;
                document.getElementById('dehum-chat-overlay').style.display = 'flex';
                document.getElementById('dehum-chat-button').classList.add('chat-open');
                document.body.style.overflow = 'hidden';
                this.trackEvent('chat_opened');
            },
            
            close(event) {
                if (event && event.target !== event.currentTarget) return;
                this.isOpen = false;
                document.getElementById('dehum-chat-overlay').style.display = 'none';
                document.getElementById('dehum-chat-button').classList.remove('chat-open');
                document.body.style.overflow = '';
                this.trackEvent('chat_closed');
            },
            
            trackEvent(action, data = {}) {
                // Analytics tracking
                if (typeof gtag !== 'undefined') {
                    gtag('event', action, {
                        'event_category': 'Dehumidifier Chat',
                        'event_label': window.location.pathname,
                        ...data
                    });
                }
                
                // WordPress AJAX
                if (typeof jQuery !== 'undefined') {
                    jQuery.post('<?php echo admin_url('admin-ajax.php'); ?>', {
                        action: 'dehum_chat_analytics',
                        event: action,
                        page: window.location.pathname,
                        data: JSON.stringify(data),
                        nonce: '<?php echo wp_create_nonce('dehum_chat_nonce'); ?>'
                    }).fail(function(xhr, status, error) {
                        console.warn('Analytics tracking failed:', error);
                    });
                }
            }
        };
        
        // Event listeners
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && DehumChat.isOpen) DehumChat.close();
        });
        
        // Auto-show with delay
        setTimeout(() => {
            if (!DehumChat.isOpen && !localStorage.getItem('dehum_chat_seen')) {
                document.getElementById('dehum-chat-button').classList.add('pulse');
                localStorage.setItem('dehum_chat_seen', '1');
            }
        }, <?php echo self::AUTO_SHOW_DELAY; ?>);
        </script>
        
        <style><?php echo $this->get_chat_styles(); ?></style>
        <?php
    }
    
    /**
     * Get CSS styles (simplified)
     */
    private function get_chat_styles() {
        return "
        #dehum-chat-widget {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: " . self::Z_INDEX . ";
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        #dehum-chat-button {
            background: linear-gradient(135deg, #0074d9, #005fa3);
            color: white;
            padding: 16px 20px;
            border-radius: 50px;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(0, 116, 217, 0.3);
            display: flex;
            align-items: center;
            gap: 12px;
            transition: all 0.3s ease;
            max-width: 280px;
        }
        
        #dehum-chat-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(0, 116, 217, 0.4);
        }
        
        #dehum-chat-button.pulse {
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { box-shadow: 0 4px 20px rgba(0, 116, 217, 0.3); }
            50% { box-shadow: 0 4px 30px rgba(0, 116, 217, 0.6); }
        }
        
        #dehum-chat-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: " . (self::Z_INDEX + 1) . ";
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .chat-modal {
            background: white;
            border-radius: 12px;
            width: 100%;
            max-width: 400px;
            height: 600px;
            max-height: 90vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }
        
        .chat-header {
            background: #0074d9;
            color: white;
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .close-btn {
            background: none;
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            padding: 0;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            transition: background 0.2s;
        }
        
        .close-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        #dehum-chat-iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        
        /* Mobile responsive */
        @media (max-width: 768px) {
            .chat-modal {
                width: 100%;
                height: 100%;
                max-height: 100vh;
                border-radius: 0;
            }
            #dehum-chat-overlay { padding: 0; }
        }
        ";
    }
    
    /**
     * Handle analytics with better error handling
     */
    public function handle_analytics() {
        // Verify nonce
        if (!isset($_POST['nonce']) || !wp_verify_nonce($_POST['nonce'], 'dehum_chat_nonce')) {
            wp_die('Security check failed', 'Unauthorized', ['response' => 403]);
        }
        
        $event = sanitize_text_field($_POST['event'] ?? '');
        $page = sanitize_text_field($_POST['page'] ?? '');
        $data = sanitize_text_field($_POST['data'] ?? '');
        
        if (empty($event)) {
            wp_die('Invalid event', 'Bad Request', ['response' => 400]);
        }
        
        // Log with timestamp
        $log_entry = sprintf(
            '[%s] Dehumidifier Chat Event: %s on %s - %s',
            current_time('mysql'),
            $event,
            $page,
            $data
        );
        error_log($log_entry);
        
        // Hook for custom analytics
        do_action('dehum_chat_analytics', $event, $page, $data);
        
        wp_die('OK');
    }
    
    /**
     * Add admin menu
     */
    public function add_admin_menu() {
        add_options_page(
            'Dehumidifier Chat Settings',
            'Dehumidifier Chat',
            'manage_options',
            'dehum-chat-settings',
            [$this, 'admin_page']
        );
    }
    
    /**
     * Admin settings page with actual settings
     */
    public function admin_page() {
        if (isset($_POST['submit'])) {
            // Handle form submission
            update_option(self::OPTION_PREFIX . 'enabled', isset($_POST['enabled']));
            update_option(self::OPTION_PREFIX . 'server_url', sanitize_url($_POST['server_url']));
            update_option(self::OPTION_PREFIX . 'title', sanitize_text_field($_POST['title']));
            update_option(self::OPTION_PREFIX . 'subtitle', sanitize_text_field($_POST['subtitle']));
            echo '<div class="notice notice-success"><p>Settings saved!</p></div>';
        }
        
        $server_url = $this->get_chat_server_url();
        $enabled = $this->get_config('enabled', true);
        $title = $this->get_chat_title();
        $subtitle = $this->get_chat_subtitle();
        
        ?>
        <div class="wrap">
            <h1>Dehumidifier Chat Settings</h1>
            
            <form method="post" action="">
                <table class="form-table">
                    <tr>
                        <th scope="row">Enable Chat Widget</th>
                        <td>
                            <input type="checkbox" name="enabled" <?php checked($enabled); ?> />
                            <label>Show chat widget on site</label>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Chat Server URL</th>
                        <td>
                            <input type="url" name="server_url" value="<?php echo esc_attr($server_url); ?>" class="regular-text" required />
                            <p class="description">URL of your Flask app (e.g., http://localhost:5001)</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Chat Title</th>
                        <td>
                            <input type="text" name="title" value="<?php echo esc_attr($title); ?>" class="regular-text" />
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Chat Subtitle</th>
                        <td>
                            <input type="text" name="subtitle" value="<?php echo esc_attr($subtitle); ?>" class="regular-text" />
                        </td>
                    </tr>
                </table>
                
                <?php submit_button(); ?>
            </form>
            
            <div class="card">
                <h2>Connection Status</h2>
                <?php
                $response = wp_remote_get($server_url . '/api/health', ['timeout' => 5]);
                if (is_wp_error($response)) {
                    $error = $response->get_error_message();
                    echo '<p><span style="color: red;">❌ Connection Failed:</span> ' . esc_html($error) . '</p>';
                } else {
                    $code = wp_remote_retrieve_response_code($response);
                    if ($code === 200) {
                        echo '<p><span style="color: green;">✅ Connected</span></p>';
                    } else {
                        echo '<p><span style="color: orange;">⚠️ Unexpected response code:</span> ' . esc_html($code) . '</p>';
                    }
                }
                ?>
            </div>
        </div>
        <?php
    }
}

// Initialize
new DehumidifierChatIntegration();

// Shortcode
function dehumidifier_chat_shortcode($atts) {
    $atts = shortcode_atts([
        'title' => 'Dehumidifier Assistant',
        'subtitle' => 'Get expert advice'
    ], $atts);
    
    return sprintf(
        '<div onclick="DehumChat.open()" style="display: inline-block; background: #0074d9; color: white; padding: 10px 20px; border-radius: 25px; cursor: pointer; font-family: sans-serif;">
            🏠 %s<br><small>%s</small>
        </div>',
        esc_html($atts['title']),
        esc_html($atts['subtitle'])
    );
}
add_shortcode('dehumidifier_chat', 'dehumidifier_chat_shortcode');
?> 