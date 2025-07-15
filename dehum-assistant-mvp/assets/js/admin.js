jQuery(document).ready(function ($) {
  // Event delegation for conversation card clicks (excluding interactive elements)
  $(document).on('click', '.card-header', function (e) {
    // Don't toggle if clicking on checkbox, delete button, or other interactive elements
    if ($(e.target).closest('.conversation-checkbox, .delete-session-btn, .conversation-actions').length > 0) {
      return;
    }

    const sessionId = $(this).closest('.conversation-card').data('session');
    toggleConversation(sessionId);
  });

  // Individual session delete
  $(document).on('click', '.delete-session-btn', function (e) {
    e.stopPropagation();
    const sessionId = $(this).data('session');
    const conversationCard = $(this).closest('.conversation-card');

    if (confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
      deleteSession(sessionId, conversationCard);
    }
  });

  // Checkbox change handlers for bulk actions
  $(document).on('change', '.session-checkbox', function () {
    updateBulkActionState();
  });

  // Bulk action form handler
  $('#bulk-action-selector').on('change', function () {
    updateBulkActionState();
  });

  // Select all/none functionality
  window.selectAllConversations = function (selectAll) {
    $('.session-checkbox').prop('checked', selectAll);
    updateBulkActionState();
  };

  // Bulk delete confirmation
  window.confirmBulkDelete = function () {
    const selectedCount = $('.session-checkbox:checked').length;
    if (selectedCount === 0) {
      alert('Please select conversations to delete.');
      return false;
    }
    return confirm(`Are you sure you want to delete ${selectedCount} selected conversation(s)? This action cannot be undone.`);
  };

  // Toggle custom date range visibility
  window.toggleCustomDates = function (value) {
    const customDates = document.getElementById('custom-dates');
    if (customDates) {
      customDates.style.display = value === 'custom' ? 'block' : 'none';
    }
  };

  // Toggle advanced delete options
  window.toggleAdvancedDelete = function () {
    const advancedDelete = $('#advanced-delete');
    const isVisible = advancedDelete.is(':visible');

    if (isVisible) {
      advancedDelete.slideUp(200);
    } else {
      advancedDelete.slideDown(200);
    }
  };

  // Update bulk action button state
  function updateBulkActionState() {
    const selectedCount = $('.session-checkbox:checked').length;
    // Keep master checkbox state in sync
    $('#master-select-all').prop('checked', selectedCount > 0 && selectedCount === $('.session-checkbox').length);
    const bulkAction = $('#bulk-action-selector').val();
    const applyBtn = $('#bulk-apply-btn');

    if (selectedCount > 0 && bulkAction === 'delete') {
      applyBtn.prop('disabled', false).text(`Delete Selected (${selectedCount})`);

      // Collect selected session IDs and add them to the form
      const selectedSessions = $('.session-checkbox:checked').map(function () {
        return this.value;
      }).get();

      // Remove existing hidden inputs
      $('input[name="selected_sessions[]"]').not('.session-checkbox').remove();

      // Add hidden inputs for selected sessions
      selectedSessions.forEach(function (sessionId) {
        $('#bulk-delete-form').append(`<input type="hidden" name="selected_sessions[]" value="${sessionId}">`);
      });
    } else {
      applyBtn.prop('disabled', true).text('Apply');
      $('input[name="selected_sessions[]"]').not('.session-checkbox').remove();
    }
  }

  // Intercept bulk delete form submission for AJAX-based deletion
  $(document).on('submit', '#bulk-delete-form', function (e) {
    const bulkAction = $('#bulk-action-selector').val();
    if (bulkAction !== 'delete') {
      return; // allow other actions / default submit
    }
    e.preventDefault(); // prevent full page reload

    const confirmProceed = confirmBulkDelete();
    if (!confirmProceed) return;

    const selectedSessions = $('.session-checkbox:checked').map(function () {
      return this.value;
    }).get();

    if (selectedSessions.length === 0) {
      return;
    }

    const bulkNonce = $('#bulk-delete-form').find('input[name="bulk_nonce"]').val();

    // Disable Apply button while processing
    const applyBtn = $('#bulk-apply-btn');
    applyBtn.prop('disabled', true).text('Deleting…');

    $.ajax({
      url: ajaxurl,
      type: 'POST',
      data: {
        action: 'dehum_mvp_bulk_delete_sessions',
        session_ids: selectedSessions,
        nonce: bulkNonce
      },
      success: function (response) {
        if (response.success) {
          // Remove deleted cards from DOM
          response.data.session_ids.forEach(function (id) {
            $('[data-session="' + id + '"]').fadeOut(300, function () {
              $(this).remove();
              updateResultsCount();
            });
          });
          showAdminNotice('success', response.data.message);
        } else {
          showAdminNotice('error', response.data.message || 'Bulk deletion failed.');
        }
        // Reset bulk UI
        selectAllConversations(false);
        applyBtn.prop('disabled', true).text('Apply');
      },
      error: function () {
        showAdminNotice('error', 'Error occurred during bulk deletion.');
        applyBtn.prop('disabled', false).text('Apply');
      }
    });
  });

  // Intercept quick-delete and advanced delete forms (delete_old, delete_by_date, delete_by_ip)
  $(document).on('submit', '.quick-delete-actions form, #advanced-delete form', function (e) {
    e.preventDefault();

    const $form = $(this);
    const bulkAction = $form.find('input[name="bulk_action"]').val();
    const bulkNonce = $form.find('input[name="bulk_nonce"]').val();

    if (!bulkAction) return;
    if (!confirm('Are you sure? This action cannot be undone.')) return;

    let ajaxData = {
      nonce: bulkNonce
    };

    switch (bulkAction) {
      case 'delete_old':
        ajaxData.action = 'dehum_mvp_delete_old_conversations';
        break;
      case 'delete_by_date':
        ajaxData.action = 'dehum_mvp_delete_by_date';
        ajaxData.start_date = $form.find('input[name="delete_start_date"]').val();
        ajaxData.end_date = $form.find('input[name="delete_end_date"]').val();
        break;
      case 'delete_by_ip':
        ajaxData.action = 'dehum_mvp_delete_by_ip';
        ajaxData.ip = $form.find('input[name="delete_ip"]').val();
        break;
      default:
        return;
    }

    // Disable button to prevent multiple clicks
    const $btn = $form.find('button[type="submit"]');
    const originalText = $btn.text();
    $btn.prop('disabled', true).text('Deleting…');

    $.post(ajaxurl, ajaxData, function (response) {
      if (response.success) {
        showAdminNotice('success', response.data.message);
        // Simple approach: reload list to reflect changes
        location.reload();
      } else {
        showAdminNotice('error', response.data.message || 'Deletion failed.');
        $btn.prop('disabled', false).text(originalText);
      }
    }).fail(function () {
      showAdminNotice('error', 'Error occurred during deletion.');
      $btn.prop('disabled', false).text(originalText);
    });
  });

  // Individual session deletion via AJAX
  function deleteSession(sessionId, conversationCard) {
    // Show loading state
    conversationCard.addClass('deleting');

    $.ajax({
      url: ajaxurl,
      type: 'POST',
      data: {
        action: 'dehum_mvp_delete_session',
        session_id: sessionId,
        nonce: dehum_admin_vars.delete_nonce
      },
      success: function (response) {
        if (response.success) {
          // Remove the conversation card with animation
          conversationCard.fadeOut(300, function () {
            $(this).remove();
            updateResultsCount();
          });

          // Show success message
          showAdminNotice('success', response.data.message);
        } else {
          conversationCard.removeClass('deleting');
          showAdminNotice('error', response.data.message || 'Failed to delete conversation.');
        }
      },
      error: function () {
        conversationCard.removeClass('deleting');
        showAdminNotice('error', 'Error occurred while deleting conversation.');
      }
    });
  }

  // Conversation expansion functionality
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

  // Load conversation details via AJAX
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
          container.html('<div class="loading-state error">Failed to load conversation</div>');
        }
      },
      error: function () {
        container.html('<div class="loading-state error">Error loading conversation</div>');
      }
    });
  }

  // Display conversation in chat bubble format
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
      html += '<div class="bubble-text">' + formatContent(msg.message) + '</div>';
      html += '<div class="bubble-time">' + msg.timestamp + '</div>';
      html += '</div>';
      html += '</div>';

      // AI response
      html += '<div class="chat-bubble ai-bubble">';
      html += '<div class="bubble-avatar">🤖</div>';
      html += '<div class="bubble-content">';
      html += '<div class="bubble-text">' + formatContent(msg.response) + '</div>';
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

  // Format content with markdown support (same as frontend)
  function formatContent(text) {
    // First escape any existing HTML to prevent XSS
    let processed = escapeHtml(text);

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
      const safeUrl = escapeHtml(url);
      return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    });

    // Convert plain URLs to clickable links
    processed = processed.replace(/(^|[^"'])(https?:\/\/[^\s<>"']+)/g, (match, prefix, url) => {
      // Don't convert URLs that are already inside href attributes
      if (match.includes('href=')) return match;

      const safeUrl = escapeHtml(url);
      return `${prefix}<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${url}</a>`;
    });

    return processed;
  }

  // Escape HTML to prevent XSS
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Show admin notice
  function showAdminNotice(type, message) {
    const noticeHtml = `<div class="notice notice-${type} is-dismissible"><p>${message}</p></div>`;
    $('.wrap h1').after(noticeHtml);

    // Auto-dismiss after 5 seconds
    setTimeout(function () {
      $('.notice.is-dismissible').not('[data-permanent]').fadeOut();
    }, 5000);
  }

  // Update results count after deletion
  function updateResultsCount() {
    const remainingCards = $('.conversation-card').length;
    $('.results-info').html(`Showing ${remainingCards} conversation(s)`);

    // Hide pagination if no results remain on this page
    if (remainingCards === 0) {
      $('.dehum-pagination').hide();
      if ($('.conversation-card').length === 0) {
        $('#conversations-list').html('<div class="dehum-empty-state"><div class="empty-icon">💬</div><h3>No conversations found</h3><p>All conversations have been deleted or no conversations match your current filters.</p></div>');
      }
    }
  }

  // Initialize page
  updateBulkActionState();
}); 