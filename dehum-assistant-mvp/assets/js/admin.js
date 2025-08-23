// Lean Admin JS for Dehumidifier Assistant: Efficient interactions, minimal DOM touches.

jQuery(document).ready(function ($) {
  // Cache frequent DOM elements for performance
  const $conversationsList = $('#conversations-list');
  const $resultsInfo = $('.results-info');
  const $pagination = $('.dehum-pagination');
  const $bulkSelector = $('#bulk-action-selector');
  const $bulkApplyBtn = $('#bulk-apply-btn');
  const $masterCheckbox = $('#master-select-all');

  // Event delegation for conversation toggles
  $conversationsList.on('click', '.card-header', function (e) {
    if ($(e.target).closest('.conversation-checkbox, .delete-session-btn, .conversation-actions').length) return;
    const $card = $(this).closest('.conversation-card');
    const sessionId = $card.data('session');
    toggleConversation(sessionId, $card);
  });

  // Individual delete
  $conversationsList.on('click', '.delete-session-btn', function (e) {
    e.stopPropagation();
    const sessionId = $(this).data('session');
    const $card = $(this).closest('.conversation-card');
    if (confirm('Delete this conversation? This cannot be undone.')) {
      deleteSession(sessionId, $card);
    }
  });

  // Checkbox changes
  $conversationsList.on('change', '.session-checkbox', updateBulkState);
  $masterCheckbox.on('change', function () {
    selectAllConversations(this.checked);
  });

  // Bulk selector change
  $bulkSelector.on('change', updateBulkState);

  // Select all/none
  window.selectAllConversations = function (selectAll) {
    $('.session-checkbox').prop('checked', selectAll);
    updateBulkState();
  };

  // Bulk delete confirmation
  window.confirmBulkDelete = function () {
    const selectedCount = $('.session-checkbox:checked').length;
    if (selectedCount === 0) {
      alert('Select conversations to delete.');
      return false;
    }
    return confirm(`Delete ${selectedCount} conversation(s)? This cannot be undone.`);
  };

  // Toggle custom dates
  window.toggleCustomDates = function (value) {
    $('#custom-dates').toggle(value === 'custom');
  };

  // Toggle advanced delete
  window.toggleAdvancedDelete = function () {
    $('#advanced-delete').slideToggle(200);
  };

  // Update bulk UI state
  function updateBulkState() {
    const selectedCount = $('.session-checkbox:checked').length;
    const totalCheckboxes = $('.session-checkbox').length;
    $masterCheckbox.prop('checked', selectedCount > 0 && selectedCount === totalCheckboxes);

    const action = $bulkSelector.val();
    $bulkApplyBtn.prop('disabled', !(selectedCount > 0 && action === 'delete'))
      .text(action === 'delete' ? `Delete Selected (${selectedCount})` : 'Apply');

    // Sync selected IDs to form (lean: only when needed)
    $('input[name="selected_sessions[]"]').not('.session-checkbox').remove();
    if (action === 'delete') {
      $('.session-checkbox:checked').each(function () {
        $('#bulk-delete-form').append(`<input type="hidden" name="selected_sessions[]" value="${this.value}">`);
      });
    }
  }

  // Handle bulk form submission (AJAX for delete)
  $('#bulk-delete-form').on('submit', function (e) {
    if ($bulkSelector.val() !== 'delete') return;
    e.preventDefault();
    if (!confirmBulkDelete()) return;

    const selectedIds = $('.session-checkbox:checked').map(function () { return this.value; }).get();
    if (!selectedIds.length) return;

    const nonce = $(this).find('input[name="bulk_nonce"]').val();
    $bulkApplyBtn.prop('disabled', true).text('Deleting…');

    $.ajax({
      url: ajaxurl,
      type: 'POST',
      data: { action: 'dehum_mvp_bulk_delete_sessions', session_ids: selectedIds, nonce: nonce },
      success: (res) => {
        if (res.success) {
          res.data.session_ids.forEach(id => {
            $(`[data-session="${id}"]`).fadeOut(300, function () { $(this).remove(); updateResults(); });
          });
          showNotice('success', res.data.message);
          location.reload(); // Simple refresh to update list
        } else {
          showNotice('error', res.data.message || 'Bulk delete failed.');
        }
        resetBulkUI();
      },
      error: () => {
        showNotice('error', 'Bulk delete error.');
        resetBulkUI();
      }
    });
  });

  // Handle quick/advanced deletes (AJAX)
  $('.quick-delete-actions form, #advanced-delete form').on('submit', function (e) {
    e.preventDefault();
    const $form = $(this);
    const action = $form.find('input[name="bulk_action"]').val();
    const nonce = $form.find('input[name="bulk_nonce"]').val();
    if (!action || !confirm('This cannot be undone. Proceed?')) return;

    let data = { action: `dehum_mvp_${action}`, nonce: nonce };
    if (action === 'delete_by_date') {
      data.start_date = $form.find('input[name="delete_start_date"]').val();
      data.end_date = $form.find('input[name="delete_end_date"]').val();
    } else if (action === 'delete_by_ip') {
      data.ip = $form.find('input[name="delete_ip"]').val();
    }

    const $btn = $form.find('button[type="submit"]');
    const originalText = $btn.text();
    $btn.prop('disabled', true).text('Deleting…');

    $.post(ajaxurl, data, (res) => {
      if (res.success) {
        showNotice('success', res.data.message);
        location.reload(); // Simple refresh to update list
      } else {
        showNotice('error', res.data.message || 'Delete failed.');
      }
      $btn.prop('disabled', false).text(originalText);
    }).fail(() => {
      showNotice('error', 'Delete error.');
      $btn.prop('disabled', false).text(originalText);
    });
  });

  // Toggle conversation
  function toggleConversation(sessionId, $card) {
    const $content = $card.find('.card-content');
    const $icon = $card.find('.expand-icon');
    $content.slideToggle(200);
    $icon.toggleClass('expanded');
    if ($content.is(':visible') && $content.find('.loading-state').length) {
      loadConversation(sessionId, $content);
    }
  }

  // Load conversation details
  function loadConversation(sessionId, $container) {
    $container.html('<div class="loading-state"><div class="loading-spinner"></div>Loading...</div>');
    $.ajax({
      url: ajaxurl,
      type: 'POST',
      data: { action: 'dehum_mvp_get_session_details', session_id: sessionId, nonce: dehum_admin_vars.nonce },
      success: (res) => {
        if (res.success && res.data.length) {
          renderConversation($container, res.data);
        } else {
          $container.html('<div class="loading-state error">Failed to load</div>');
        }
      },
      error: () => $container.html('<div class="loading-state error">Load error</div>')
    });
  }

  // Render conversation UI
  function renderConversation($container, messages) {
    let html = '<div class="conversation-thread">';
    html += `<div class="conversation-thread-header"><strong>Conversation (${messages.length} exchanges)</strong></div>`;
    html += '<div class="conversation-messages">';
    messages.forEach(msg => {
      // User message with blue shading
      html += `<div class="chat-bubble user-bubble"><div class="bubble-content"><div class="bubble-text"><strong>User:</strong> ${formatContent(msg.message)}</div><div class="bubble-time">${msg.timestamp}</div></div></div>`;
      // AI response with gray shading
      html += `<div class="chat-bubble ai-bubble"><div class="bubble-content"><div class="bubble-text"><strong>Assistant:</strong> ${formatContent(msg.response)}</div><div class="bubble-time">${msg.timestamp}</div></div></div>`;
    });
    html += '</div>';
    html += `<div class="conversation-thread-footer">Session ID: <code>${messages[0].id}</code> | IP: <code>${messages[0].user_ip}</code> | Total: ${messages.length * 2}</div>`;
    html += '</div>';
    $container.html(html);
  }

  // Format content (simple markdown)
  function formatContent(text) {
    return escapeHtml(text)
      .replace(/\n/g, '<br>')
      .replace(/### (.*?)<br>/g, '<h3>$1</h3>')
      .replace(/## (.*?)<br>/g, '<h2>$1</h2>')
      .replace(/# (.*?)<br>/g, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
      .replace(/(^|[^"'])(https?:\/\/[^\s<>"']+)/g, '$1<a href="$2" target="_blank">$2</a>');
  }

  function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  // Delete single session
  function deleteSession(sessionId, $card) {
    $card.addClass('deleting');
    $.ajax({
      url: ajaxurl,
      type: 'POST',
      data: { action: 'dehum_mvp_delete_session', session_id: sessionId, nonce: dehum_admin_vars.delete_nonce },
      success: (res) => {
        if (res.success) {
          $card.fadeOut(300, () => { $card.remove(); updateResults(); });
          showNotice('success', res.data.message);
        } else {
          $card.removeClass('deleting');
          showNotice('error', res.data.message || 'Delete failed.');
        }
      },
      error: () => {
        $card.removeClass('deleting');
        showNotice('error', 'Delete error.');
      }
    });
  }

  // Update showNotice to be more persistent
  function showNotice(type, msg) {
    const notice = `<div class="notice notice-${type} is-dismissible"><p>${msg}</p><button type="button" class="notice-dismiss"><span class="screen-reader-text">Dismiss</span></button></div>`;
    if (!$('#admin-notices').length) {
      $('.wrap').prepend('<div id="admin-notices"></div>');
    }
    $('#admin-notices').html(notice);

    // Dismiss handler
    $('#admin-notices').on('click', '.notice-dismiss', function () {
      $(this).closest('.notice').remove();
    });
  }

  // Update results count
  function updateResults() {
    const count = $('.conversation-card').length;
    $resultsInfo.html(`Showing ${count} conversation(s)`);
    if (!count) {
      $pagination.hide();
      $conversationsList.html('<div class="dehum-empty-state"><h3>No conversations</h3><p>No matches or all deleted.</p></div>');
    }
  }

  // Reset bulk UI
  function resetBulkUI() {
    selectAllConversations(false);
    $bulkApplyBtn.prop('disabled', true).text('Apply');
  }

  // Initial setup
  updateBulkState();
});

// Inside ready: add reset click and keydown handlers
jQuery(function ($) {
  $('#dehum-reset-rate-btn').on('click', function () {
    if (!confirm('Reset all rate limits?')) return;
    const nonce = (window.dehum_admin_vars && dehum_admin_vars.rate_nonce) ? dehum_admin_vars.rate_nonce : dehum_admin_vars.nonce;
    $.post(ajaxurl, { action: 'dehum_reset_rate', nonce: nonce }, (res) => {
      const msg = res && res.success ? (res.data && res.data.message ? res.data.message : 'Rate limits reset.') : (res && res.data && res.data.message ? res.data.message : 'Reset failed');
      if (typeof showNotice === 'function') {
        showNotice(res.success ? 'success' : 'error', msg);
      } else {
        const notice = `<div class="notice notice-${res.success ? 'success' : 'error'} is-dismissible"><p>${msg}</p></div>`;
        if ($('.wrap').length) {
          $('.wrap').prepend(notice);
        } else {
          $('body').prepend(notice);
        }
      }
    });
  });

  $('#conversations-list').on('keydown', '.expand-icon', function (e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      $(this).closest('.conversation-card').find('.card-header').trigger('click');
    }
  });
}); 