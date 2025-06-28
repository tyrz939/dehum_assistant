/**
 * Dehumidifier Assistant Chat Widget
 * Professional JavaScript implementation
 */

(function ($) {
  'use strict';

  const ChatWidget = {
    // Configuration
    selectors: {
      widget: '#dehum-mvp-chat-widget',
      button: '#dehum-mvp-chat-button',
      modal: '#dehum-mvp-chat-modal',
      closeBtn: '#dehum-close-btn',
      messages: '#dehum-chat-messages',
      input: '#dehum-chat-input',
      sendBtn: '#dehum-send-btn'
    },

    // State
    isOpen: false,
    isProcessing: false,
    conversation: [],

    /**
     * Initialize the chat widget
     */
    init() {
      this.bindEvents();
      this.setupAccessibility();
      this.loadConversation();
    },

    /**
     * Bind event handlers
     */
    bindEvents() {
      // Open chat
      $(this.selectors.button).on('click', () => {
        this.openChat();
      });

      // Close chat
      $(this.selectors.closeBtn).on('click', () => {
        this.closeChat();
      });

      // Close on background click
      $(this.selectors.modal).on('click', (e) => {
        if (e.target === e.currentTarget) {
          this.closeChat();
        }
      });

      // Send message
      $(this.selectors.sendBtn).on('click', () => {
        this.sendMessage();
      });

      // Enter key to send
      $(this.selectors.input).on('keypress', (e) => {
        if (e.which === 13 && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });

      // Escape key to close
      $(document).on('keydown', (e) => {
        if (e.key === 'Escape' && this.isOpen) {
          this.closeChat();
        }
      });
    },

    /**
     * Setup accessibility features
     */
    setupAccessibility() {
      $(this.selectors.modal).attr('aria-hidden', 'true');
    },

    /**
     * Open the chat modal
     */
    openChat() {
      if (this.isOpen) return;

      this.isOpen = true;
      $(this.selectors.modal).addClass('show').attr('aria-hidden', 'false');

      // Focus the input
      setTimeout(() => {
        $(this.selectors.input).focus();
      }, 100);

      // Reload conversation from storage in case it was cleared in another tab
      this.loadConversation();
    },

    /**
     * Close the chat modal
     */
    closeChat() {
      if (!this.isOpen) return;

      this.isOpen = false;
      $(this.selectors.modal).removeClass('show').attr('aria-hidden', 'true');
    },

    /**
     * Send a message
     */
    sendMessage() {
      const message = $(this.selectors.input).val().trim();

      if (!message || this.isProcessing) return;

      // Add user message to UI
      this.addMessage('user', message);
      $(this.selectors.input).val('');

      // Show typing indicator
      this.showTypingIndicator();

      // Send to backend
      this.callAPI(message)
        .then(response => {
          this.hideTypingIndicator();
          this.addMessage('assistant', response.response);
        })
        .catch(error => {
          this.hideTypingIndicator();
          this.addMessage('error', error.message || 'Sorry, something went wrong. Please try again.');
        });
    },

    /**
     * Call the WordPress AJAX API
     */
    callAPI(message) {
      this.isProcessing = true;

      return new Promise((resolve, reject) => {
        $.ajax({
          url: dehumMVP.ajaxUrl,
          type: 'POST',
          data: {
            action: 'dehum_mvp_chat',
            message: message,
            nonce: dehumMVP.nonce
          },
          timeout: 30000
        }).done(response => {
          if (response.success) {
            resolve(response.data);
          } else {
            reject(new Error(response.data?.message || 'API request failed'));
          }
        }).fail(error => {
          reject(new Error('Connection error. Please try again.'));
        }).always(() => {
          this.isProcessing = false;
        });
      });
    },

    /**
     * Add a message to the chat
     */
    addMessage(type, content) {
      const messageClass = `dehum-message dehum-message--${type}`;
      const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      const message = {
        type,
        content,
        timestamp
      };

      // Don't save error messages to history
      if (type !== 'error') {
        this.conversation.push(message);
        this.saveConversation();
      }

      this.renderMessage(message);
      this.scrollToBottom();
    },

    /**
     * Renders a single message object to the DOM
     */
    renderMessage(message) {
      const messageClass = `dehum-message dehum-message--${message.type}`;
      const messageHtml = `
            <div class="${messageClass}">
                <div class="dehum-message__bubble">
                    ${this.escapeHtml(message.content)}
                </div>
                <div class="dehum-message__timestamp">${message.timestamp}</div>
            </div>
        `;
      $(this.selectors.messages).append(messageHtml);
    },

    /**
     * Load conversation from localStorage
     */
    loadConversation() {
      try {
        const storedConversation = localStorage.getItem('dehum_conversation');
        if (storedConversation) {
          this.conversation = JSON.parse(storedConversation);
          $(this.selectors.messages).empty();
          this.conversation.forEach(message => this.renderMessage(message));
          this.scrollToBottom();
        }
      } catch (e) {
        this.conversation = [];
      }
    },

    /**
     * Save conversation to localStorage
     */
    saveConversation() {
      try {
        localStorage.setItem('dehum_conversation', JSON.stringify(this.conversation));
      } catch (e) {
        // Silently fail if localStorage is not available
      }
    },

    /**
     * Show typing indicator
     */
    showTypingIndicator() {
      const typingHtml = `
        <div id="typing-indicator" class="dehum-message dehum-message--assistant">
            <div class="dehum-message__bubble">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
    `;
      $(this.selectors.messages).append(typingHtml);
      this.scrollToBottom();
    },

    /**
     * Hide typing indicator
     */
    hideTypingIndicator() {
      $('#typing-indicator').remove();
    },

    /**
     * Scroll to bottom of messages
     */
    scrollToBottom() {
      const messagesEl = $(this.selectors.messages)[0];
      if (messagesEl) {
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
  };

  // Initialize when DOM is ready
  $(document).ready(() => {
    ChatWidget.init();
  });

})(jQuery);