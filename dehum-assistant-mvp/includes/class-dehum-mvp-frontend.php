<?php
// Prevent direct access
if (!defined('ABSPATH')) exit;

/**
 * Lean Dehumidifier MVP Frontend
 * Handles assets, render, AJAX proxy to Python, DB save.
 */
class Dehum_MVP_Frontend {

  private $db; // For save

  public function __construct() {
    $this->db = Dehum_MVP_Main::instance()->database; // From main class
    add_action('wp_enqueue_scripts', [$this, 'enqueue_assets']);
    add_action('wp_footer', [$this, 'render_chat_widget']);
    add_action('wp_ajax_dehum_chat_response', [$this, 'ajax_chat_response']);
    add_action('wp_ajax_nopriv_dehum_chat_response', [$this, 'ajax_chat_response']);
    add_action('wp_ajax_dehum_stream_response', [$this, 'ajax_stream_response']);
    add_action('wp_ajax_nopriv_dehum_stream_response', [$this, 'ajax_stream_response']);
    add_action('wp_ajax_dehum_clear_session', [$this, 'ajax_clear_session']);
    add_action('wp_ajax_nopriv_dehum_clear_session', [$this, 'ajax_clear_session']);
    add_action('wp_ajax_dehum_get_session_history', [$this, 'ajax_get_session_history']);
    add_action('wp_ajax_nopriv_dehum_get_session_history', [$this, 'ajax_get_session_history']);
    add_action('admin_notices', [$this, 'dep_warnings']);
  }

  public function dep_warnings() {
    if (!function_exists('curl_init')) echo '<div class="notice notice-error"><p>Dehum MVP: cURL missing—install for proxy.</p></div>';
    if (!extension_loaded('openssl')) echo '<div class="notice notice-error"><p>Dehum MVP: OpenSSL missing—needed for auth.</p></div>';
    if (!function_exists('sodium_crypto_secretbox_keygen')) echo '<div class="notice notice-error"><p>Dehum MVP: libsodium missing—key encryption fails, using no auth.</p></div>';
  }

  public function enqueue_assets() {
    if (is_admin() || (get_option('dehum_mvp_chat_logged_in_only') && !is_user_logged_in())) return;

    wp_enqueue_style('material-symbols', 'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200', [], null);

    $css_path = DEHUM_MVP_PLUGIN_PATH . 'assets/css/chat.css';
    wp_enqueue_style('dehum-chat', DEHUM_MVP_PLUGIN_URL . 'assets/css/chat.css', [], filemtime($css_path) ?: DEHUM_MVP_VERSION);

    $js_path = DEHUM_MVP_PLUGIN_PATH . 'assets/js/chat.js';
    wp_enqueue_script('dehum-chat', DEHUM_MVP_PLUGIN_URL . 'assets/js/chat.js', ['jquery'], filemtime($js_path) ?: DEHUM_MVP_VERSION, true);
    $ai_url = rtrim((string) get_option('dehum_mvp_ai_service_url'), '/');
    $auth = $this->get_decrypted_auth();
    wp_localize_script('dehum-chat', 'dehumMVP', [
      'ajaxUrl' => admin_url('admin-ajax.php'),
      'nonce' => wp_create_nonce(DEHUM_MVP_CHAT_NONCE),
      'saveNonce' => wp_create_nonce('dehum_mvp_save_conversation'),
      'maxLen' => DEHUM_MVP_MESSAGE_MAX_LENGTH ?? 500,
      'isLoggedIn' => is_user_logged_in() ? 1 : 0,
      'aiUrl' => $ai_url,
      'auth' => $auth,
    ]);
  }

  public function render_chat_widget() {
    if (is_admin() || (get_option('dehum_mvp_chat_logged_in_only') && !is_user_logged_in())) return;

    $title = apply_filters('dehum_mvp_title', 'Dehumidifiers Australia Assistant');
    $placeholder = apply_filters('dehum_mvp_placeholder', 'Ask about dehumidifier sizing...');
    $disclaimer = apply_filters('dehum_mvp_disclaimer', 'BETA TEST  v0.6: AI can be wrong. Please verify important information.');
    $maxLen = defined('DEHUM_MVP_MESSAGE_MAX_LENGTH') ? DEHUM_MVP_MESSAGE_MAX_LENGTH : 500;

    echo <<<HTML
<div id="dehum-mvp-chat-widget">
    <button id="dehum-mvp-chat-button" class="dehum-chat-button" aria-label="Open chat assistant">
        <span class="material-symbols-outlined" style="font-size:24px;line-height:1;">chat</span>
    </button>
    
    <div id="dehum-mvp-chat-modal" class="dehum-chat-modal" aria-hidden="true" role="dialog" aria-labelledby="chat-title" aria-describedby="chat-description">
        <div class="dehum-chat-container">
            <div class="dehum-chat-header">
                <h3 id="chat-title">$title</h3>
                <div class="dehum-header-actions">
                    <button id="dehum-clear-btn" class="dehum-clear-btn" aria-label="Clear conversation" title="Clear conversation and start fresh">
                        <span class="material-symbols-outlined">delete</span>
                    </button>
                    <button id="dehum-close-btn" class="dehum-close-btn" aria-label="Close chat">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </div>
            </div>
            
            <div id="dehum-chat-messages" class="dehum-chat-messages" role="log" aria-live="polite" aria-label="Chat messages" aria-describedby="chat-description">
                <!-- Messages here -->
            </div>
            
            <div class="dehum-chat-input">
                <div class="dehum-input-area">
                    <textarea id="dehum-chat-input" placeholder="$placeholder" rows="1" aria-label="Type your message" maxlength="$maxLen"></textarea>
                    <div class="dehum-input-footer">
                        <span id="dehum-char-count" class="dehum-char-count">0/$maxLen</span>
                        <button id="dehum-send-btn" class="dehum-send-btn" aria-label="Send message">
                            <span class="material-symbols-outlined">send</span>
                        </button>
                    </div>
                </div>
                
                <div class="dehum-disclaimer">$disclaimer</div>
            </div>
        </div>
    </div>
    
    <div id="chat-description" class="sr-only">
        An AI-powered dehumidifier sizing assistant that can help you find the right dehumidifier 
        for your space. Supports markdown formatting.
    </div>
</div>
HTML;
  }

