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
    currentSessionId: null,
    streamingComplete: false,

    // Simplified phase state management
    currentPhase: {
      phase: null,
      messageIndex: -1,
      elements: {
        summary: null,
        recommendations: null
      },
      content: {
        tools: '',
        summary: '',
        recommendations: ''
      }
    },

    // Debouncing
    debounceTimers: {},

    // Privacy notice for localStorage
    localStorageNoticeShown: false,

    /**
     * Initialize the chat widget
     */
    init() {
      this.bindEvents();
      this.setupAccessibility();
      this.checkLocalStoragePrivacy();

      // Load conversation and session ID
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
     * Check and notify about localStorage usage for privacy compliance
     */
    checkLocalStoragePrivacy() {
      if (!this.localStorageNoticeShown && !localStorage.getItem('dehum_privacy_acknowledged')) {
        console.info('Dehumidifier Assistant: This chat uses browser storage to save your conversation history locally. No data is shared with third parties.');
        localStorage.setItem('dehum_privacy_acknowledged', 'true');
        this.localStorageNoticeShown = true;
      }
    },

    /**
     * Debounce function to limit rapid function calls
     */
    debounce(func, delay, key = 'default') {
      if (this.debounceTimers[key]) {
        clearTimeout(this.debounceTimers[key]);
      }
      this.debounceTimers[key] = setTimeout(func, delay);
    },

    /**
     * Reset phase state for new conversation
     */
    resetPhaseState() {
      this.currentPhase = {
        phase: null,
        messageIndex: -1,
        elements: {
          summary: null,
          recommendations: null
        },
        content: {
          tools: '',
          summary: '',
          recommendations: ''
        }
      };
    },

    /**
     * Announce messages to screen readers for accessibility
     */
    announceToScreenReader(message) {
      // Create a visually hidden element that screen readers can access
      const announcement = $('<div>')
        .attr('aria-live', 'polite')
        .attr('aria-atomic', 'true')
        .addClass('sr-only')
        .css({
          position: 'absolute',
          width: '1px',
          height: '1px',
          padding: '0',
          margin: '-1px',
          overflow: 'hidden',
          clip: 'rect(0,0,0,0)',
          whiteSpace: 'nowrap',
          border: '0'
        })
        .text(message);

      $('body').append(announcement);

      // Remove after announcement is read
      setTimeout(() => {
        announcement.remove();
      }, 1000);
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

      // Update char count on input with debouncing for performance
      $(this.selectors.input).on('input', () => {
        // Run immediately for responsiveness
        this.updateCharCount();
        // Debounce the more expensive auto-resize operation
        this.debounce(() => {
          this.autoResizeInput();
        }, 100, 'autoResize');
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

      // Only reload conversation if messages container is empty (first open)
      // This prevents duplicate welcome messages on subsequent opens
      if ($(this.selectors.messages).children().length === 0) {
        this.loadConversation();
      }
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
      this.resetPhaseState(); // Clear phase state to prevent tool content issues

      // Clear storage
      this.saveConversation();
      this.saveSessionId();

      // Clear messages and show welcome message (this handles clearing and adding properly)
      $(this.selectors.messages).empty();
      this.showWelcomeMessage();

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

      // Reset phase state for new conversation turn
      this.resetPhaseState();

      // Lock the interface immediately
      this.lockInterface();

      // Add user message to UI
      this.addMessage('user', message);
      $(this.selectors.input).val('');

      // Announce new message to screen readers
      this.announceToScreenReader(`You said: ${message}`);

      // Show typing indicator
      this.showTypingIndicator();

      // Try streaming first, fallback to regular if it fails
      this.callStreamingAPI(message)
        .catch(error => {
          console.log('Streaming failed, falling back to regular API:', error);
          return this.callAPI(message);
        })
        .then(async response => {
          // Only handle response if streaming didn't already handle it
          if (response && !this.streamingComplete) {
            this.hideTypingIndicator();

            // For fallback API, we don't have separate tool content, so use regular message
            const messageElement = this.addMessage('assistant', response.response, true);

            // Update conversation with proper structure for consistency
            if (this.conversation.length > 0) {
              const lastMessage = this.conversation[this.conversation.length - 1];
              if (lastMessage.type === 'assistant') {
                lastMessage.toolContent = null; // No separate tool content from fallback API
                lastMessage.mainContent = response.response;
              }
            }

            // Store session ID from response
            if (response.session_id) {
              this.currentSessionId = response.session_id;
              this.saveSessionId();
            }

            // IMPORTANT: Save conversation when using fallback API
            // The WordPress AJAX handler already logs it, but we call this for consistency
            // and to ensure admin logs are updated
            try {
              await this.saveConversationToWordPress(message, response.response);
            } catch (error) {
              console.warn('Failed to save conversation via WordPress AJAX (this may be expected if handled by WordPress):', error);
              // Don't interrupt user experience - this is just for admin logging
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

      // Automatically restore focus to input field so user can continue typing
      if (this.isOpen) {
        setTimeout(() => {
          $(this.selectors.input).focus();
        }, 100);
      }
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

        let summaryElement = null;
        let recsElement = null;
        let currentContent = '';
        let recsContent = '';
        let toolContent = ''; // Separate container for tool progress messages
        let isThinking = false;
        let currentMessageIndex = -1; // Track current message in conversation history
        let currentPhase = null;

        // Make streaming request with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout

        let response;
        try {
          response = await fetch(streamUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': await this.getAIServiceAuth()
            },
            body: JSON.stringify(requestData),
            signal: controller.signal
          });
        } catch (fetchError) {
          clearTimeout(timeoutId);
          if (fetchError.name === 'AbortError') {
            throw new Error('Request timed out after 60 seconds');
          }
          throw new Error(`Network error: ${fetchError.message}`);
        }

        clearTimeout(timeoutId);

        if (!response.ok) {
          let errorMessage = `Streaming request failed: ${response.status}`;
          try {
            const errorData = await response.text();
            if (errorData) {
              errorMessage += ` - ${errorData}`;
            }
          } catch (e) {
            // Ignore parsing errors for error message
          }
          throw new Error(errorMessage);
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
                const jsonStr = line.slice(6).trim(); // Remove "data: " and trim whitespace
                if (!jsonStr) continue; // Skip empty lines

                let data;
                try {
                  data = JSON.parse(jsonStr);
                } catch (parseError) {
                  console.warn('Failed to parse streaming JSON:', parseError, 'Raw data:', jsonStr);
                  continue; // Skip malformed JSON chunks
                }

                // Validate data structure
                if (!data || typeof data !== 'object') {
                  console.warn('Invalid data structure in stream:', data);
                  continue;
                }

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
                    this.saveIncompleteState('thinking', currentContent, toolContent);
                  }
                } else if (data.is_streaming_chunk) {
                  // Handle both content chunks and tool progress messages
                  const phase = data.metadata?.phase || 'default';

                  // Fix: If this is a tool phase message, treat it as a separate progress message
                  if (phase === 'tools') {
                    // Tool progress messages - display as separate content
                    if (!summaryElement) {
                      this.hideTypingIndicator();
                      summaryElement = this.addMessage('assistant', '', true);
                      currentMessageIndex = this.conversation.length - 1;
                    }
                    // Add tool progress to separate container
                    toolContent += (toolContent ? '\n' : '') + data.message;
                    // Display tool content immediately
                    this.updateMessage(summaryElement, toolContent);
                    currentPhase = phase;
                  } else {
                    // Regular content chunks (initial_summary, recommendations)

                    // Create new message element if phase changed or no current element
                    if (phase !== currentPhase || (phase === 'initial_summary' && !summaryElement) || (phase === 'recommendations' && !recsElement)) {
                      this.hideTypingIndicator();
                      if (phase === 'initial_summary') {
                        summaryElement = this.addMessage('assistant', '', true);
                      } else if (phase === 'recommendations') {
                        recsElement = this.addMessage('assistant', '', true);
                      }
                      currentMessageIndex = this.conversation.length - 1;
                      currentPhase = phase;
                    }

                    // Append chunk to appropriate element without echoing summary in recs
                    if (phase === 'initial_summary') {
                      currentContent += data.message;
                      // Combine tool content with summary content for display
                      const displayContent = toolContent ? toolContent + '\n\n' + currentContent : currentContent;
                      this.updateMessage(summaryElement, displayContent);
                    } else if (phase === 'recommendations') {
                      if (isThinking) {
                        this.hideThinkingIndicator();
                        isThinking = false;
                      }
                      recsContent += data.message;
                      this.updateMessage(recsElement, recsContent);  // Only recs content
                    }

                    // Save state - include tool content in saved state
                    let saveContent;
                    if (phase === 'initial_summary') {
                      saveContent = toolContent ? toolContent + '\n\n' + currentContent : currentContent;
                      this.saveIncompleteState(phase, saveContent, toolContent);
                    } else {
                      saveContent = recsContent;
                      this.saveIncompleteState(phase, saveContent, toolContent);
                    }
                  }

                  // Scroll to bottom after each chunk update (with timeout for DOM render)
                  setTimeout(() => this.scrollToBottom(), 0);

                } else if (data.is_progress_update) {
                  // Fix: Handle old-style progress updates without creating message bubbles
                  // Just log for debugging - could be used for progress indicators in future
                  console.debug('Tool progress:', data.metadata?.status, data.metadata?.tool_name);

                } else if (data.is_final) {
                  // Final message - streaming is complete
                  this.hideThinkingIndicator();
                  this.streamingComplete = true;

                  // If we didn't get any partial content before the final message,
                  // use the data.message directly so the user sees something.
                  if (!currentContent && !recsContent && !toolContent && data.message) {
                    currentContent = data.message;
                  }

                  // Ensure there's a message element to update / create if it doesn't exist
                  if (!summaryElement) {
                    this.hideTypingIndicator();
                    summaryElement = this.addMessage('assistant', currentContent, true);
                    currentMessageIndex = this.conversation.length - 1;
                  }

                  // Ensure final content combines everything for history (tool + summary + recommendations)
                  let finalContent = '';
                  if (toolContent) {
                    finalContent += toolContent;
                  }
                  if (currentContent) {
                    finalContent += (finalContent ? '\n\n' : '') + currentContent;
                  }
                  if (recsContent) {
                    finalContent += (finalContent ? '\n\n' : '') + recsContent;
                  }

                  // Mark as complete in conversation history with separated content
                  if (currentMessageIndex >= 0 && currentMessageIndex < this.conversation.length) {
                    this.conversation[currentMessageIndex].content = finalContent;
                    this.conversation[currentMessageIndex].toolContent = toolContent || null;
                    this.conversation[currentMessageIndex].mainContent = (currentContent || '') + (recsContent ? '\n\n' + recsContent : '');
                    this.conversation[currentMessageIndex].phase = 'complete';
                    this.conversation[currentMessageIndex].isComplete = true;
                    this.saveConversation();
                  }

                  // Scroll to bottom after final update (with timeout)
                  setTimeout(() => this.scrollToBottom(), 0);

                  // Clear incomplete state
                  this.clearIncompleteState();

                } else if (data.metadata?.phase === 'initial_complete' || data.metadata?.phase === 'thinking_complete') {
                  // Phase completion markers - update current content but don't duplicate
                  if (data.metadata.phase === 'initial_complete') {
                    // Phase 1 complete
                    if (!summaryElement) {
                      this.hideTypingIndicator();
                      summaryElement = this.addMessage('assistant', data.message, true);
                      currentContent = data.message;
                      currentMessageIndex = this.conversation.length - 1;
                    } else if (currentContent !== data.message) {
                      // Only update if content is different (avoid duplication)
                      currentContent = data.message;
                      this.updateMessage(summaryElement, currentContent);
                    }
                  }
                  // thinking_complete doesn't need content update - just phase transition

                  // Scroll to bottom after phase completion (with timeout)
                  setTimeout(() => this.scrollToBottom(), 0);

                } else {
                  // Handle other phase responses (thinking character streaming, etc.)
                  if (data.metadata?.char_streaming) {
                    // Character-by-character streaming (thinking message)
                    // Don't create message elements for individual characters during thinking
                    return;
                  } else if (!summaryElement) {
                    // Initial response for cases without streaming
                    this.hideTypingIndicator();
                    summaryElement = this.addMessage('assistant', data.message || '', true);
                    currentContent = data.message || '';
                    currentMessageIndex = this.conversation.length - 1;

                    // Mark as initial phase in conversation history
                    if (currentMessageIndex >= 0) {
                      this.conversation[currentMessageIndex].phase = 'initial';
                      this.conversation[currentMessageIndex].isComplete = false;
                      this.saveConversation();
                    }
                  }

                  // Scroll to bottom after other updates (with timeout)
                  setTimeout(() => this.scrollToBottom(), 0);
                }
              } catch (e) {
                console.error('Error processing streaming chunk:', e, 'Line:', line);
                // Continue processing other chunks even if one fails
              }
            }
          }
        }

        // Save complete conversation to WordPress - include all content types
        let finalContentForSave = '';
        if (toolContent) {
          finalContentForSave += toolContent;
        }
        if (currentContent) {
          finalContentForSave += (finalContentForSave ? '\n\n' : '') + currentContent;
        }
        if (recsContent) {
          finalContentForSave += (finalContentForSave ? '\n\n' : '') + recsContent;
        }
        await this.saveConversationToWordPress(message, finalContentForSave);

        return { session_id: this.currentSessionId, response: finalContentForSave };

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
          phase: 'complete',
          isComplete: true,
          // Preserve tool content separately for proper reconstruction
          toolContent: null,
          mainContent: content
        };
        this.conversation.push(message);
        this.saveConversation();
      }

      // Add copy button for assistant messages if enabled
      const copyConfig = dehumMVP.copyButtons || { enabled: true, ariaLabel: 'Copy message', title: 'Copy to clipboard' };
      const copyButtonHtml = (type === 'assistant' && content.trim() && copyConfig.enabled) ? `
        <button class="dehum-copy-btn" aria-label="${copyConfig.ariaLabel}" title="${copyConfig.title}">
          <span class="material-symbols-outlined">content_copy</span>
        </button>
      ` : '';

      const messageHtml = `
        <div class="${messageClass}" role="article" aria-label="${type} message">
          <div class="dehum-message__bubble">${this.formatContent(content)}${copyButtonHtml}</div>
          <div class="dehum-message__timestamp">${timestamp}</div>
        </div>
      `;

      const $message = $(messageHtml);
      $(this.selectors.messages).append($message);

      // Bind copy functionality if copy button exists
      if (type === 'assistant' && content.trim() && copyConfig.enabled) {
        this.bindCopyButton($message.find('.dehum-copy-btn'), content);
      }

      this.scrollToBottom();

      // Announce assistant messages to screen readers
      if (type === 'assistant' && content) {
        // Use debouncing to avoid overwhelming screen readers during streaming
        this.debounce(() => {
          this.announceToScreenReader(`Assistant responded: ${content.substring(0, 100)}${content.length > 100 ? '...' : ''}`);
        }, 500, 'announce');
      }

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
     * Show welcome message by fetching it from the server
     */
    async showWelcomeMessage() {
      // Clear any existing welcome messages first (scoped to messages container)
      $(this.selectors.messages).find('.dehum-welcome').remove();

      try {
        const response = await $.ajax({
          url: dehumMVP.ajaxUrl,
          type: 'POST',
          data: {
            action: 'dehum_get_welcome_message',
            nonce: dehumMVP.nonce
          }
        });

        if (response.success && response.data.message) {
          const welcomeHtml = `
            <div class="dehum-welcome">
              ${response.data.message}
            </div>
          `;
          $(this.selectors.messages).append(welcomeHtml);
          this.scrollToBottom();
        } else {
          // Fallback welcome message if server request fails
          this.showFallbackWelcomeMessage();
        }
      } catch (error) {
        console.error('Failed to load welcome message:', error);
        // Fallback welcome message if server request fails
        this.showFallbackWelcomeMessage();
      }
    },

    /**
     * Show fallback welcome message (in case server request fails)
     */
    showFallbackWelcomeMessage() {
      // Clear any existing welcome messages first (scoped to messages container)
      $(this.selectors.messages).find('.dehum-welcome').remove();

      const welcomeHtml = `
        <div class="dehum-welcome">
          <strong>Welcome! I'm your dehumidifier sizing assistant.</strong><br>
          I can help you with:<br>
          • <strong>Sizing recommendations</strong> - Provide space details (length × width × height in meters), current humidity (RH%), and target humidity (RH%)<br>
          • <strong>Product specifications</strong> - Ask about features, technical details, or performance data<br>
          • <strong>Installation & maintenance</strong> - Questions about setup, operation, or troubleshooting<br><br>
          Is this for a pool room or regular space? What can I help you with today?
        </div>
      `;
      $(this.selectors.messages).append(welcomeHtml);
      this.scrollToBottom();
    },

    /**
     * Render a message from history
     */
    renderMessage(message) {
      const messageClass = `dehum-message dehum-message--${message.type}`;
      const copyConfig = dehumMVP.copyButtons || { enabled: true, ariaLabel: 'Copy message', title: 'Copy to clipboard' };

      // Check if this message has separate tool content (from streaming)
      if (message.type === 'assistant' && message.toolContent && message.mainContent) {
        // Render tool content first as a separate bubble
        const toolMessageHtml = `
          <div class="${messageClass}" role="article" aria-label="tool usage message">
            <div class="dehum-message__bubble">${this.formatContent(message.toolContent)}</div>
            <div class="dehum-message__timestamp">${message.timestamp}</div>
          </div>
        `;
        $(this.selectors.messages).append(toolMessageHtml);

        // Then render the main content as a separate bubble with copy button
        const copyButtonHtml = (copyConfig.enabled) ? `
          <button class="dehum-copy-btn" aria-label="${copyConfig.ariaLabel}" title="${copyConfig.title}">
            <span class="material-symbols-outlined">content_copy</span>
          </button>
        ` : '';

        const mainMessageHtml = `
          <div class="${messageClass}" role="article" aria-label="${message.type} message">
            <div class="dehum-message__bubble">${this.formatContent(message.mainContent)}${copyButtonHtml}</div>
            <div class="dehum-message__timestamp">${message.timestamp}</div>
          </div>
        `;

        const $mainMessage = $(mainMessageHtml);
        $(this.selectors.messages).append($mainMessage);

        // Bind copy functionality for the main content (full response)
        if (copyConfig.enabled) {
          this.bindCopyButton($mainMessage.find('.dehum-copy-btn'), message.content);
        }
      } else {
        // Render as single message (original behavior)
        const copyButtonHtml = (message.type === 'assistant' && message.content.trim() && copyConfig.enabled) ? `
          <button class="dehum-copy-btn" aria-label="${copyConfig.ariaLabel}" title="${copyConfig.title}">
            <span class="material-symbols-outlined">content_copy</span>
          </button>
        ` : '';

        const messageHtml = `
          <div class="${messageClass}" role="article" aria-label="${message.type} message">
            <div class="dehum-message__bubble">${this.formatContent(message.content)}${copyButtonHtml}</div>
            <div class="dehum-message__timestamp">${message.timestamp}</div>
          </div>
        `;

        const $message = $(messageHtml);
        $(this.selectors.messages).append($message);

        // Bind copy functionality if copy button exists
        if (message.type === 'assistant' && message.content.trim() && copyConfig.enabled) {
          this.bindCopyButton($message.find('.dehum-copy-btn'), message.content);
        }
      }
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
            // Migrate to new tool content structure for backward compatibility
            if (!msg.hasOwnProperty('toolContent')) {
              msg.toolContent = null;
              msg.mainContent = msg.content;
            }
            return msg;
          });

          // Clear messages container
          $(this.selectors.messages).empty();

          // Filter complete messages to render
          const completeMessages = this.conversation.filter(msg => msg.isComplete && msg.phase === 'complete');

          if (completeMessages.length > 0) {
            // Render existing conversation
            completeMessages.forEach(message => this.renderMessage(message));
          } else {
            // No complete messages, show welcome message
            this.showWelcomeMessage();
          }

          this.scrollToBottom();
        } else {
          // No conversation history, clear any existing messages and show welcome
          $(this.selectors.messages).empty();
          this.showWelcomeMessage();
        }
      } catch (e) {
        this.conversation = [];
        // Clear messages and show welcome message on error
        $(this.selectors.messages).empty();
        this.showWelcomeMessage();
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
        const response = await $.ajax({
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

        if (response.success) {
          console.log('Conversation saved to WordPress successfully');
        } else {
          console.error('WordPress rejected conversation save:', response.data?.message || 'Unknown error');
        }
      } catch (error) {
        console.error('Failed to save conversation to WordPress:', error);

        // Log additional debugging info
        if (error.status === 403) {
          console.error('403 Error - Possible causes:');
          console.error('1. Chat may be restricted to logged-in users only (check admin settings)');
          console.error('2. Nonce verification failed');
          console.error('3. User does not have required permissions');
        } else if (error.status === 429) {
          console.error('429 Error - Rate limited');
        }

        // Re-throw so calling code can handle appropriately
        throw error;
      }
    },

    /**
     * Generate a cryptographically secure session ID
     */
    generateSessionId() {
      // Use crypto.randomUUID if available (modern browsers)
      if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
      }

      // Fallback for older browsers
      const timestamp = Date.now().toString(36);
      const randomPart = Math.random().toString(36).substr(2, 9);
      const extraRandom = Math.random().toString(36).substr(2, 9);
      return `${timestamp}_${randomPart}_${extraRandom}`;
    },

    /**
     * Bind copy functionality to a copy button
     */
    bindCopyButton($button, content) {
      $button.on('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.copyToClipboard(content, $button);
      });
    },

    /**
     * Copy content to clipboard with visual feedback
     */
    async copyToClipboard(content, $button) {
      try {
        // Strip HTML formatting for clean text copy
        const textContent = this.stripHtmlForCopy(content);

        // Use modern Clipboard API if available
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(textContent);
        } else {
          // Fallback for older browsers
          this.fallbackCopyToClipboard(textContent);
        }

        // Visual feedback
        this.showCopyFeedback($button, 'success');

        // Announce to screen readers
        this.announceToScreenReader('Message copied to clipboard');

      } catch (error) {
        console.error('Failed to copy to clipboard:', error);
        this.showCopyFeedback($button, 'error');
        this.announceToScreenReader('Failed to copy message');
      }
    },

    /**
     * Fallback copy method for older browsers
     */
    fallbackCopyToClipboard(text) {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      textArea.style.top = '-999999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      try {
        document.execCommand('copy');
      } finally {
        document.body.removeChild(textArea);
      }
    },

    /**
     * Strip HTML formatting for clean text copy
     */
    stripHtmlForCopy(htmlContent) {
      // Create a temporary element to parse HTML
      const tempDiv = $('<div>').html(htmlContent);

      // Convert specific HTML elements to readable text
      tempDiv.find('h1, h2, h3, h4, h5, h6').each(function () {
        $(this).prepend('# ');
      });

      tempDiv.find('li').each(function () {
        $(this).prepend('• ');
      });

      tempDiv.find('br').replaceWith('\n');
      tempDiv.find('p').after('\n');

      // Get clean text content
      let textContent = tempDiv.text();

      // Clean up extra whitespace
      textContent = textContent.replace(/\n\s*\n/g, '\n\n').trim();

      return textContent;
    },

    /**
     * Show visual feedback for copy operation
     */
    showCopyFeedback($button, type) {
      const originalIcon = $button.find('.material-symbols-outlined').text();
      const originalTitle = $button.attr('title');

      if (type === 'success') {
        $button.find('.material-symbols-outlined').text('check');
        $button.attr('title', 'Copied!').addClass('dehum-copy-btn--success');
      } else {
        $button.find('.material-symbols-outlined').text('error');
        $button.attr('title', 'Copy failed').addClass('dehum-copy-btn--error');
      }

      // Reset after 2 seconds
      setTimeout(() => {
        $button.find('.material-symbols-outlined').text(originalIcon);
        $button.attr('title', originalTitle);
        $button.removeClass('dehum-copy-btn--success dehum-copy-btn--error');
      }, 2000);
    },

    /**
     * Update an existing message element
     */
    updateMessage(messageElement, newContent) {
      const contentDiv = messageElement.find('.dehum-message__bubble');
      if (contentDiv.length) {
        // Check if this is an assistant message and should have a copy button
        const isAssistantMessage = messageElement.hasClass('dehum-message--assistant');
        const copyConfig = dehumMVP.copyButtons || { enabled: true, ariaLabel: 'Copy message', title: 'Copy to clipboard' };
        const copyButtonHtml = (isAssistantMessage && newContent.trim() && copyConfig.enabled) ? `
          <button class="dehum-copy-btn" aria-label="${copyConfig.ariaLabel}" title="${copyConfig.title}">
            <span class="material-symbols-outlined">content_copy</span>
          </button>
        ` : '';

        contentDiv.html(this.formatContent(newContent) + copyButtonHtml);

        // Bind copy functionality if copy button was added
        if (isAssistantMessage && newContent.trim() && copyConfig.enabled) {
          this.bindCopyButton(contentDiv.find('.dehum-copy-btn'), newContent);
        }
      }
      // Scroll to bottom after updating the message content (with timeout for DOM render)
      setTimeout(() => this.scrollToBottom(), 0);
    },

    /* Save an incomplete state (e.g., 'thinking', 'streaming') */
    saveIncompleteState(phase, content, toolContent = null) {
      if (this.conversation.length > 0) {
        const lastMessage = this.conversation[this.conversation.length - 1];
        if (lastMessage.type === 'assistant') {
          // Update existing assistant message
          lastMessage.phase = phase;
          lastMessage.isComplete = false;
          lastMessage.content = content;
          lastMessage.timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

          // Preserve tool content separately if provided
          if (toolContent !== null) {
            lastMessage.toolContent = toolContent;
            // Separate main content from tool content
            lastMessage.mainContent = content.replace(toolContent, '').replace(/^\n\n/, '').trim();
          } else {
            lastMessage.mainContent = content;
          }
        }
      }
      this.saveConversation();
    },

    /* Clear all incomplete states */
    clearIncompleteState() {
      this.conversation = this.conversation.filter(msg => msg.phase === 'complete');
      this.saveConversation();
    },

    /* Check for interrupted analysis on chat initialization */
    checkForInterruption() {
      const incompleteMessages = this.conversation.filter(msg => !msg.isComplete || msg.phase !== 'complete');

      if (incompleteMessages.length > 0) {
        const lastIncomplete = incompleteMessages[incompleteMessages.length - 1];

        if (lastIncomplete.phase === 'thinking' || lastIncomplete.phase === 'streaming') {
          this.showInterruptionMessage(lastIncomplete);
        }
      }
    },

    /* Show interruption message with retry button */
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

    /* Retry analysis after interruption */
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
        this.resetPhaseState(); // Reset phase state for clean retry
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

              // For retry fallback API, ensure proper structure
              const messageElement = this.addMessage('assistant', response.response, true);

              // Update conversation with proper structure for consistency
              if (this.conversation.length > 0) {
                const lastMessage = this.conversation[this.conversation.length - 1];
                if (lastMessage.type === 'assistant') {
                  lastMessage.toolContent = null; // No separate tool content from fallback API
                  lastMessage.mainContent = response.response;
                }
              }

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