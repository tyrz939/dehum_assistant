jQuery(document).ready(function ($) {
  'use strict';

  // Chat widget functionality
  const ChatWidget = {
    isOpen: false,
    conversationHistory: [],
    sessionId: null,  // Step 5.2: Track session ID for conversation threading

    init: function () {
      this.bindEvents();
      this.loadConversationHistory();
      this.updateCharCounter();
      this.initSession();  // Step 5.2: Initialize session management
    },

    bindEvents: function () {
      // Open chat when button is clicked
      $('#dehum-mvp-chat-button').on('click', this.openChat.bind(this));

      // Close chat when X is clicked
      $('#dehum-mvp-close-chat').on('click', this.closeChat.bind(this));

      // Clear chat when clear button is clicked
      $('#dehum-mvp-clear-chat').on('click', this.clearChatWithConfirmation.bind(this));

      // Send message when Send button is clicked
      $('#dehum-mvp-send-button').on('click', this.sendMessage.bind(this));

      // Send message when Enter is pressed (Shift+Enter for new line)
      $('#dehum-mvp-chat-input').on('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          ChatWidget.sendMessage();
        }
      });

      // Update character counter
      $('#dehum-mvp-chat-input').on('input', this.updateCharCounter.bind(this));

      // Close chat when clicking outside (optional)
      $(document).on('click', function (e) {
        if (ChatWidget.isOpen &&
          !$(e.target).closest('#dehum-mvp-chat-modal, #dehum-mvp-chat-button').length) {
          // Uncomment to enable click-outside-to-close
          // ChatWidget.closeChat();
        }
      });
    },

    openChat: function () {
      $('#dehum-mvp-chat-modal').fadeIn(300);
      $('#dehum-mvp-chat-button').hide();
      this.isOpen = true;

      // Focus on input
      setTimeout(() => {
        $('#dehum-mvp-chat-input').focus();
      }, 350);

      // Scroll to bottom
      this.scrollToBottom();
    },

    closeChat: function () {
      $('#dehum-mvp-chat-modal').fadeOut(300);
      $('#dehum-mvp-chat-button').show();
      this.isOpen = false;
    },

    sendMessage: function () {
      const input = $('#dehum-mvp-chat-input');
      const message = input.val().trim();

      // Step 3.2: Enhanced validation
      const validation = this.validateInput(message);
      if (!validation.isValid) {
        validation.errors.forEach(error => {
          this.showError(error);
        });
        return;
      }

      // Clear input and disable send button
      input.val('');
      this.updateCharCounter();
      this.setInputState(false);

      // Add user message to chat
      this.addMessage(message, 'user');

      // Show typing indicator
      this.showTypingIndicator();

      // Send to WordPress AJAX
      this.sendToWordPress(message);
    },

    sendToWordPress: function (message) {
      // Step 5.2: Prepare AJAX data with session ID
      const ajaxData = {
        action: 'dehum_mvp_chat',
        message: message,
        nonce: dehumMVP.nonce
      };

      // Include session ID if we have one
      if (this.sessionId) {
        ajaxData.session_id = this.sessionId;
        console.log('Dehum MVP: Sending message with existing session ID:', this.sessionId);
      } else {
        console.log('Dehum MVP: Sending message without session ID (will generate new)');
      }

      // Debug: Log the actual data being sent
      console.log('Dehum MVP: AJAX data being sent:', ajaxData);

      $.ajax({
        url: dehumMVP.ajaxUrl,
        type: 'POST',
        data: ajaxData,
        success: function (response) {
          ChatWidget.hideTypingIndicator();

          if (response.success) {
            // Step 5.2: Store session ID from server response
            if (response.data.session_id) {
              if (!ChatWidget.sessionId) {
                console.log('Dehum MVP: Received new session ID from server:', response.data.session_id);
                ChatWidget.sessionId = response.data.session_id;
                ChatWidget.saveSessionId();
              } else if (ChatWidget.sessionId !== response.data.session_id) {
                console.log('Dehum MVP: Session ID mismatch! Local:', ChatWidget.sessionId, 'Server:', response.data.session_id);
                ChatWidget.sessionId = response.data.session_id;
                ChatWidget.saveSessionId();
              } else {
                console.log('Dehum MVP: Confirmed session ID continues:', ChatWidget.sessionId);
              }
            }

            ChatWidget.addMessage(response.data.response, 'assistant');
            ChatWidget.saveConversationHistory();
          } else {
            // Show error and restore message to input for retry
            ChatWidget.showError(response.data.message || 'Something went wrong. Please try again.');

            // Restore original message to input if available
            if (response.data.original_message) {
              ChatWidget.restoreMessageToInput(response.data.original_message);
            }
          }

          ChatWidget.setInputState(true);
        },
        error: function (xhr, status, error) {
          ChatWidget.hideTypingIndicator();

          // Step 4.2: Handle rate limiting errors specially
          if (xhr.status === 429) {
            try {
              const errorData = JSON.parse(xhr.responseText);
              if (errorData.data && errorData.data.rate_limited) {
                ChatWidget.showError(errorData.data.message, false); // Don't auto-dismiss rate limit messages
                ChatWidget.setInputState(true);
                return; // Don't restore message for rate limits
              }
            } catch (e) {
              // Fall through to generic error handling
            }
          }

          ChatWidget.showError('Connection failed. Please check your internet and try again.');

          // Restore message to input for network errors too
          ChatWidget.restoreMessageToInput(message);
          ChatWidget.setInputState(true);

          console.error('AJAX Error:', { xhr, status, error });
        }
      });
    },

    // Create message HTML structure
    createMessageElement: function (message, type, timestamp, animate = false) {
      const messageClass = type === 'user' ? 'user-message' : 'assistant-message';
      const timeString = new Date(timestamp).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit'
      });

      const style = animate ? 'style="opacity: 0; transform: translateY(10px);"' : '';

      return `
        <div class="${messageClass}" ${style}>
          <div class="message-content">${this.formatMessage(message)}</div>
          <div class="message-time">${timeString}</div>
        </div>
      `;
    },

    addMessage: function (message, type) {
      const messagesContainer = $('#dehum-mvp-chat-messages');
      const timestamp = new Date().toISOString();

      // Create message with animation
      const messageHtml = this.createMessageElement(message, type, timestamp, true);
      const $newMessage = $(messageHtml);
      messagesContainer.append($newMessage);

      // Animate message in
      $newMessage.animate({
        opacity: 1,
        transform: 'translateY(0px)'
      }, 300);

      // Save to conversation history
      this.conversationHistory.push({
        message: message,
        type: type,
        timestamp: timestamp
      });

      this.scrollToBottom();
    },

    showTypingIndicator: function () {
      const messagesContainer = $('#dehum-mvp-chat-messages');
      const typingHtml = `
        <div class="typing-indicator" id="typing-indicator" style="opacity: 0;">
          <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="typing-text">${dehumMVP.strings.typing}</span>
        </div>
      `;

      const $typing = $(typingHtml);
      messagesContainer.append($typing);

      // Fade in typing indicator
      $typing.animate({ opacity: 1 }, 200);

      this.scrollToBottom();
    },

    hideTypingIndicator: function () {
      const $typing = $('#typing-indicator');
      if ($typing.length) {
        $typing.animate({ opacity: 0 }, 200, function () {
          $(this).remove();
        });
      }
    },

    setInputState: function (enabled) {
      const input = $('#dehum-mvp-chat-input');
      const button = $('#dehum-mvp-send-button');

      if (enabled) {
        input.prop('disabled', false);
        button.prop('disabled', false).text(dehumMVP.strings.sendButton);
        input.focus();
      } else {
        input.prop('disabled', true);
        button.prop('disabled', true).text('Sending...');
      }
    },

    updateCharCounter: function () {
      const input = $('#dehum-mvp-chat-input');
      const counter = $('#char-count');
      const length = input.val().length;

      counter.text(length);

      // Change color if approaching limit
      if (length > 350) {
        counter.css('color', '#f44336');
      } else if (length > 300) {
        counter.css('color', '#ff9800');
      } else {
        counter.css('color', '#666');
      }
    },

    scrollToBottom: function () {
      const messagesContainer = $('#dehum-mvp-chat-messages');
      messagesContainer.scrollTop(messagesContainer[0].scrollHeight);
    },

    saveConversationHistory: function () {
      localStorage.setItem('dehum_mvp_conversation', JSON.stringify(this.conversationHistory));
    },

    loadConversationHistory: function () {
      const saved = localStorage.getItem('dehum_mvp_conversation');
      if (saved) {
        try {
          this.conversationHistory = JSON.parse(saved);
          this.displayConversationHistory();
        } catch (e) {
          console.warn('Failed to load conversation history:', e);
          this.conversationHistory = [];
        }
      }
    },

    displayConversationHistory: function () {
      const messagesContainer = $('#dehum-mvp-chat-messages');

      // Clear existing messages except welcome message
      messagesContainer.find('.user-message, .assistant-message').not(':first').remove();

      // Display saved messages using the same structure as new messages
      this.conversationHistory.forEach(item => {
        if (item.type === 'user' || item.type === 'assistant') {
          const messageHtml = this.createMessageElement(item.message, item.type, item.timestamp, false);
          messagesContainer.append(messageHtml);
        }
      });

      this.scrollToBottom();
    },

    clearHistory: function () {
      this.conversationHistory = [];
      localStorage.removeItem('dehum_mvp_conversation');

      // Step 5.2: Clear session when clearing history 
      console.log('Dehum MVP: Clearing session history and starting new session');
      this.sessionId = null;
      localStorage.removeItem('dehum_mvp_session_id');

      // Clear messages except welcome message
      const messagesContainer = $('#dehum-mvp-chat-messages');
      messagesContainer.find('.user-message, .assistant-message').not(':first').remove();

      // Clear any typing indicators or errors
      messagesContainer.find('.typing-indicator, .error-message').remove();

      // Reset input
      $('#dehum-mvp-chat-input').val('');
      this.updateCharCounter();

      // Scroll to top to show welcome message
      this.scrollToBottom();
    },

    clearChatWithConfirmation: function () {
      // Only ask for confirmation if there's actually conversation history
      if (this.conversationHistory.length > 0) {
        if (confirm('Start a new conversation? This will clear your current chat history.')) {
          this.clearHistory();
        }
      } else {
        // No history, no need to show any message - just keep the welcome message
        console.log('Chat already clear - no action needed');
      }
    },

    // Step 5.2: Session management functions
    initSession: function () {
      this.loadSessionId();
    },

    saveSessionId: function () {
      if (this.sessionId) {
        localStorage.setItem('dehum_mvp_session_id', this.sessionId);
        console.log('Dehum MVP: Saved session ID to localStorage:', this.sessionId);
      } else {
        console.log('Dehum MVP: Cannot save session ID - sessionId is null');
      }
    },

    loadSessionId: function () {
      const saved = localStorage.getItem('dehum_mvp_session_id');
      if (saved) {
        this.sessionId = saved;
        console.log('Dehum MVP: Loaded existing session ID:', this.sessionId);
      } else {
        console.log('Dehum MVP: No existing session ID found in localStorage');
      }
    },

    restoreMessageToInput: function (message) {
      const input = $('#dehum-mvp-chat-input');
      input.val(message);
      this.updateCharCounter();

      // Focus on input and show user the message is restored
      setTimeout(() => {
        input.focus();
        input[0].setSelectionRange(message.length, message.length); // Cursor at end
      }, 100);
    },

    formatMessage: function (message) {
      // Enhanced message formatting for better readability
      let formatted = this.escapeHtml(message);

      // Add line breaks for better paragraph spacing
      formatted = formatted.replace(/\n\n/g, '</p><p>');
      formatted = formatted.replace(/\n/g, '<br>');

      // Wrap in paragraph if it contains breaks
      if (formatted.includes('<br>') || formatted.includes('</p>')) {
        formatted = '<p>' + formatted + '</p>';
      }

      return formatted;
    },

    escapeHtml: function (text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    },

    // Step 3.2: Enhanced error handling with auto-dismiss
    showError: function (errorMessage, autoDismiss = true) {
      const messagesContainer = $('#dehum-mvp-chat-messages');
      const errorId = 'error-' + Date.now();

      const errorHtml = `
        <div class="error-message" id="${errorId}" style="opacity: 0;">
          <div class="error-content">
            <span class="error-icon">⚠️</span>
            <span class="error-text">${this.escapeHtml(errorMessage)}</span>
          </div>
        </div>
      `;

      const $error = $(errorHtml);
      messagesContainer.append($error);

      // Animate error in
      $error.animate({ opacity: 1 }, 200);

      // Auto-dismiss after 5 seconds if enabled
      if (autoDismiss) {
        setTimeout(() => {
          $error.animate({ opacity: 0 }, 300, function () {
            $(this).remove();
          });
        }, 5000);
      }

      this.scrollToBottom();
    },

    // Step 3.2: Real-time validation feedback
    validateInput: function (message) {
      const validation = {
        isValid: true,
        errors: []
      };

      if (!message || message.trim().length === 0) {
        validation.isValid = false;
        validation.errors.push('Please enter a message');
      }

      if (message.length > 400) {
        validation.isValid = false;
        validation.errors.push('Message too long (400 character limit)');
      }

      // Check for common non-dehumidifier topics (basic filtering)
      const offTopicKeywords = ['weather', 'politics', 'sports', 'cooking', 'travel'];
      const lowerMessage = message.toLowerCase();
      const hasOffTopicKeywords = offTopicKeywords.some(keyword =>
        lowerMessage.includes(keyword) && !lowerMessage.includes('humid')
      );

      if (hasOffTopicKeywords) {
        validation.isValid = false;
        validation.errors.push('I can only help with dehumidifier and humidity questions');
      }

      return validation;
    },

    // Debug function to check session status
    debugSessionStatus: function () {
      console.log('=== Dehum MVP Session Debug ===');
      console.log('Current sessionId:', this.sessionId);
      console.log('localStorage sessionId:', localStorage.getItem('dehum_mvp_session_id'));
      console.log('Conversation history length:', this.conversationHistory.length);
      console.log('Chat widget open:', this.isOpen);
      console.log('===============================');
    },

    // Test function to simulate session behavior
    testSessionFlow: function () {
      console.log('=== Testing Session Flow ===');

      // Test 1: Check initial state
      this.debugSessionStatus();

      // Test 2: Send a test message
      console.log('Sending test message...');
      this.addMessage('Test message for session debugging', 'user');

      // Test 3: Check localStorage
      setTimeout(() => {
        console.log('After 1 second:');
        this.debugSessionStatus();
      }, 1000);
    },

    // Function to force a new session (for testing)
    forceNewSession: function () {
      console.log('Forcing new session...');
      this.sessionId = null;
      localStorage.removeItem('dehum_mvp_session_id');
      this.debugSessionStatus();
    }
  };

  // Initialize chat widget
  ChatWidget.init();

  // Make ChatWidget available globally for debugging
  window.DehumChatWidget = ChatWidget;

  // Console message for developers
  console.log('Dehumidifier Assistant MVP loaded successfully!');
  console.log('Debug functions available:');
  console.log('- DehumChatWidget.debugSessionStatus()');
  console.log('- DehumChatWidget.testSessionFlow()');
  console.log('- DehumChatWidget.forceNewSession()');

  // Show initial session status
  setTimeout(function () {
    ChatWidget.debugSessionStatus();
  }, 1000);
}); 