  // Removed legacy welcome endpoint; welcome now seeded via session history

  public function ajax_chat_response() {
    if (!wp_verify_nonce($_POST['nonce'] ?? '', DEHUM_MVP_CHAT_NONCE)) wp_send_json_error('Invalid nonce', 403);
    $msg = sanitize_textarea_field($_POST['message'] ?? '');
    $session = sanitize_text_field($_POST['session_id'] ?? '');
    if (empty($msg)) wp_send_json_error('Empty message', 400);

    // Rate limiting (epoch-based, consistent with streaming)
    $epoch = (int) get_option('dehum_mvp_rate_epoch', 1);
    $ip = $this->get_user_ip();
    $key = 'dehum_mvp_rate_limit_' . $epoch . '_' . md5($ip);
    $count = (int) get_transient($key);
    if ($count >= DEHUM_MVP_DAILY_MESSAGE_LIMIT) {
      wp_send_json_error(['message' => 'You\'ve reached the daily message limit for this demo version. Please try again tomorrow, or contact support if you need extended access.', 'rate_limited' => true], 429);
    }
    set_transient($key, $count + 1, DAY_IN_SECONDS);

    $base = rtrim(get_option('dehum_mvp_ai_service_url'), '/');
    if (empty($base)) wp_send_json_error('AI service not configured');

    $url = $base . '/chat';
    $auth = $this->get_decrypted_auth();
    $headers = ['Content-Type' => 'application/json'];
    if ($auth) $headers['Authorization'] = $auth;

    $response = wp_remote_post($url, [
      'headers' => $headers,
      'body' => json_encode(['message' => $msg, 'session_id' => $session]),
      'timeout' => 30,
    ]);

    if (is_wp_error($response)) wp_send_json_error($response->get_error_message(), 500);
    $body = json_decode(wp_remote_retrieve_body($response), true);
    wp_send_json_success(['response' => $body['message'] ?? 'No response']);
  }

