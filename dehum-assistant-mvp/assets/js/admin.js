jQuery(document).ready(function ($) {
  // Event delegation for conversation card clicks
  $(document).on('click', '.card-header', function () {
    const sessionId = $(this).closest('.conversation-card').data('session');
    toggleConversation(sessionId);
  });

  function toggleConversation(sessionId) {
    const content = $('#content-' + sessionId);
    const icon = $('[data-session="' + sessionId + '"] .expand-icon');

    if (content.is(':hidden')) {
      // Expand
      content.slideDown(200);
      icon.addClass('expanded');

      // Load conversation if not already loaded
      if (content.find('.loading-state').length > 0) {
        loadConversation(sessionId);
      }
    } else {
      // Collapse
      content.slideUp(200);
      icon.removeClass('expanded');
    }
  }

  function loadConversation(sessionId) {
    const container = $('#content-' + sessionId);

    $.ajax({
      url: ajaxurl,
      type: 'POST',
      data: {
        action: 'dehum_mvp_get_session_details',
        session_id: sessionId,
        nonce: dehum_admin_vars.nonce
      },
      success: function (response) {
        if (response.success && response.data.length > 0) {
          displayConversationFlow(container, response.data);
        } else {
          container.html('<div class="loading-state" style="color: #d63638;">Failed to load conversation</div>');
        }
      },
      error: function () {
        container.html('<div class="loading-state" style="color: #d63638;">Error loading conversation</div>');
      }
    });
  }

  function displayConversationFlow(container, messages) {
    let html = '<div class="conversation-thread">';

    // Conversation header with summary info
    html += '<div class="conversation-thread-header">';
    html += '<div class="thread-info">';
    html += '<strong>Conversation Thread</strong> • ' + messages.length + ' exchange' + (messages.length !== 1 ? 's' : '');
    html += '</div>';
    html += '<div class="thread-meta">';
    html += '<span class="session-duration">Started ' + messages[0].timestamp;
    if (messages.length > 1) {
      html += ' • Ended ' + messages[messages.length - 1].timestamp;
    }
    html += '</span>';
    html += '</div>';
    html += '</div>';

    // Natural conversation flow
    html += '<div class="conversation-messages">';

    $.each(messages, function (index, msg) {
      // User message
      html += '<div class="chat-bubble user-bubble">';
      html += '<div class="bubble-avatar">👤</div>';
      html += '<div class="bubble-content">';
      html += '<div class="bubble-text">' + $('<div>').text(msg.message).html() + '</div>';
      html += '<div class="bubble-time">' + msg.timestamp + '</div>';
      html += '</div>';
      html += '</div>';

      // AI response
      html += '<div class="chat-bubble ai-bubble">';
      html += '<div class="bubble-avatar">🤖</div>';
      html += '<div class="bubble-content">';
      html += '<div class="bubble-text">' + $('<div>').text(msg.response).html() + '</div>';
      html += '<div class="bubble-time">' + msg.timestamp + '</div>';
      html += '</div>';
      html += '</div>';
    });

    html += '</div>'; // Close conversation-messages

    // Conversation footer with session info
    html += '<div class="conversation-thread-footer">';
    html += '<div class="session-info">';
    html += '<span><strong>Session ID:</strong> <code>' + messages[0].id + '</code></span>';
    html += '<span><strong>User IP:</strong> <code>' + messages[0].user_ip + '</code></span>';
    html += '<span><strong>Total Messages:</strong> ' + (messages.length * 2) + ' (' + messages.length + ' exchanges)</span>';
    html += '</div>';
    html += '</div>';

    html += '</div>'; // Close conversation-thread
    container.html(html);
  }

  // Handle custom date range toggle
  window.toggleCustomDates = function (value) {
    const customDates = document.getElementById('custom-dates');
    if (customDates) {
      customDates.style.display = value === 'custom' ? 'block' : 'none';
    }
  };
}); 