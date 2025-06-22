<?php
/**
 * Plugin Name: Dehumidifier Assistant Chat
 * Description: Simple, reliable floating chat widget for dehumidifier sizing advice
 * Version: 0.0.2
 * Author: John Keen
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

class DehumidifierChat {
    
    public function __construct() {
        add_action('wp_footer', [$this, 'render_chat_widget']);
        add_action('admin_menu', [$this, 'add_admin_menu']);
        add_action('admin_init', [$this, 'register_settings']);
    }
    
    private function get_server_url() {
        return get_option('dehum_chat_server_url', 'http://localhost:5001');
    }
    
    private function is_enabled() {
        return get_option('dehum_chat_enabled', true);
    }
    
    public function render_chat_widget() {
        if (!$this->is_enabled() || is_admin()) return;
        
        $server_url = $this->get_server_url();
        ?>
        
        <!-- Simple Chat Widget -->
        <div id="dehum-chat-widget">
            <!-- Chat Button -->
            <div id="dehum-chat-btn" onclick="openDehumChat()">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
                    <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                    <circle cx="8" cy="10" r="1" fill="#667eea"/>
                    <circle cx="12" cy="10" r="1" fill="#667eea"/>
                    <circle cx="16" cy="10" r="1" fill="#667eea"/>
                </svg>
                <div class="chat-tooltip">Dehumidifier Assistant</div>
            </div>
            
            <!-- Chat Modal -->
            <div id="dehum-chat-modal" style="display: none;">
                <div class="modal-backdrop" onclick="closeDehumChat()"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>🏠 Dehumidifier Assistant</h3>
                        <button onclick="closeDehumChat()" class="close-btn">&times;</button>
                    </div>
                    <div class="modal-body">
                        <iframe 
                            id="dehum-iframe" 
                            src="<?php echo esc_url($server_url . '/popup'); ?>"
                            width="100%" 
                            height="100%" 
                            frameborder="0">
                        </iframe>
                    </div>
                </div>
            </div>
        </div>

        <style>
        #dehum-chat-widget {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 999999;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        #dehum-chat-btn {
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
            transition: all 0.3s ease;
            position: relative;
        }

        #dehum-chat-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 30px rgba(102, 126, 234, 0.6);
        }

        #dehum-chat-btn:hover .chat-tooltip {
            opacity: 1;
            visibility: visible;
        }

        .chat-tooltip {
            position: absolute;
            right: 70px;
            top: 50%;
            transform: translateY(-50%);
            background: #333;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
            white-space: nowrap;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        }

        .chat-tooltip::after {
            content: '';
            position: absolute;
            left: 100%;
            top: 50%;
            transform: translateY(-50%);
            border: 6px solid transparent;
            border-left-color: #333;
        }

        #dehum-chat-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1000000;
        }

        .modal-backdrop {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.6);
        }

                 .modal-content {
             position: absolute;
             bottom: 90px;
             right: 20px;
             width: 420px;
             height: 600px;
             background: white;
             border-radius: 12px;
             overflow: hidden;
             box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
             animation: modalSlideUp 0.3s ease;
         }

                 @keyframes modalSlideUp {
             from {
                 opacity: 0;
                 transform: translateY(20px);
             }
             to {
                 opacity: 1;
                 transform: translateY(0);
             }
         }

        .modal-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-header h3 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
        }

        .close-btn {
            background: none;
            border: none;
            color: white;
            font-size: 28px;
            cursor: pointer;
            padding: 0;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
        }

        .close-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .modal-body {
            height: calc(100% - 68px);
            position: relative;
        }

        #dehum-iframe {
            border: none;
        }

                 /* Mobile responsive */
         @media (max-width: 768px) {
             .modal-content {
                 position: fixed;
                 top: 0;
                 left: 0;
                 right: 0;
                 bottom: 0;
                 width: 100%;
                 height: 100%;
                 border-radius: 0;
                 animation: modalSlideIn 0.3s ease;
             }
             
             #dehum-chat-btn {
                 width: 56px;
                 height: 56px;
             }
             
             .chat-tooltip {
                 display: none;
             }
         }

         @keyframes modalSlideIn {
             from {
                 opacity: 0;
                 transform: translateY(100%);
             }
             to {
                 opacity: 1;
                 transform: translateY(0);
             }
         }
        </style>

                 <script>
         function openDehumChat() {
             document.getElementById('dehum-chat-modal').style.display = 'block';
             document.body.style.overflow = 'hidden';
             
             // Auto-scroll to bottom after iframe loads
             const iframe = document.getElementById('dehum-iframe');
             iframe.onload = function() {
                 try {
                     // Try to scroll the iframe content to bottom
                     const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                     const chatContainer = iframeDoc.querySelector('#chat-container, .chat-container, [class*="chat"]');
                     if (chatContainer) {
                         chatContainer.scrollTop = chatContainer.scrollHeight;
                     }
                 } catch (e) {
                     // Cross-origin restrictions - send message to iframe instead
                     iframe.contentWindow.postMessage({action: 'scrollToBottom'}, '*');
                 }
             };
         }

         function closeDehumChat() {
             document.getElementById('dehum-chat-modal').style.display = 'none';
             document.body.style.overflow = '';
         }

         // Close on Escape key
         document.addEventListener('keydown', function(e) {
             if (e.key === 'Escape') {
                 closeDehumChat();
             }
         });

         // Prevent zoom on mobile
         document.addEventListener('touchstart', function(e) {
             if (e.touches.length > 1) {
                 e.preventDefault();
             }
         }, {passive: false});

         let lastTouchEnd = 0;
         document.addEventListener('touchend', function(e) {
             const now = (new Date()).getTime();
             if (now - lastTouchEnd <= 300) {
                 e.preventDefault();
             }
             lastTouchEnd = now;
         }, false);
         </script>
        
        <?php
    }
    
    public function register_settings() {
        register_setting('dehum_chat_settings', 'dehum_chat_enabled');
        register_setting('dehum_chat_settings', 'dehum_chat_server_url');
    }
    
    public function add_admin_menu() {
        add_options_page(
            'Dehumidifier Chat',
            'Dehumidifier Chat',
            'manage_options',
            'dehum-chat',
            [$this, 'admin_page']
        );
    }
    
    public function admin_page() {
        if (isset($_POST['submit'])) {
            update_option('dehum_chat_enabled', isset($_POST['enabled']));
            update_option('dehum_chat_server_url', sanitize_url($_POST['server_url']));
            echo '<div class="notice notice-success"><p>Settings saved!</p></div>';
        }
        
        $enabled = $this->is_enabled();
        $server_url = $this->get_server_url();
        ?>
        
        <div class="wrap">
            <h1>🏠 Dehumidifier Chat Settings</h1>
            
            <form method="post">
                <table class="form-table">
                    <tr>
                        <th scope="row">Enable Chat</th>
                        <td>
                            <label>
                                <input type="checkbox" name="enabled" <?php checked($enabled); ?> />
                                Show chat widget on website
                            </label>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Server URL</th>
                        <td>
                            <input type="url" name="server_url" value="<?php echo esc_attr($server_url); ?>" class="regular-text" required />
                            <p class="description">Your Flask app URL (e.g., http://localhost:5001 or https://your-app.onrender.com)</p>
                        </td>
                    </tr>
                </table>
                
                <?php submit_button(); ?>
            </form>
            
            <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; margin-top: 20px;">
                <h3>🔍 Quick Test</h3>
                <p>After saving settings, visit your website and look for a <strong>purple chat button</strong> in the bottom-right corner.</p>
                <p>Click it to open the chat modal with your dehumidifier assistant.</p>
            </div>
        </div>
        
        <?php
    }
}

// Initialize the plugin
new DehumidifierChat();
?>