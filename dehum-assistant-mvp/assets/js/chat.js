// Lean Dehumidifier Chat JS: Streaming to Python backend via WP proxy, session, save to WP.

document.addEventListener('DOMContentLoaded', () => {

  const widget = document.getElementById('dehum-mvp-chat-widget');
  if (!widget) {
    console.error('Chat widget not found');
    return;
  }

  const modal = widget.querySelector('#dehum-mvp-chat-modal');
  const closeBtn = widget.querySelector('#dehum-close-btn');
  const clearBtn = widget.querySelector('#dehum-clear-btn');
  const messages = widget.querySelector('#dehum-chat-messages');
  const input = widget.querySelector('#dehum-chat-input');
  const sendBtn = widget.querySelector('#dehum-send-btn');
  const charCount = widget.querySelector('#dehum-char-count');

  let sessionId = localStorage.getItem('dehum_session') || (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).substring(2));
  localStorage.setItem('dehum_session', sessionId);
  const storageKey = `dehum_history_${sessionId}`;
  let isRestoring = false;
  let isStreaming = false;
  let currentSource = null;

  // Smooth auto-scroll helpers
  const NEAR_BOTTOM_THRESHOLD = 80; // px from bottom considered "near bottom"
  const BUBBLE_TOP_STOP_THRESHOLD = 60; // px from top to stop auto-scrolling for large replies
  let userInteracted = false;

  // Mark interaction to pause auto-scroll
  ['wheel', 'touchstart', 'pointerdown'].forEach(evt => {
    messages.addEventListener(evt, () => { userInteracted = true; }, { passive: true });
  });
  messages.addEventListener('scroll', () => {
    // Resume auto-scroll once user returns to near-bottom
    if (isNearBottom()) userInteracted = false;
  });

  function isNearBottom() {
    const distanceFromBottom = messages.scrollHeight - messages.scrollTop - messages.clientHeight;
    return distanceFromBottom < NEAR_BOTTOM_THRESHOLD;
  }

  function smartScroll(targetDiv) {
    // Only auto-scroll if user hasn't scrolled away from the bottom
    if (userInteracted && !isNearBottom()) return;

    // When streaming large replies, stop once the message top is near the viewport top
    if (targetDiv) {
      const bubbleRect = targetDiv.getBoundingClientRect();
      const containerRect = messages.getBoundingClientRect();
      const bubbleTopWithinContainer = bubbleRect.top - containerRect.top;
      if (bubbleTopWithinContainer <= BUBBLE_TOP_STOP_THRESHOLD) return;
    }

    try {
      messages.scrollTo({ top: messages.scrollHeight, behavior: 'smooth' });
    } catch (_) {
      // Fallback if smooth not supported
      messages.scrollTop = messages.scrollHeight;
    }
  }

  function setStreamingUI(active) {
    isStreaming = !!active;
    if (isStreaming) {
      input.setAttribute('readonly', 'true');
      sendBtn.innerHTML = '<span class="material-symbols-outlined">stop_circle</span>';
      sendBtn.title = 'Stop';
      sendBtn.setAttribute('aria-label', 'Stop streaming');
    } else {
      input.removeAttribute('readonly');
      sendBtn.innerHTML = '<span class="material-symbols-outlined">send</span>';
      sendBtn.title = 'Send';
      sendBtn.setAttribute('aria-label', 'Send message');
    }
  }

  function stopStreaming() {
    if (currentSource) {
      try { currentSource.close(); } catch (_) { }
      currentSource = null;
    }
    setStreamingUI(false);
  }

  function finalizeStream() {
    stopStreaming();
  }

  function getStoredHistory() {
    try {
      const raw = localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  }

  function setStoredHistory(history) {
    try { localStorage.setItem(storageKey, JSON.stringify(history)); } catch (_) { }
  }

  function pushHistory(role, content) {
    const hist = getStoredHistory();
    hist.push({ role, content, t: Date.now() });
    setStoredHistory(hist);
  }

  function updateLastAssistant(content) {
    const hist = getStoredHistory();
    if (hist.length && hist[hist.length - 1].role === 'assistant') {
      hist[hist.length - 1].content = content;
      setStoredHistory(hist);
    } else {
      hist.push({ role: 'assistant', content, t: Date.now() });
      setStoredHistory(hist);
    }
  }

  // Restore from localStorage on load
  (function restoreFromLocal() {
    const hist = getStoredHistory();
    if (hist && hist.length) {
      isRestoring = true;
      hist.forEach(item => addMessage(item.role === 'user' ? 'user' : 'assistant', item.content));
      isRestoring = false;
    }
  })();

  // Delegated open
  document.addEventListener('click', (e) => {
    if (e.target.closest('#dehum-mvp-chat-button')) {
      modal.classList.add('show');
      modal.setAttribute('aria-hidden', 'false');
      if (!messages.innerHTML.trim()) {
        // Load persisted history
        fetch(dehumMVP.ajaxUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: `action=dehum_get_session_history&session_id=${sessionId}&nonce=${dehumMVP.nonce}`
        })
          .then(res => res.json())
          .then(data => {
            if (data.success && Array.isArray(data.data.history) && data.data.history.length) {
              isRestoring = true;
              data.data.history.forEach(item => addMessage(item.role === 'user' ? 'user' : 'assistant', item.content));
              isRestoring = false;
              // Sync server history into localStorage for future
              setStoredHistory(data.data.history.map(h => ({ role: h.role, content: h.content, t: Date.now() })));
            }
          })
          .catch(() => { });
      }
    }
  });

  // Close
  closeBtn.addEventListener('click', () => {
    modal.classList.remove('show');
    modal.setAttribute('aria-hidden', 'true');
  });

  // Close on clicking overlay (outside the chat container)
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.classList.remove('show');
      modal.setAttribute('aria-hidden', 'true');
    }
  });

  // Clear
  clearBtn.addEventListener('click', () => {
    messages.innerHTML = '';
    // Clear backend session
    fetch(dehumMVP.ajaxUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `action=dehum_clear_session&session_id=${sessionId}&nonce=${dehumMVP.nonce}`
    })
      .then(res => res.json())
      .then(() => {
        localStorage.removeItem(storageKey);
        // Reload server-seeded history (will include welcome if empty)
        fetch(dehumMVP.ajaxUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: `action=dehum_get_session_history&session_id=${sessionId}&nonce=${dehumMVP.nonce}`
        })
          .then(r => r.json())
          .then(data => {
            if (data.success && Array.isArray(data.data.history)) {
              isRestoring = true;
              data.data.history.forEach(item => addMessage(item.role === 'user' ? 'user' : 'assistant', item.content));
              isRestoring = false;
              setStoredHistory(data.data.history.map(h => ({ role: h.role, content: h.content, t: Date.now() })));
            }
          })
          .catch(() => { });
      })
      .catch(() => {
        localStorage.removeItem(storageKey);
      });
  });

  // Send / Stop
  sendBtn.addEventListener('click', () => {
    if (isStreaming) {
      stopStreaming();
    } else {
      sendMessage();
    }
  });

  input.addEventListener('keydown', (e) => {
    if (isStreaming) {
      // Block sending while streaming
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
      }
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Auto-resize and char count
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
    charCount.textContent = `${input.value.length}/${dehumMVP.maxLen}`;
    charCount.classList.toggle('exceeded', input.value.length > dehumMVP.maxLen);
  });

  // Removed separate welcome fetch; server seeds welcome in history when empty.

  function sendMessage() {
    if (isStreaming) return; // safety
    const text = input.value.trim();
    if (!text || text.length > dehumMVP.maxLen) return;
    addMessage('user', text);
    input.value = '';
    input.style.height = 'auto';
    charCount.textContent = `0/${dehumMVP.maxLen}`;

    // Stream
    const params = new URLSearchParams({
      action: 'dehum_stream_response',
      message: text,
      session_id: sessionId,
      nonce: dehumMVP.nonce
    });
    const source = new EventSource(`${dehumMVP.ajaxUrl}?${params.toString()}`);
    currentSource = source;
    setStreamingUI(true);

    let responseText = '';
    let toolContent = '';
    let isDone = false;
    const tempDiv = addMessage('assistant', ''); // Streaming placeholder
    source.onmessage = (e) => {
      if (e.data === '[DONE]') {
        isDone = true;
        try { source.close(); } catch (_) { }
        saveConversationWithRetry(text, responseText + (toolContent ? '\n[Tool Results]\n' + toolContent : ''));
        finalizeStream();
        return;
      }
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'done') { // Or your final signal
          isDone = true;
          try { source.close(); } catch (_) { }
          saveConversationWithRetry(text, responseText + (toolContent ? '\n[Tool Results]\n' + toolContent : ''));
          finalizeStream();
          return;
        }
        if (data.type === 'response') {
          responseText += data.content || '';
        } else if (data.type === 'tool_start') {
          toolContent += `Starting ${data.total_tools} tool${data.total_tools > 1 ? 's' : ''}...\n`;
        } else if (data.type === 'tool_progress') {
          toolContent += `${data.message || `Executing tool ${data.tool_index}: ${data.tool_name}`}\n`;
        } else if (data.type === 'tool_result') {
          toolContent += `Result for ${data.tool_name}: ${JSON.stringify(data.data, null, 2)}\n\n`;
        }
        // Persist tool details if any exist
        const hasTool = toolContent.trim().length > 0;
        updateMessage(tempDiv, responseText, toolContent, hasTool);
        smartScroll(tempDiv);
      } catch (err) {
        responseText += e.data;
        updateMessage(tempDiv, responseText, '', false);
      }
    };
    source.onopen = () => { };
    source.onerror = (e) => {
      try { source.close(); } catch (_) { }
      if (isDone) return; // Normal closure
      updateMessage(tempDiv, 'Stream failed. Please try again.', '', false);
      finalizeStream();
      const retryBtn = document.createElement('button');
      retryBtn.className = 'dehum-retry-btn';
      retryBtn.textContent = 'Retry';
      retryBtn.addEventListener('click', () => {
        tempDiv.remove();
        sendMessage();
      });
      tempDiv.querySelector('.dehum-message__bubble').appendChild(retryBtn);
    };
    source.addEventListener('final', () => {
      try { source.close(); } catch (_) { }
      saveConversationWithRetry(text, responseText + toolContent);
      finalizeStream();
    });
  }

  function parseResponse(text) {
    // Simple parser: assume if contains [TOOL_START] ... [TOOL_END], extract
    const toolMatch = text.match(/\[\TOOL_START\]([\s\S]*?)\[\TOOL_END\]/);
    if (toolMatch) {
      return { main: text.replace(toolMatch[0], ''), tool: toolMatch[1].trim() };
    }
    return { main: text, tool: '' };
  }

  function addMessage(type, text, tool = '') {
    const div = document.createElement('div');
    div.className = `dehum-message dehum-message--${type}`;
    const bubble = document.createElement('div');
    bubble.className = 'dehum-message__bubble';
    div.appendChild(bubble);
    const timestamp = document.createElement('div');
    timestamp.className = 'dehum-message__timestamp';
    timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    div.appendChild(timestamp);

    if (type === 'assistant') {
      if (text) {
        updateMessage(div, text, tool, !!tool);
        addCopyButton(bubble);
        if (!isRestoring) pushHistory('assistant', text);
      } else {
        // Show loading dots while waiting for response
        bubble.innerHTML = `
          <div class="dehum-loading">
            <div class="dehum-loading-dot"></div>
            <div class="dehum-loading-dot"></div>
            <div class="dehum-loading-dot"></div>
          </div>
        `;
      }
    } else {
      bubble.innerHTML = parseMarkdown(text);
      if (type === 'user' && !isRestoring) pushHistory('user', text);
    }

    messages.appendChild(div);
    smartScroll(div);
    return div;
  }

  function updateMessage(div, main, tool, hasTool) {
    const bubble = div.querySelector('.dehum-message__bubble');
    let html = '';
    if (hasTool) {
      html += renderTool(tool);
    }
    html += parseMarkdown(main);
    bubble.innerHTML = html;
    addCopyButton(bubble, main.trim());
    if (!isRestoring) updateLastAssistant(main);
  }

  function renderTool(toolText) {
    const safe = (s) => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // Try to format lines into readable blocks
    const lines = (toolText || '').trim().split(/\n+/).filter(Boolean);
    const formatted = lines.map(line => {
      // Highlight headings and tool names
      if (/^Starting /i.test(line) || /^Result for /i.test(line) || /^Executing /i.test(line)) {
        return `<div class="dehum-tool-line"><strong>${safe(line)}</strong></div>`;
      }
      // Pretty-print JSON blocks if present
      const m = line.match(/^(Result for [^:]+: )(.+)$/);
      if (m) {
        let jsonPart = safe(m[2]);
        return `<div class="dehum-tool-line"><em>${safe(m[1])}</em><pre class="dehum-tool-pre">${jsonPart}</pre></div>`;
      }
      return `<div class="dehum-tool-line">${safe(line)}</div>`;
    }).join('');

    return `<details class="dehum-tool-details">
      <summary>Tool Use <span class="material-symbols-outlined">build</span></summary>
      <div class="dehum-tool-content">${formatted}</div>
    </details>`;
  }

  function addCopyButton(bubble, content) {
    if (!content) return;
    const copyBtn = document.createElement('button');
    copyBtn.className = 'dehum-copy-btn';
    copyBtn.innerHTML = '<span class="material-symbols-outlined">content_copy</span>';
    copyBtn.title = 'Copy to clipboard';
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(content).then(() => {
        copyBtn.innerHTML = '<span class="material-symbols-outlined">check</span>';
        setTimeout(() => copyBtn.innerHTML = '<span class="material-symbols-outlined">content_copy</span>', 2000);
      });
    });
    bubble.appendChild(copyBtn);
  }

  // Modified saveConversation with retry and localStorage fallback
  async function saveConversationWithRetry(userMsg, assistResp, maxRetries = 3) {
    // Stash to localStorage as fallback before attempting save
    const fallbackKey = `dehum_unsaved_${sessionId}`;
    const fallbackData = { user: userMsg, assistant: assistResp, timestamp: Date.now() };
    localStorage.setItem(fallbackKey, JSON.stringify(fallbackData));

    const body = `action=dehum_mvp_save_conversation&message=${encodeURIComponent(userMsg)}&response=${encodeURIComponent(assistResp)}&session_id=${sessionId}&nonce=${dehumMVP.saveNonce}`;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const response = await fetch(dehumMVP.ajaxUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: body
        });
        const data = await response.json();
        if (data.success) {
          // Clear fallback on success
          localStorage.removeItem(fallbackKey);
          console.log('Conversation saved successfully');
          return true;
        }
      } catch (err) {
        console.error(`Save attempt ${attempt} failed: ${err}`);
      }
      // Exponential backoff
      await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, attempt - 1)));
    }
    console.error('All save attempts failed. Data preserved in localStorage.');
    return false;
  }

  function parseMarkdown(text) {
    if (!text) return '';
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // Images first (so link replacer below doesn't consume them)
    text = text
      .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer"><img src="$2" alt="$1" loading="lazy" class="dehum-chat-image" onerror="this.alt=\'Image failed\'; this.src=\'\';" /></a>');

    return text
      .replace(/\n{2,}/g, '<br><br>')
      .replace(/\n/g, '<br>')
      .replace(/### (.*?)(<br>|$)/g, '<h3>$1</h3>')
      .replace(/## (.*?)(<br>|$)/g, '<h2>$1</h2>')
      .replace(/# (.*?)(<br>|$)/g, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
      // Links AFTER images so we don't clobber image syntax
      .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  }
});