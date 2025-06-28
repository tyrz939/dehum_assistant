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
          displayMessages(container, response.data);
        } else {
          container.html('<div class="loading-state" style="color: #d63638;">Failed to load conversation</div>');
        }
      },
      error: function () {
        container.html('<div class="loading-state" style="color: #d63638;">Error loading conversation</div>');
      }
    });
  }

  function displayMessages(container, messages) {
    let html = '<div class="chat-messages">';

    $.each(messages, function (index, msg) {
      html += '<div class="chat-message">';

      // User message
      html += '<div class="message-user">';
      html += '<div class="message-header">User • ' + msg.timestamp + '</div>';
      html += '<div class="message-text">' + $('<div>').text(msg.message).html() + '</div>';
      html += '</div>';

      // Assistant response
      html += '<div class="message-assistant">';
      html += '<div class="message-header">Assistant</div>';
      html += '<div class="message-text">' + $('<div>').text(msg.response).html() + '</div>';
      html += '</div>';

      html += '</div>';
    });

    html += '</div>';
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