/**
 * Dehumidifier Assistant Chat Widget
 * Modern, modular JavaScript implementation inspired by Open WebUI
 * Enhanced with better UX, improved state management, and image rendering support
 */

(function ($) {
  'use strict';

  // ===============================
  // BUNDLED MARKED.JS FOR MARKDOWN
  // ===============================

  // Simplified markdown parser (lightweight alternative to full marked.js)
  // Enhanced with image rendering support inspired by Open WebUI
  const MarkdownRenderer = {
    /**
     * Parse markdown text to HTML with image support
     */
    parse(text) {
      if (!text) return '';

      // Escape HTML first
      let html = this.escapeHtml(text);

      // Convert markdown patterns in order (images before links to avoid conflicts)
      html = this.parseHeadings(html);
      html = this.parseLists(html);
      html = this.parseCodeBlocks(html);
      html = this.parseInlineCode(html);
      html = this.parseImages(html); // Parse images before links
      html = this.parseLinks(html);
      html = this.parseBold(html);
      html = this.parseItalic(html);
      html = this.parseLineBreaks(html);

      return html;
    },

    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    },

    parseHeadings(text) {
      return text.replace(/^### (.*$)/gm, '<h3>$1</h3>')
        .replace(/^## (.*$)/gm, '<h2>$1</h2>')
        .replace(/^# (.*$)/gm, '<h1>$1</h1>');
    },

    parseLists(text) {
      const lines = text.split('\n');
      const result = [];
      let inList = false;

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmedLine = line.trim();

        if (trimmedLine.startsWith('- ') || trimmedLine.startsWith('• ')) {
          if (!inList) {
            result.push('<ul>');
            inList = true;
          }
          const listText = trimmedLine.startsWith('• ') ? trimmedLine.slice(2).trim() : trimmedLine.slice(2).trim();
          result.push(`<li>${listText}</li>`);
        } else if (inList && trimmedLine === '') {
          // It's a blank line within a list. Look ahead to see if the list continues.
          const nextLine = lines[i + 1];
          if (nextLine && (nextLine.trim().startsWith('- ') || nextLine.trim().startsWith('• '))) {
            // The list continues after a blank line. Add a spacer to create one line of whitespace.
            result.push('<li class="dehum-list-spacer"></li>');
          } else {
            // The list ends here.
            result.push('</ul>');
            inList = false;
            result.push(line); // Pass the blank line through
          }
        } else {
          if (inList) {
            result.push('</ul>');
            inList = false;
          }
          result.push(line);
        }
      }

      if (inList) {
        result.push('</ul>');
      }

      return result.join('\n');
    },

    parseCodeBlocks(text) {
      return text.replace(/```[\s\S]*?```/g, (match) => {
        const code = match.slice(3, -3).trim();
        return `<pre><code>${code}</code></pre>`;
      });
    },

    parseInlineCode(text) {
      return text.replace(/`([^`]+)`/g, '<code>$1</code>');
    },

    /**
     * Parse markdown images with security validation and error handling
     * Inspired by Open WebUI's image handling approach
     */
    parseImages(text) {
      // Match markdown image syntax: ![alt text](url "optional title")
      return text.replace(/!\[([^\]]*)\]\(([^)]+)(?:\s+"([^"]*)")?\)/g, (match, alt, url, title) => {
        // Security validation: only allow HTTPS URLs
        if (!this.isValidImageUrl(url)) {
          return `<div class="dehum-image-error" role="img" aria-label="${alt || 'Invalid image'}"><span class="dehum-image-error-icon">🖼️</span><span class="dehum-image-error-text">${alt || 'Image unavailable'} (Invalid URL)</span></div>`;
        }

        // Create image element with lazy loading and error handling
        const escapedAlt = this.escapeHtml(alt || 'Image');
        const escapedTitle = title ? this.escapeHtml(title) : '';
        const titleAttr = escapedTitle ? ` title="${escapedTitle}"` : '';

        return `<img class="dehum-chat-image" src="${this.escapeHtml(url)}" alt="${escapedAlt}"${titleAttr} loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" /><div class="dehum-image-error" style="display: none;" role="img" aria-label="${escapedAlt}"><span class="dehum-image-error-icon">🖼️</span><span class="dehum-image-error-text">${escapedAlt}</span><span class="dehum-image-error-detail">Failed to load image</span></div>`;
      });
    },

    /**
     * Validate image URLs for security
     */
    isValidImageUrl(url) {
      try {
        const urlObj = new URL(url);

        // Only allow HTTPS URLs for security
        if (urlObj.protocol !== 'https:') {
          return false;
        }

        // Optional: Add domain whitelist check
        const allowedDomains = dehumMVP.allowedImageDomains || [];
        if (allowedDomains.length > 0 && !allowedDomains.includes(urlObj.hostname)) {
          console.warn(`Image domain not in whitelist: ${urlObj.hostname}`);
          // Still allow if no whitelist is configured, just warn
        }

        return true;
      } catch (e) {
        return false;
      }
    },

    parseLinks(text) {
      // Markdown links (avoid double-processing images)
      text = text.replace(/(?<!\!)\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

      // Auto-detect URLs (avoid URLs already in image tags)
      text = text.replace(/(^|[^"'=])(https?:\/\/[^\s<>"']+)/g,
        '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');

      return text;
    },

    parseBold(text) {
      return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    },

    parseItalic(text) {
      return text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    },

    parseLineBreaks(text) {
      // Process line breaks more carefully to avoid breaks between list items
      let result = text;

      // First, protect list content from getting line breaks
      result = result.replace(/(<ul>[\s\S]*?<\/ul>)/g, (match) => {
        // Inside lists, remove newlines between li tags completely
        return match.replace(/(<\/li>)\s*\n\s*(<li>)/g, '$1$2');
      });

      // Then handle remaining line breaks for non-list content
      result = result.replace(/\n\n/g, '<br><br>'); // Paragraph breaks
      result = result.replace(/\n/g, '<br>'); // Single line breaks

      return result;
    }
  };

  // ===============================
  // MESSAGE RENDERER
  // ===============================

  const MessageRenderer = {
    /**
     * Render a message with proper formatting and components
     * Enhanced with image error handling inspired by Open WebUI
     */
    render(type, content, options = {}) {
      const messageClass = `dehum-message dehum-message--${type}`;
      const timestamp = options.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      // Format content based on type
      let formattedContent = '';
      if (type === 'assistant') {
        formattedContent = MarkdownRenderer.parse(content);
      } else {
        formattedContent = this.escapeHtml(content);
      }

      // Add copy button for assistant messages
      const copyButton = (type === 'assistant' && content.trim() && options.enableCopyButton !== false)
        ? this.renderCopyButton()
        : '';

      const messageHtml = `
        <div class="${messageClass} dehum-fade-in" role="article" aria-label="${type} message">
          <div class="dehum-message__bubble">
            ${formattedContent}
            ${copyButton}
          </div>
          <div class="dehum-message__timestamp">${timestamp}</div>
        </div>
      `;

      const $message = $(messageHtml);

      // Bind image error handling and accessibility for images
      if (type === 'assistant') {
        this.bindImageHandlers($message);
      }

      return $message;
    },

    /**
     * Bind image error handlers and accessibility features
     */
    bindImageHandlers($message) {
      const images = $message.find('.dehum-chat-image');
      images.each(function () {
        const $img = $(this);
        const $errorDiv = $img.next('.dehum-image-error');

        // Enhanced error handling with accessibility announcement
        $img.on('error', function () {
          console.warn('Image failed to load:', $img.attr('src'));
          $img.hide();
          $errorDiv.show();

          // Announce error to screen readers
          AccessibilityManager.announce(`Image failed to load: ${$img.attr('alt')}`);
        });

        // Successful load handler for accessibility
        $img.on('load', function () {
          console.debug('Image loaded successfully:', $img.attr('src'));

          // Announce successful load to screen readers if it was previously failed
          if ($errorDiv.is(':visible')) {
            AccessibilityManager.announce(`Image loaded: ${$img.attr('alt')}`);
          }
        });

        // Add click handler for basic image viewing (inspired by Open WebUI)
        $img.on('click', function () {
          const src = $img.attr('src');
          const alt = $img.attr('alt');

          // Open image in new tab (lightweight alternative to modal)
          window.open(src, '_blank', 'noopener,noreferrer');

          // Announce click action
          AccessibilityManager.announce(`Opening image: ${alt}`);
        });

        // Add keyboard support for accessibility
        $img.attr('tabindex', '0').on('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            $img.click();
          }
        });
      });
    },

    renderCopyButton() {
      const config = dehumMVP.copyButtons || { enabled: true, ariaLabel: 'Copy message', title: 'Copy to clipboard' };
      return `
        <button class="dehum-copy-btn" aria-label="${config.ariaLabel}" title="${config.title}">
          <span class="material-symbols-outlined">content_copy</span>
        </button>
      `;
    },

    renderTypingIndicator() {
      return `
        <div id="typing-indicator" class="dehum-message dehum-message--assistant dehum-fade-in">
          <div class="dehum-message__bubble">
            <div class="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      `;
    },

    renderThinkingIndicator() {
      return `
        <div id="thinking-indicator" class="dehum-message dehum-message--thinking dehum-fade-in">
          <div class="dehum-message__bubble">
            🤔 Analyzing your requirements and finding the best dehumidifier options
            <span class="thinking-dots">
              <span>.</span><span>.</span><span>.</span>
            </span>
          </div>
        </div>
      `;
    },

    renderInterruptionMessage(phase) {
      const phaseText = phase === 'thinking' ? 'analyzing' : 'generating recommendations';
      return `
        <div class="dehum-message dehum-message--interruption dehum-fade-in">
          <div class="dehum-message__bubble">
            ⚠️ Analysis was interrupted while ${phaseText}.
            <br><br>
            <button class="dehum-retry-btn" onclick="ChatWidget.retryAnalysis()">
              🔄 Click to retry analysis
            </button>
          </div>
          <div class="dehum-message__timestamp">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
        </div>
      `;
    },

    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
  };

  // ===============================
  // CLIPBOARD MANAGER
  // ===============================

  const ClipboardManager = {
    /**
     * Copy content to clipboard with visual feedback
     */
    async copy(content, $button) {
      try {
        // Strip HTML formatting for clean text copy
        const textContent = this.stripHtml(content);

        // Use modern Clipboard API if available
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(textContent);
        } else {
          // Fallback for older browsers
          this.fallbackCopy(textContent);
        }

        this.showFeedback($button, 'success');
        AccessibilityManager.announce('Message copied to clipboard');

      } catch (error) {
        console.error('Failed to copy to clipboard:', error);
        this.showFeedback($button, 'error');
        AccessibilityManager.announce('Failed to copy message');
      }
    },

    fallbackCopy(text) {
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

    stripHtml(htmlContent) {
      // Create a temporary element to parse HTML
      const tempDiv = $('<div>').html(htmlContent);

      // Handle images specially - replace with alt text
      tempDiv.find('img').each(function () {
        const alt = $(this).attr('alt') || 'Image';
        $(this).replaceWith(`[Image: ${alt}]`);
      });

      // Handle image error divs
      tempDiv.find('.dehum-image-error').each(function () {
        const text = $(this).find('.dehum-image-error-text').text() || 'Image';
        $(this).replaceWith(`[Image: ${text}]`);
      });

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

    showFeedback($button, type) {
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
    }
  };

  // ===============================
  // ACCESSIBILITY MANAGER
  // ===============================

  const AccessibilityManager = {
    /**
     * Announce messages to screen readers
     */
    announce(message) {
      const announcement = $('<div>')
        .attr('aria-live', 'polite')
        .attr('aria-atomic', 'true')
        .addClass('sr-only')
        .text(message);

      $('body').append(announcement);

      // Remove after announcement is read
      setTimeout(() => {
        announcement.remove();
      }, 1000);
    },

    /**
     * Set up focus management for modal
     */
    setupModalFocus(modalSelector) {
      const $modal = $(modalSelector);
      const focusableElements = $modal.find('button, textarea, input, [tabindex]:not([tabindex="-1"])');
      const firstFocusable = focusableElements.first();
      const lastFocusable = focusableElements.last();

      // Trap focus within modal
      $modal.on('keydown', (e) => {
        if (e.key === 'Tab') {
          if (e.shiftKey) {
            if (document.activeElement === firstFocusable[0]) {
              e.preventDefault();
              lastFocusable.focus();
            }
          } else {
            if (document.activeElement === lastFocusable[0]) {
              e.preventDefault();
              firstFocusable.focus();
            }
          }
        }
      });
    }
  };

  // ===============================
  // STATE MANAGER
  // ===============================

  const StateManager = {
    storageKeys: {
      conversation: 'dehum_conversation',
      sessionId: 'dehum_session_id',
      incompleteState: 'dehum_incomplete_state'
    },

    /**
     * Save conversation to localStorage
     */
    saveConversation(conversation) {
      try {
        localStorage.setItem(this.storageKeys.conversation, JSON.stringify(conversation));
      } catch (e) {
        console.warn('Could not save conversation to localStorage');
      }
    },

    /**
     * Load conversation from localStorage
     */
    loadConversation() {
      try {
        const stored = localStorage.getItem(this.storageKeys.conversation);
        if (stored) {
          const conversation = JSON.parse(stored);
          // Migrate old conversation format if needed
          return conversation.map(msg => {
            if (!msg.hasOwnProperty('phase')) {
              msg.phase = 'complete';
              msg.isComplete = true;
            }
            if (!msg.hasOwnProperty('toolContent')) {
              msg.toolContent = null;
              msg.mainContent = msg.content;
            }
            return msg;
          });
        }
      } catch (e) {
        console.warn('Could not load conversation from localStorage');
      }
      return [];
    },

    /**
     * Save session ID to localStorage
     */
    saveSessionId(sessionId) {
      try {
        if (sessionId) {
          localStorage.setItem(this.storageKeys.sessionId, sessionId);
        } else {
          localStorage.removeItem(this.storageKeys.sessionId);
        }
      } catch (e) {
        console.warn('Could not save session ID to localStorage');
      }
    },

    /**
     * Load session ID from localStorage
     */
    loadSessionId() {
      try {
        return localStorage.getItem(this.storageKeys.sessionId);
      } catch (e) {
        console.warn('Could not load session ID from localStorage');
        return null;
      }
    },

    /**
     * Save incomplete state for interruption recovery
     */
    saveIncompleteState(phase, content, toolContent = null) {
      try {
        const state = {
          phase,
          content,
          toolContent,
          timestamp: Date.now()
        };
        localStorage.setItem(this.storageKeys.incompleteState, JSON.stringify(state));
      } catch (e) {
        console.warn('Could not save incomplete state to localStorage');
      }
    },

    /**
     * Load incomplete state
     */
    loadIncompleteState() {
      try {
        const stored = localStorage.getItem(this.storageKeys.incompleteState);
        if (stored) {
          return JSON.parse(stored);
        }
      } catch (e) {
        console.warn('Could not load incomplete state from localStorage');
      }
      return null;
    },

    /**
     * Clear incomplete state
     */
    clearIncompleteState() {
      try {
        localStorage.removeItem(this.storageKeys.incompleteState);
      } catch (e) {
        console.warn('Could not clear incomplete state from localStorage');
      }
    }
  };

  // ===============================
  // MAIN CHAT WIDGET
  // ===============================

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
    welcomeMessageShown: false, // Prevents duplicate welcome messages during initialization race conditions

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

    /**
     * Initialize the chat widget
     */
    init() {
      this.bindEvents();
      this.setupAccessibility();
      this.loadConversation();
      this.loadSessionId();
      this.initButtonEffects();
      this.updateCharCount();
      this.autoResizeInput();
      this.checkForInterruption();
      this.checkPrivacyNotice();
    },


    /**
     * Check and notify about localStorage usage for privacy compliance
     */
    checkPrivacyNotice() {
      if (!localStorage.getItem('dehum_privacy_acknowledged')) {
        console.info('Dehumidifier Assistant: This chat uses browser storage to save your conversation history locally. No data is shared with third parties.');
        try {
          localStorage.setItem('dehum_privacy_acknowledged', 'true');
        } catch (e) {
          // Silently fail if localStorage is not available
        }
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
        this.updateCharCount();
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

      // Copy button delegation
      $(document).on('click', '.dehum-copy-btn', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $button = $(e.currentTarget);
        const content = $button.closest('.dehum-message__bubble').clone();
        content.find('.dehum-copy-btn').remove(); // Remove copy button from content
        ClipboardManager.copy(content.html(), $button);
      });
    },

    /**
     * Setup accessibility features
     */
    setupAccessibility() {
      $(this.selectors.modal).attr('aria-hidden', 'true');
      AccessibilityManager.setupModalFocus(this.selectors.modal);
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

      // Only reload conversation if messages container is empty
      if ($(this.selectors.messages).children().length === 0) {
        this.welcomeMessageShown = false; // Reset flag for first open
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
      this.welcomeMessageShown = false; // Reset welcome message flag
      this.resetPhaseState();

      // Clear storage
      StateManager.saveConversation(this.conversation);
      StateManager.saveSessionId(this.currentSessionId);
      StateManager.clearIncompleteState();

      // Clear messages and show welcome message
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
      AccessibilityManager.announce(`You said: ${message}`);

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

            // For fallback API, we don't have separate tool content
            const messageElement = this.addMessage('assistant', response.response, true);

            // Update conversation with proper structure for consistency
            if (this.conversation.length > 0) {
              const lastMessage = this.conversation[this.conversation.length - 1];
              if (lastMessage.type === 'assistant') {
                lastMessage.toolContent = null;
                lastMessage.mainContent = response.response;
              }
            }

            // Store session ID from response
            if (response.session_id) {
              this.currentSessionId = response.session_id;
              StateManager.saveSessionId(this.currentSessionId);
            }

            // Save conversation when using fallback API (non-critical - don't interrupt user flow)
            try {
              await this.saveConversationToWordPress(message, response.response);
            } catch (error) {
              console.warn('Failed to save conversation via WordPress AJAX (non-critical):', error);
              // Don't interrupt user experience - conversation save is for admin logging only
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

      // Automatically restore focus to input field
      if (this.isOpen) {
        setTimeout(() => {
          $(this.selectors.input).focus();
        }, 100);
      }
    },

    /**
     * Show typing indicator
     */
    showTypingIndicator() {
      this.hideTypingIndicator(); // Remove any existing indicator
      $(this.selectors.messages).append(MessageRenderer.renderTypingIndicator());
      this.scrollToBottom();
    },

    /**
     * Hide typing indicator
     */
    hideTypingIndicator() {
      $('#typing-indicator').remove();
    },

    /**
     * Show thinking indicator with animated dots
     */
    showThinkingIndicator() {
      this.hideTypingIndicator();
      $(this.selectors.messages).append(MessageRenderer.renderThinkingIndicator());
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
        let toolContent = '';
        let isThinking = false;
        let currentMessageIndex = -1;
        let currentPhase = null;

        // Make streaming request with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000);

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
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;

                let data;
                try {
                  data = JSON.parse(jsonStr);
                } catch (parseError) {
                  console.warn('Failed to parse streaming JSON:', parseError, 'Raw data:', jsonStr);
                  continue;
                }

                if (!data || typeof data !== 'object') {
                  console.warn('Invalid data structure in stream:', data);
                  continue;
                }

                // Store session ID
                if (data.session_id) {
                  this.currentSessionId = data.session_id;
                  StateManager.saveSessionId(this.currentSessionId);
                }

                // Handle different types of responses
                if (data.is_thinking) {
                  if (!isThinking) {
                    this.showThinkingIndicator();
                    isThinking = true;
                    StateManager.saveIncompleteState('thinking', currentContent, toolContent);
                  }
                } else if (data.is_streaming_chunk) {
                  const phase = data.metadata?.phase || 'default';

                  if (phase === 'tools') {
                    if (!summaryElement) {
                      this.hideTypingIndicator();
                      summaryElement = this.addMessage('assistant', '', true);
                      currentMessageIndex = this.conversation.length - 1;
                    }
                    toolContent += (toolContent ? '\n' : '') + data.message;
                    this.updateMessage(summaryElement, toolContent);
                    currentPhase = phase;
                  } else {
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

                    if (phase === 'initial_summary') {
                      currentContent += data.message;
                      const displayContent = toolContent ? toolContent + '\n\n' + currentContent : currentContent;
                      this.updateMessage(summaryElement, displayContent);
                    } else if (phase === 'recommendations') {
                      if (isThinking) {
                        this.hideThinkingIndicator();
                        isThinking = false;
                      }
                      recsContent += data.message;
                      this.updateMessage(recsElement, recsContent);
                    }

                    // Save state
                    let saveContent;
                    if (phase === 'initial_summary') {
                      saveContent = toolContent ? toolContent + '\n\n' + currentContent : currentContent;
                      StateManager.saveIncompleteState(phase, saveContent, toolContent);
                    } else {
                      saveContent = recsContent;
                      StateManager.saveIncompleteState(phase, saveContent, toolContent);
                    }
                  }

                  setTimeout(() => this.scrollToBottom(), 0);

                } else if (data.is_final) {
                  this.hideThinkingIndicator();
                  this.streamingComplete = true;

                  if (!currentContent && !recsContent && !toolContent && data.message) {
                    currentContent = data.message;
                  }

                  if (!summaryElement) {
                    this.hideTypingIndicator();
                    summaryElement = this.addMessage('assistant', currentContent, true);
                    currentMessageIndex = this.conversation.length - 1;
                  }

                  // Combine all content for history
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

                  // Mark as complete in conversation history
                  if (currentMessageIndex >= 0 && currentMessageIndex < this.conversation.length) {
                    this.conversation[currentMessageIndex].content = finalContent;
                    this.conversation[currentMessageIndex].toolContent = toolContent || null;
                    this.conversation[currentMessageIndex].mainContent = (currentContent || '') + (recsContent ? '\n\n' + recsContent : '');
                    this.conversation[currentMessageIndex].phase = 'complete';
                    this.conversation[currentMessageIndex].isComplete = true;
                    StateManager.saveConversation(this.conversation);
                  }

                  setTimeout(() => this.scrollToBottom(), 0);
                  StateManager.clearIncompleteState();

                } else if (data.metadata?.phase === 'initial_complete' || data.metadata?.phase === 'thinking_complete') {
                  if (data.metadata.phase === 'initial_complete') {
                    if (!summaryElement) {
                      this.hideTypingIndicator();
                      summaryElement = this.addMessage('assistant', data.message, true);
                      currentContent = data.message;
                      currentMessageIndex = this.conversation.length - 1;
                    } else if (currentContent !== data.message) {
                      currentContent = data.message;
                      this.updateMessage(summaryElement, currentContent);
                    }
                  }

                  setTimeout(() => this.scrollToBottom(), 0);

                } else {
                  if (data.metadata?.char_streaming) {
                    return;
                  } else if (!summaryElement) {
                    this.hideTypingIndicator();
                    summaryElement = this.addMessage('assistant', data.message || '', true);
                    currentContent = data.message || '';
                    currentMessageIndex = this.conversation.length - 1;

                    if (currentMessageIndex >= 0) {
                      this.conversation[currentMessageIndex].phase = 'initial';
                      this.conversation[currentMessageIndex].isComplete = false;
                      StateManager.saveConversation(this.conversation);
                    }
                  }

                  setTimeout(() => this.scrollToBottom(), 0);
                }
              } catch (e) {
                console.error('Error processing streaming chunk:', e, 'Line:', line);
              }
            }
          }
        }

        // Save complete conversation to WordPress
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

      const requestData = {
        action: 'dehum_mvp_chat',
        message: message,
        nonce: dehumMVP.nonce
      };

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
     * Add a message to the chat
     */
    addMessage(type, content, returnElement = false) {
      const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      // Save to conversation history if not an error
      if (type !== 'error') {
        const message = {
          type,
          content,
          timestamp,
          phase: content ? 'complete' : 'placeholder', // Mark empty messages as placeholders
          isComplete: !!content, // Only complete if there is content
          toolContent: null,
          mainContent: content
        };
        this.conversation.push(message);
        StateManager.saveConversation(this.conversation);
      }

      const $message = MessageRenderer.render(type, content, { timestamp });
      $(this.selectors.messages).append($message);

      this.scrollToBottom();

      // Announce assistant messages to screen readers
      if (type === 'assistant' && content) {
        this.debounce(() => {
          AccessibilityManager.announce(`Assistant responded: ${content.substring(0, 100)}${content.length > 100 ? '...' : ''}`);
        }, 500, 'announce');
      }

      return returnElement ? $message : undefined;
    },

    /**
     * Add a system message (for notifications)
     */
    addSystemMessage(content) {
      const messageHtml = `
        <div class="dehum-message dehum-message--system dehum-fade-in">
          <div class="dehum-message__bubble">
            <em>${MessageRenderer.escapeHtml(content)}</em>
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
     * Show persistent welcome message styled as assistant message
     * Always displayed at the top of every chat session
     */
    async showWelcomeMessage() {
      // Skip if welcome message already shown and messages container has content
      if (this.welcomeMessageShown && $(this.selectors.messages).children().length > 0) {
        return;
      }

      // Remove any existing welcome message to avoid duplicates
      $(this.selectors.messages).find('.dehum-welcome-message').remove();

      try {
        const response = await $.ajax({
          url: dehumMVP.ajaxUrl,
          type: 'POST',
          data: {
            action: 'dehum_get_welcome_message',
            nonce: dehumMVP.nonce
          }
        });

        const welcomeContent = response.success && response.data.message
          ? response.data.message
          : this.getFallbackWelcomeContent();

        this.renderWelcomeMessage(welcomeContent);
        this.welcomeMessageShown = true; // Mark as shown
      } catch (error) {
        console.error('Failed to load welcome message:', error);
        this.renderWelcomeMessage(this.getFallbackWelcomeContent());
        this.welcomeMessageShown = true; // Mark as shown even for fallback
      }
    },

    /**
     * Get fallback welcome content
     */
    getFallbackWelcomeContent() {
      return "**Dehumidifier Assistant**\n" +
        "- **Sizing:** Room dimensions + humidity\n" +
        "- **Technical:** Installation, troubleshooting\n" +
        "- **Products:** Specs, comparisons, pricing\n" +
        "Pool room or regular space?";
    },

    /**
     * Render welcome message as regular assistant message
     */
    renderWelcomeMessage(content) {
      const welcomeMessage = MessageRenderer.render('assistant', content, {
        timestamp: '',
        enableCopyButton: false
      });

      // Add special class for identification and styling
      welcomeMessage.addClass('dehum-welcome-message');
      welcomeMessage.find('.dehum-message__timestamp').hide();

      // Always insert at the top
      $(this.selectors.messages).prepend(welcomeMessage);
    },

    /**
     * Render a message from history
     */
    renderMessage(message) {
      if (message.type === 'assistant' && message.toolContent && message.mainContent) {
        // Render tool content first
        const $toolMessage = MessageRenderer.render('assistant', message.toolContent, {
          timestamp: message.timestamp,
          enableCopyButton: false
        });
        $(this.selectors.messages).append($toolMessage);

        // Then render main content with copy button
        const $mainMessage = MessageRenderer.render('assistant', message.mainContent, {
          timestamp: message.timestamp
        });
        $(this.selectors.messages).append($mainMessage);
      } else {
        // Render as single message
        const $message = MessageRenderer.render(message.type, message.content, {
          timestamp: message.timestamp
        });
        $(this.selectors.messages).append($message);
      }
    },

    /**
     * Load conversation from localStorage
     */
    loadConversation() {
      this.conversation = StateManager.loadConversation();

      $(this.selectors.messages).empty();

      // Show welcome message only if not already shown or if no conversation history
      const completeMessages = this.conversation.filter(msg => msg.isComplete && msg.phase === 'complete');
      if (!this.welcomeMessageShown || completeMessages.length === 0) {
        this.showWelcomeMessage();
      }

      // Then load any existing conversation history
      if (completeMessages.length > 0) {
        completeMessages.forEach(message => this.renderMessage(message));
      }

      this.scrollToBottom();
    },

    /**
     * Load session ID from storage
     */
    loadSessionId() {
      this.currentSessionId = StateManager.loadSessionId();
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
     * Update character counter
     */
    updateCharCount() {
      const current = $(this.selectors.input).val().length;
      const counterEl = $('#dehum-char-count');
      if (counterEl.length) {
        counterEl.text(`${current}/${this.maxLen}`);
        counterEl.toggleClass('exceeded', current > this.maxLen);
      }
    },

    /**
     * Auto-resize textarea
     */
    autoResizeInput() {
      const textarea = $(this.selectors.input)[0];
      if (!textarea) return;

      textarea.style.height = 'auto';

      const container = $('.dehum-chat-container')[0];
      const maxPx = container ? container.clientHeight * 0.25 : 120;

      const newHeight = Math.min(textarea.scrollHeight, maxPx);
      textarea.style.height = newHeight + 'px';

      textarea.style.overflowY = textarea.scrollHeight > maxPx ? 'auto' : 'hidden';
    },

    /**
     * Update an existing message element
     */
    updateMessage(messageElement, newContent) {
      const contentDiv = messageElement.find('.dehum-message__bubble');
      if (contentDiv.length) {
        const isAssistantMessage = messageElement.hasClass('dehum-message--assistant');
        const copyButton = isAssistantMessage && newContent.trim()
          ? MessageRenderer.renderCopyButton()
          : '';

        contentDiv.html(MarkdownRenderer.parse(newContent) + copyButton);

        // Rebind image handlers for new content
        if (isAssistantMessage) {
          MessageRenderer.bindImageHandlers(messageElement);
        }
      }
      setTimeout(() => this.scrollToBottom(), 0);
    },

    /**
     * Check for interrupted analysis
     */
    checkForInterruption() {
      const incompleteState = StateManager.loadIncompleteState();

      if (incompleteState) {
        // Check if the interruption was recent (within last hour)
        const hourAgo = Date.now() - (60 * 60 * 1000);
        if (incompleteState.timestamp > hourAgo) {
          this.showInterruptionMessage(incompleteState.phase);
        } else {
          // Clear old incomplete state
          StateManager.clearIncompleteState();
        }
      }
    },

    /**
     * Show interruption message with retry button
     */
    showInterruptionMessage(phase) {
      const interruptionHtml = MessageRenderer.renderInterruptionMessage(phase);
      $(this.selectors.messages).append(interruptionHtml);
      this.scrollToBottom();
    },

    /**
     * Retry analysis after interruption
     */
    retryAnalysis() {
      $('.dehum-message--interruption').remove();
      StateManager.clearIncompleteState();

      const lastUserMessage = this.conversation
        .filter(msg => msg.type === 'user')
        .pop();

      if (lastUserMessage) {
        this.conversation = this.conversation.filter(msg => msg.type !== 'assistant' || msg.isComplete);
        this.resetPhaseState();
        StateManager.saveConversation(this.conversation);

        this.lockInterface();
        this.showTypingIndicator();

        this.callStreamingAPI(lastUserMessage.content)
          .catch(error => {
            console.log('Streaming failed on retry, falling back to regular API:', error);
            return this.callAPI(lastUserMessage.content);
          })
          .then(response => {
            if (response && !this.streamingComplete) {
              this.hideTypingIndicator();

              const messageElement = this.addMessage('assistant', response.response, true);

              if (this.conversation.length > 0) {
                const lastMessage = this.conversation[this.conversation.length - 1];
                if (lastMessage.type === 'assistant') {
                  lastMessage.toolContent = null;
                  lastMessage.mainContent = response.response;
                }
              }

              if (response.session_id) {
                this.currentSessionId = response.session_id;
                StateManager.saveSessionId(this.currentSessionId);
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
    async saveConversationToWordPress(userMessage, assistantResponse, retryCount = 0) {
      const maxRetries = 2;

      try {
        const response = await $.ajax({
          url: dehumMVP.ajaxUrl,
          type: 'POST',
          data: {
            action: 'dehum_mvp_save_conversation',
            message: userMessage,
            response: assistantResponse,
            session_id: this.currentSessionId,
            nonce: dehumMVP.saveNonce || dehumMVP.nonce // Use separate save nonce
          }
        });

        if (response.success) {
          console.log('Conversation saved to WordPress successfully');
        } else {
          console.error('WordPress rejected conversation save:', response.data?.message || 'Unknown error');

          // Log detailed error for debugging
          this.logSaveError('WordPress rejection', {
            userMessage: userMessage.substring(0, 100) + '...',
            responseLength: assistantResponse.length,
            sessionId: this.currentSessionId,
            errorMessage: response.data?.message
          });
        }
      } catch (error) {
        console.error('Failed to save conversation to WordPress:', error);

        // Log detailed error for debugging
        this.logSaveError('AJAX failure', {
          userMessage: userMessage.substring(0, 100) + '...',
          responseLength: assistantResponse.length,
          sessionId: this.currentSessionId,
          status: error.status,
          statusText: error.statusText,
          retryCount: retryCount
        });

        // Handle specific error types
        if (error.status === 403) {
          console.error('403 Error - Possible causes:');
          console.error('1. Chat may be restricted to logged-in users only');
          console.error('2. Nonce verification failed');
          console.error('3. User does not have required permissions');
        } else if (error.status === 429) {
          console.error('429 Error - Rate limited');
        } else if (error.status === 0 || error.status === 502 || error.status === 503) {
          // Network/server errors - retry if possible
          if (retryCount < maxRetries) {
            console.log(`Retrying save request (attempt ${retryCount + 1}/${maxRetries + 1})...`);

            // Wait before retry with exponential backoff
            await new Promise(resolve => setTimeout(resolve, Math.pow(2, retryCount) * 1000));

            return this.saveConversationToWordPress(userMessage, assistantResponse, retryCount + 1);
          }
        }

        throw error;
      }
    },

    /**
     * Log save errors for debugging purposes
     */
    logSaveError(errorType, details) {
      const errorData = {
        timestamp: new Date().toISOString(),
        type: errorType,
        userAgent: navigator.userAgent,
        url: window.location.href,
        ...details
      };

      console.error('Conversation Save Error Details:', errorData);

      // Store in sessionStorage for admin debugging (if available)
      try {
        const existingErrors = JSON.parse(sessionStorage.getItem('dehum_save_errors') || '[]');
        existingErrors.push(errorData);

        // Keep only last 10 errors
        if (existingErrors.length > 10) {
          existingErrors.splice(0, existingErrors.length - 10);
        }

        sessionStorage.setItem('dehum_save_errors', JSON.stringify(existingErrors));
      } catch (e) {
        // Ignore storage errors
      }
    },

    /**
     * Generate a cryptographically secure session ID
     */
    generateSessionId() {
      if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
      }

      const timestamp = Date.now().toString(36);
      const randomPart = Math.random().toString(36).substr(2, 9);
      const extraRandom = Math.random().toString(36).substr(2, 9);
      return `${timestamp}_${randomPart}_${extraRandom}`;
    }
  };

  // Make ChatWidget globally accessible for retry functionality
  window.ChatWidget = ChatWidget;

  // Initialize when DOM is ready
  $(document).ready(() => {
    ChatWidget.init();
  });

})(jQuery);