  public function ajax_stream_response() {
    if (!wp_verify_nonce($_GET['nonce'] ?? '', DEHUM_MVP_CHAT_NONCE)) wp_send_json_error('Invalid nonce', 403);
    // Respect access control toggle so behavior matches save endpoint
    if (get_option('dehum_mvp_chat_logged_in_only') && !is_user_logged_in()) {
      wp_send_json_error('Chat is currently restricted to logged-in users only.', 403);
    }

    // NEW: Rate limiting check
    $epoch = (int) get_option('dehum_mvp_rate_epoch', 1);
    $ip = $this->get_user_ip();
    $key = 'dehum_mvp_rate_limit_' . $epoch . '_' . md5($ip);
    $count = (int) get_transient($key);

    if ($count >= DEHUM_MVP_DAILY_MESSAGE_LIMIT) {
      header('Content-Type: text/event-stream');
      header('Cache-Control: no-cache');
      header('X-Accel-Buffering: no');
      echo 'data: ' . json_encode([
        'error' => 'You\'ve reached the daily message limit for this demo version. Please try again tomorrow, or contact support if you need extended access.',
        'rate_limited' => true
      ]) . "\n\n";
      flush();
      die();
    }

    // Increment counter for this attempt
    set_transient($key, $count + 1, DAY_IN_SECONDS);

    $msg = sanitize_textarea_field($_GET['message'] ?? '');
    $session = sanitize_text_field($_GET['session_id'] ?? '');
  
    $base = rtrim(get_option('dehum_mvp_ai_service_url'), '/');
    if (empty($base)) wp_send_json_error('AI service not configured', 500);
  
    $url = $base . '/chat/stream';
    header('Content-Type: text/event-stream');
    header('Cache-Control: no-cache');
    header('X-Accel-Buffering: no');
  
    $auth = $this->get_decrypted_auth();
    $headers = ['Accept: text/event-stream', 'Content-Type: application/json'];
    if ($auth) $headers[] = 'Authorization: ' . $auth;

    if (!function_exists('curl_init')) { echo "data: ERROR: cURL missing\n\n"; flush(); die(); }
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(['message' => $msg, 'session_id' => $session]));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
    curl_setopt($ch, CURLOPT_WRITEFUNCTION, function($ch, $data) {
      echo $data;
      if (function_exists('ob_flush')) @ob_flush();
      flush();
      return strlen($data);
    });
    curl_setopt($ch, CURLOPT_TIMEOUT, 120); // Longer timeout for streams
    $ok = curl_exec($ch);
    if ($ok === false) {
      echo "data: ERROR: " . str_replace(["\n","\r"], ' ', curl_error($ch)) . "\n\n";
      flush();
    }
    curl_close($ch);
    die();
  }

  // save and AI service config endpoints are handled centrally by AJAX class

  public function ajax_clear_session() {
    if (!wp_verify_nonce($_POST['nonce'] ?? '', DEHUM_MVP_CHAT_NONCE)) wp_send_json_error('Invalid nonce', 403);
    $session = sanitize_text_field($_POST['session_id'] ?? '');
    if (empty($session)) wp_send_json_error('Missing session_id', 400);

    $deleted_rows = 0;
    if ($this->db) {
      $res = $this->db->delete_session($session);
      if ($res !== false) $deleted_rows = intval($res);
    }

    // Forward clear to Python backend (best-effort)
    $base = rtrim(get_option('dehum_mvp_ai_service_url'), '/');
    if (!empty($base)) {
      $url = $base . '/clear_session';
      $auth = $this->get_decrypted_auth();
      $headers = ['Content-Type' => 'application/json'];
      if ($auth) $headers['Authorization'] = $auth;
      $response = wp_remote_post($url, [
        'headers' => $headers,
        'body'    => json_encode(['session_id' => $session]),
        'timeout' => 10,
      ]);
      // Ignore errors; DB clear already done
    }

    wp_send_json_success(['cleared' => true, 'deleted_rows' => $deleted_rows]);
  }

  public function ajax_get_session_history() {
    if (!wp_verify_nonce($_POST['nonce'] ?? '', DEHUM_MVP_CHAT_NONCE)) wp_send_json_error('Invalid nonce', 403);
    $session = sanitize_text_field($_POST['session_id'] ?? '');
    if (empty($session)) wp_send_json_error('Missing session_id', 400);

    if (!$this->db) wp_send_json_success(['history' => []]);
    $rows = $this->db->get_session_details($session);
    $history = [];
    if (is_array($rows)) {
      foreach ($rows as $row) {
        $msg = isset($row->message) ? trim((string)$row->message) : '';
        $resp = isset($row->response) ? trim((string)$row->response) : '';
        if ($msg !== '') $history[] = ['role' => 'user', 'content' => $msg, 'timestamp' => $row->timestamp ?? ''];
        if ($resp !== '') $history[] = ['role' => 'assistant', 'content' => $resp, 'timestamp' => $row->timestamp ?? ''];
      }
    }
    // If no history exists for this session, seed with a single welcome message
    if (empty($history)) {
      $welcome = apply_filters('dehum_mvp_welcome_message', "**Dehumidifier Assistant**\n- **Sizing:** Room dimensions + humidity\n- **Technical:** Installation, troubleshooting\n- **Products:** Specs, comparisons, pricing\nPool room or regular space?");
      $history[] = ['role' => 'assistant', 'content' => $welcome, 'timestamp' => current_time('mysql')];
    }
    wp_send_json_success(['history' => $history]);
  }

  private function get_user_ip() {
    return $_SERVER['REMOTE_ADDR'] ?? 'unknown';
  }

  private function decrypt_credential($encrypted) {
    if (empty($encrypted)) return '';
    $key_b64 = get_option('dehum_mvp_encryption_key');
    if (empty($key_b64)) return '';
    $key = base64_decode($key_b64);
    // libsodium: base64(nonce + cipher)
    if (function_exists('sodium_crypto_secretbox_open')) {
      $decoded = base64_decode($encrypted);
      if ($decoded && strlen($decoded) > SODIUM_CRYPTO_SECRETBOX_NONCEBYTES) {
        $nonce = mb_substr($decoded, 0, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES, '8bit');
        $ciphertext = mb_substr($decoded, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES, null, '8bit');
        $plain = @sodium_crypto_secretbox_open($ciphertext, $nonce, $key);
        if ($plain !== false) return $plain;
      }
    }
    // OpenSSL legacy: base64(iv:cipher)
    $decoded = base64_decode($encrypted);
    if ($decoded === false) return '';
    $parts = explode(':', $decoded, 2);
    if (count($parts) !== 2) return '';
    $iv = base64_decode($parts[0]);
    $cipher = $parts[1];
    $plain = @openssl_decrypt($cipher, 'aes-256-cbc', $key, 0, $iv);
    return $plain !== false ? $plain : '';
  }

  private function get_decrypted_auth() {
    $enc = get_option('dehum_mvp_ai_service_key_encrypted');
    if (!$enc) return '';
    $plain = $this->decrypt_credential($enc);
    return $plain ? 'Bearer ' . $plain : '';
  }
}