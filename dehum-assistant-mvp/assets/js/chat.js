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
      clearBtn: '#dehum-clear-btn',
      messages: '#dehum-chat-messages',
      input: '#dehum-chat-input',
      sendBtn: '#dehum-send-btn'
    },

    maxLen: parseInt(dehumMVP.maxLen || 1200, 10),

    // State
    isOpen: false,
    isProcessing: false,
    conversation: [],
    currentSessionId: null, // Track current session ID
    streamingComplete: false, // Flag to track if streaming has completed

    /**
     * Initialize the chat widget
     */
    init() {
      this.bindEvents();
      this.setupAccessibility();
      this.loadConversation();
      this.loadSessionId();
      this.initButtonEffects();

      // Initialize char counter
      this.updateCharCount();

      // Initial auto-size
      this.autoResizeInput();

      // Check for interrupted analysis on chat initialization
      this.checkForInterruption();
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

      // Clear conversation
      $(this.selectors.clearBtn).on('click', () => {
        this.clearConversation();
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

      // Update char count on input
      $(this.selectors.input).on('input', () => {
        this.autoResizeInput();
        this.updateCharCount();
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
     * Initialize button visual effects
     */
    initButtonEffects() {
      // Add a subtle pulse effect after a delay to draw attention
      setTimeout(() => {
        $(this.selectors.button).addClass('pulse');

        // Remove pulse after first interaction
        $(this.selectors.button).one('click', () => {
          $(this.selectors.button).removeClass('pulse');
        });
      }, 3000);
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
      this.loadSessionId();
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
     * Clear the conversation and start a new session
     */
    clearConversation() {
      if (this.isProcessing) return;

      // Confirm with user
      if (!confirm('Clear conversation and start fresh? This cannot be undone.')) {
        return;
      }

      // Clear frontend state
      this.conversation = [];
      this.currentSessionId = null;
      $(this.selectors.messages).empty();

      // Clear storage
      this.saveConversation();
      this.saveSessionId();

      // Show confirmation message
      this.addSystemMessage('Conversation cleared. Starting fresh!');

      // Focus input for new conversation
      $(this.selectors.input).focus();
    },

    /**
     * Send a message
     */
    sendMessage() {
      const message = $(this.selectors.input).val().trim();

      if (message.length > this.maxLen) {
        this.addSystemMessage(`Message exceeds ${this.maxLen} characters.`);
        return;
      }

      if (!message || this.isProcessing) return;

      // Lock the interface immediately
      this.lockInterface();

      // Add user message to UI
      this.addMessage('user', message);
      $(this.selectors.input).val('');

      // Show typing indicator
      this.showTypingIndicator();

      // Try streaming first, fallback to regular if it fails
      this.callStreamingAPI(message)
        .catch(error => {
          console.log('Streaming failed, falling back to regular API:', error);
          return this.callAPI(message);
        })
        .then(response => {
          // Only handle response if streaming didn't already handle it
          if (response && !this.streamingComplete) {
            this.hideTypingIndicator();
            this.addMessage('assistant', response.response);

            // Store session ID from response
            if (response.session_id) {
              this.currentSessionId = response.session_id;
              this.saveSessionId();
            }
          }
        })
        .catch(error => {
          this.hideTypingIndicator();
          this.addMessage('error', error.message || 'Sorry, something went wrong. Please try again.');
        })
        .finally(() => {
          this.streamingComplete = false;
          this.unlockInterface(); // Always unlock interface when done
        });
    },

    /**
     * Lock the interface during processing
     */
    lockInterface() {
      this.isProcessing = true;
      $(this.selectors.input).prop('disabled', true).attr('placeholder', 'Processing...');
      $(this.selectors.sendBtn).prop('disabled', true).addClass('dehum-btn--disabled');
    },

    /**
     * Unlock the interface after processing
     */
    unlockInterface() {
      this.isProcessing = false;
      $(this.selectors.input).prop('disabled', false).attr('placeholder', 'Ask about dehumidifier sizing...');
      $(this.selectors.sendBtn).prop('disabled', false).removeClass('dehum-btn--disabled');
    },

    /**
     * Show thinking indicator with animated dots
     */
    showThinkingIndicator() {
      this.hideTypingIndicator(); // Remove typing indicator first

      const thinkingHtml = `
        <div id="thinking-indicator" class="dehum-message dehum-message--thinking">
          <div class="dehum-message__bubble">
            🤔 Let me analyze the available options and find the best dehumidifier combinations for your specific requirements
            <span class="thinking-dots">
              <span>.</span><span>.</span><span>.</span>
            </span>
          </div>
        </div>
      `;

      $(this.selectors.messages).append(thinkingHtml);
      this.scrollToBottom();
    },

    /**
     * Hide thinking indicator
     */
    hideThinkingIndicator() {
      $('#thinking-indicator').remove();
    },

    /**
     * Call the AI service streaming endpoint directly
     */
    async callStreamingAPI(message) {
      this.isProcessing = true;
      this.streamingComplete = false;

      try {
        // Get AI service URL from WordPress settings
        const aiServiceUrl = await this.getAIServiceURL();
        if (!aiServiceUrl) {
          throw new Error('Streaming not available - no AI service URL configured');
        }

        const streamUrl = aiServiceUrl.replace(/\/$/, '') + '/chat/stream';

        // Prepare request data
        const requestData = {
          message: message,
          session_id: this.currentSessionId || this.generateSessionId(),
          user_id: dehumMVP.isLoggedIn ? 'wp_user' : null
        };

        let assistantMessageElement = null;
        let currentContent = '';
        let isThinking = false;
        let streamingContent = ''; // For accumulating streaming text chunks
        let currentMessageIndex = -1; // Track current message in conversation history

        // Make streaming request
        const response = await fetch(streamUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': await this.getAIServiceAuth()
          },
          body: JSON.stringify(requestData)
        });

        if (!response.ok) {
          throw new Error(`Streaming request failed: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ') && line !== 'data: [DONE]') {
              try {
                const jsonStr = line.slice(6); // Remove "data: "
                const data = JSON.parse(jsonStr);

                // Store session ID
                if (data.session_id) {
                  this.currentSessionId = data.session_id;
                  this.saveSessionId();
                }

                // Handle different types of responses
                if (data.is_thinking) {
                  // Show thinking indicator with animated dots
                  if (!isThinking) {
                    this.showThinkingIndicator();
                    isThinking = true;

                    // Save incomplete state for interruption detection
                    this.saveIncompleteState('thinking', currentContent);
                  }
                } else if (data.is_streaming_chunk) {
                  // Real-time text chunk from OpenAI
                  if (isThinking) {
                    // Hide thinking indicator and start showing streaming content
                    this.hideThinkingIndicator();
                    isThinking = false;

                    // Create the message element for streaming content
                    if (!assistantMessageElement) {
                      assistantMessageElement = this.addMessage('assistant', currentContent, true);
                      currentMessageIndex = this.conversation.length - 1;
                    }

                    // Update conversation state
                    this.saveIncompleteState('streaming', currentContent);
                  }

                  // Accumulate streaming content and update message
                  streamingContent += data.message;
                  if (assistantMessageElement) {
                    this.updateMessage(assistantMessageElement, currentContent + '\n\n' + streamingContent);
                  }
                } else if (data.is_final) {
                  // Final message - streaming is complete
                  this.hideThinkingIndicator();

                  if (assistantMessageElement && streamingContent) {
                    // Update with final content (already accumulated)
                    this.updateMessage(assistantMessageElement, currentContent + '\n\n' + streamingContent);

                    // Mark as complete in conversation history
                    if (currentMessageIndex >= 0 && currentMessageIndex < this.conversation.length) {
                      this.conversation[currentMessageIndex].content = currentContent + '\n\n' + streamingContent;
                      this.conversation[currentMessageIndex].phase = 'complete';
                      this.conversation[currentMessageIndex].isComplete = true;
                      this.saveConversation();
                    }
                  } else if (data.message && data.message.trim()) {
                    // Create new message if no streaming occurred
                    if (!assistantMessageElement) {
                      assistantMessageElement = this.addMessage('assistant', currentContent + data.message, true);
                    } else {
                      this.updateMessage(assistantMessageElement, currentContent + '\n\n' + data.message);
                    }
                  }

                  // Clear incomplete state
                  this.clearIncompleteState();
                  this.streamingComplete = true;
                } else {
                  // Initial response - show immediately
                  if (!assistantMessageElement) {
                    this.hideTypingIndicator();
                    assistantMessageElement = this.addMessage('assistant', data.message, true);
                    currentContent = data.message;
                    currentMessageIndex = this.conversation.length - 1;

                    // Mark as initial phase in conversation history
                    if (currentMessageIndex >= 0) {
                      this.conversation[currentMessageIndex].phase = 'initial';
                      this.conversation[currentMessageIndex].isComplete = false;
                      this.saveConversation();
                    }
                  } else {
                    currentContent += '\n\n' + data.message;
                    this.updateMessage(assistantMessageElement, currentContent);
                  }
                }
              } catch (e) {
                console.error('Error parsing streaming data:', e);
              }
            }
          }
        }

        // Save complete conversation to WordPress
        const finalContent = streamingContent ? (currentContent + '\n\n' + streamingContent) : currentContent;
        await this.saveConversationToWordPress(message, finalContent);

        return { session_id: this.currentSessionId, response: finalContent };

      } catch (error) {
        console.error('Streaming error:', error);
        throw error;
      } finally {
        this.isProcessing = false;
      }
    },

    /**
     * Call the WordPress AJAX API
     */
    callAPI(message) {
      this.isProcessing = true;

      // Prepare data with session ID if available
      const requestData = {
        action: 'dehum_mvp_chat',
        message: message,
        nonce: dehumMVP.nonce
      };

      // Include session ID if we have one
      if (this.currentSessionId) {
        requestData.session_id = this.currentSessionId;
      }

      return new Promise((resolve, reject) => {
        $.ajax({
          url: dehumMVP.ajaxUrl,
          type: 'POST',
          data: requestData,
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
     * Add a message to the chat (modified to handle both streaming and regular messages)
     */
    addMessage(type, content, returnElement = false) {
      const messageClass = `dehum-message dehum-message--${type}`;
      const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      // Save to conversation history if not an error
      if (type !== 'error') {
        const message = {
          type,
          content,
          timestamp,
          phase: 'complete', // Track message phases: initial, thinking, recommendations, complete
          isComplete: true
        };
        this.conversation.push(message);
        this.saveConversation();
      }

      const messageHtml = `
        <div class="${messageClass}">
          <div class="dehum-message__bubble">${this.formatContent(content)}</div>
          <div class="dehum-message__timestamp">${timestamp}</div>
        </div>
      `;

      const $message = $(messageHtml);
      $(this.selectors.messages).append($message);
      this.scrollToBottom();

      return returnElement ? $message : undefined;
    },

    /**
     * Add a system message (for notifications)
     */
    addSystemMessage(content) {
      const messageHtml = `
        <div class="dehum-message dehum-message--system">
            <div class="dehum-message__bubble">
                <em>${this.escapeHtml(content)}</em>
            </div>
        </div>
      `;
      $(this.selectors.messages).append(messageHtml);
      this.scrollToBottom();

      // Auto-remove system messages after 3 seconds
      setTimeout(() => {
        $('.dehum-message--system').fadeOut(300, function () {
          $(this).remove();
        });
      }, 3000);
    },

    /**
     * Render a message from history
     */
    renderMessage(message) {
      const messageClass = `dehum-message dehum-message--${message.type}`;
      const messageHtml = `
        <div class="${messageClass}">
          <div class="dehum-message__bubble">${this.formatContent(message.content)}</div>
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

          // Migrate old conversation format if needed
          this.conversation = this.conversation.map(msg => {
            if (!msg.hasOwnProperty('phase')) {
              msg.phase = 'complete';
              msg.isComplete = true;
            }
            return msg;
          });

          $(this.selectors.messages).empty();

          // Only render complete messages
          this.conversation
            .filter(msg => msg.isComplete && msg.phase === 'complete')
            .forEach(message => this.renderMessage(message));

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
     * Load session ID from localStorage
     */
    loadSessionId() {
      try {
        const storedSessionId = localStorage.getItem('dehum_session_id');
        if (storedSessionId) {
          this.currentSessionId = storedSessionId;
        }
      } catch (e) {
        this.currentSessionId = null;
      }
    },

    /**
     * Save session ID to localStorage
     */
    saveSessionId() {
      try {
        if (this.currentSessionId) {
          localStorage.setItem('dehum_session_id', this.currentSessionId);
        } else {
          localStorage.removeItem('dehum_session_id');
        }
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
    },

    /**
     * Escape HTML then convert markdown to HTML
     */
    formatContent(text) {
      // First escape any existing HTML to prevent XSS
      let processed = this.escapeHtml(text);

      // Split into lines for processing headings and lists
      const lines = processed.split('\n');
      const htmlLines = [];
      let inList = false;

      lines.forEach(line => {
        let formatted = line;

        // Headings
        if (formatted.startsWith('### ')) {
          formatted = `<h3>${formatted.slice(4)}</h3>`;
        } else if (formatted.startsWith('## ')) {
          formatted = `<h2>${formatted.slice(3)}</h2>`;
        } else if (formatted.startsWith('# ')) {
          formatted = `<h1>${formatted.slice(2)}</h1>`;
        }

        // Bold and italic (apply to all lines, including headings content)
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // Lists
        if (formatted.trim().startsWith('- ')) {
          if (!inList) {
            htmlLines.push('<ul>');
            inList = true;
          }
          htmlLines.push(`<li>${formatted.trim().slice(2)}</li>`);
        } else {
          if (inList) {
            htmlLines.push('</ul>');
            inList = false;
          }
          htmlLines.push(formatted);
        }
      });

      if (inList) {
        htmlLines.push('</ul>');
      }

      // Join back with <br> only where there were empty lines or between paragraphs
      processed = htmlLines.join('<br>');

      // Convert markdown links
      processed = processed.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, (match, label, url) => {
        const safeUrl = this.escapeHtml(url);
        return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`;
      });

      // Convert plain URLs to clickable links
      processed = processed.replace(/(^|[^"'])(https?:\/\/[^\s<>"']+)/g, (match, prefix, url) => {
        // Don't convert URLs that are already inside href attributes
        if (match.includes('href=')) return match;

        const safeUrl = this.escapeHtml(url);
        return `${prefix}<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${url}</a>`;
      });

      // No need for additional \n to <br> since we joined with <br>
      return processed;
    },

    /* Character counter */
    updateCharCount() {
      const current = $(this.selectors.input).val().length;
      const counterEl = $('#dehum-char-count');
      if (counterEl.length) {
        counterEl.text(`${current}/${this.maxLen}`);
        counterEl.toggleClass('exceeded', current > this.maxLen);
      }
    },

    /* Auto-resize textarea up to 25% container height or 180px */
    autoResizeInput() {
      const textarea = $(this.selectors.input)[0];
      if (!textarea) return;

      // Reset height to compute scrollHeight accurately
      textarea.style.height = 'auto';

      // Determine cap: 25% of chat container height (or 180px fallback)
      const container = $('.dehum-chat-container')[0];
      const maxPx = container ? container.clientHeight * 0.25 : 180;

      const newHeight = Math.min(textarea.scrollHeight, maxPx);
      textarea.style.height = newHeight + 'px';

      // Toggle scrollbar visibility
      textarea.style.overflowY = textarea.scrollHeight > maxPx ? 'auto' : 'hidden';
    },

    /**
     * Get AI service URL from WordPress
     */
    async getAIServiceURL() {
      try {
        const response = await $.ajax({
          url: dehumMVP.ajaxUrl,
          type: 'POST',
          data: {
            action: 'dehum_get_ai_service_url',
            nonce: dehumMVP.nonce
          }
        });

        if (response.success) {
          return response.data.url;
        }
      } catch (error) {
        console.error('Failed to get AI service URL:', error);
      }
      return null;
    },

    /**
     * Get AI service authentication header
     */
    async getAIServiceAuth() {
      try {
        const response = await $.ajax({
          url: dehumMVP.ajaxUrl,
          type: 'POST',
          data: {
            action: 'dehum_get_ai_service_auth',
            nonce: dehumMVP.nonce
          }
        });

        if (response.success && response.data.auth) {
          return response.data.auth;
        }
      } catch (error) {
        console.error('Failed to get AI service auth:', error);
      }
      return '';
    },

    /**
     * Save conversation to WordPress for admin logging
     */
    async saveConversationToWordPress(userMessage, assistantResponse) {
      try {
        await $.ajax({
          url: dehumMVP.ajaxUrl,
          type: 'POST',
          data: {
            action: 'dehum_mvp_save_conversation',
            message: userMessage,
            response: assistantResponse,
            session_id: this.currentSessionId,
            nonce: dehumMVP.nonce
          }
        });
      } catch (error) {
        console.error('Failed to save conversation to WordPress:', error);
        // Don't throw - this is just for logging
      }
    },

    /**
     * Generate a session ID if we don't have one
     */
    generateSessionId() {
      return new Date().toISOString().slice(0, 19).replace(/[:-]/g, '') + '_' + Math.random().toString(36).substr(2, 8);
    },

    /**
     * Update an existing message element
     */
    updateMessage(messageElement, newContent) {
      const contentDiv = messageElement.find('.dehum-message__bubble');
      if (contentDiv.length) {
        contentDiv.html(this.formatContent(newContent));
      }
    },

    /**
     * Save an incomplete state (e.g., 'thinking', 'streaming')
     */
    saveIncompleteState(phase, content) {
      if (this.conversation.length > 0) {
        const lastMessage = this.conversation[this.conversation.length - 1];
        if (lastMessage.type === 'assistant') {
          // Update existing assistant message
          lastMessage.phase = phase;
          lastMessage.isComplete = false;
          lastMessage.content = content;
          lastMessage.timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
      }
      this.saveConversation();
    },

    /**
     * Clear all incomplete states
     */
    clearIncompleteState() {
      this.conversation = this.conversation.filter(msg => msg.phase === 'complete');
      this.saveConversation();
    },

    /**
     * Check for interrupted analysis on chat initialization
     */
    checkForInterruption() {
      const incompleteMessages = this.conversation.filter(msg => !msg.isComplete || msg.phase !== 'complete');

      if (incompleteMessages.length > 0) {
        const lastIncomplete = incompleteMessages[incompleteMessages.length - 1];

        if (lastIncomplete.phase === 'thinking' || lastIncomplete.phase === 'streaming') {
          this.showInterruptionMessage(lastIncomplete);
        }
      }
    },

    /**
     * Show interruption message with retry button
     */
    showInterruptionMessage(incompleteMessage) {
      const interruptionHtml = `
        <div class="dehum-message dehum-message--interruption">
          <div class="dehum-message__bubble">
            ⚠️ Analysis was interrupted while ${incompleteMessage.phase === 'thinking' ? 'thinking' : 'generating recommendations'}.
            <br><br>
            <button class="dehum-retry-btn" onclick="ChatWidget.retryAnalysis()">
              🔄 Click to retry analysis
            </button>
          </div>
          <div class="dehum-message__timestamp">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
        </div>
      `;

      $(this.selectors.messages).append(interruptionHtml);
      this.scrollToBottom();
    },

    /**
     * Retry analysis after interruption
     */
    retryAnalysis() {
      // Remove interruption message
      $('.dehum-message--interruption').remove();

      // Clear incomplete states
      this.clearIncompleteState();

      // Get the last user message to retry
      const lastUserMessage = this.conversation
        .filter(msg => msg.type === 'user')
        .pop();

      if (lastUserMessage) {
        // Remove the incomplete assistant response
        this.conversation = this.conversation.filter(msg => msg.type !== 'assistant' || msg.isComplete);
        this.saveConversation();

        // Retry the analysis
        this.lockInterface();
        this.showTypingIndicator();

        this.callStreamingAPI(lastUserMessage.content)
          .catch(error => {
            console.log('Streaming failed on retry, falling back to regular API:', error);
            return this.callAPI(lastUserMessage.content);
          })
          .then(response => {
            // Only handle response if streaming didn't already handle it
            if (response && !this.streamingComplete) {
              this.hideTypingIndicator();
              this.addMessage('assistant', response.response);

              // Store session ID from response
              if (response.session_id) {
                this.currentSessionId = response.session_id;
                this.saveSessionId();
              }
            }
          })
          .catch(error => {
            this.hideTypingIndicator();
            this.addMessage('error', error.message || 'Sorry, something went wrong. Please try again.');
          })
          .finally(() => {
            this.streamingComplete = false;
            this.unlockInterface();
          });
      }
    }
  };

  // Initialize when DOM is ready
  $(document).ready(() => {
    ChatWidget.init();
  });

})(jQuery);