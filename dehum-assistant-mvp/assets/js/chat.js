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
  let ws = null;
  let wsUrl = null;
  const toolPanels = new WeakMap();
  const thinkingMap = new WeakMap();
  const fragmentsMap = new WeakMap(); // ordered [{ type: 'text', value }, { type: 'tool', html }]

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
    if (ws) {
      try { ws.close(); } catch (_) { }
      ws = null;
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
      if (messages.children.length === 0) {
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

    // Prefer WebSocket streaming; fallback to SSE proxy if needed
    const tempDiv = addMessage('assistant', '');
    toolPanels.set(tempDiv, []);
    thinkingMap.set(tempDiv, false);
    fragmentsMap.set(tempDiv, []);
    let responseText = '';
    let toolContent = '';
    let isDone = false;
    setStreamingUI(true);

    // Removed SSE fallback – WS only. Show a friendly error if WS cannot be used.

    async function fetchWSToken() {
      try {
        const res = await fetch(dehumMVP.ajaxUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: `action=dehum_get_ws_token&session_id=${encodeURIComponent(sessionId)}&nonce=${encodeURIComponent(dehumMVP.nonce)}`
        });
        const data = await res.json();
        if (data && data.success && data.data && data.data.token) return data.data.token;
      } catch (_) { }
      return null;
    }

    function wsUrlFor(token) {
      try {
        const u = new URL(dehumMVP.aiUrl);
        u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
        u.pathname = (u.pathname.replace(/\/$/, '')) + '/ws';
        if (token) {
          u.search = `?token=${encodeURIComponent(token)}`;
        }
        return u.toString();
      } catch (_) {
        return null;
      }
    }

    function wireHandlers(api, source) {
      if (source instanceof WebSocket) {
        source.onmessage = (e) => {
          try { api.onChunk(JSON.parse(e.data)); } catch { /* ignore */ }
        };
        source.onerror = () => { if (!isDone) api.onError(); };
        source.onclose = () => { if (!isDone) api.onError(); };
      }
    }

    function handleData(data) {
      if (data.metadata && data.metadata.phase === 'tools') {
        if (data.metadata.status === 'starting_tools') {
          thinkingMap.set(tempDiv, true);
        } else if (data.metadata.status === 'tools_completed') {
          thinkingMap.set(tempDiv, false);
        }
      }
      if (data.type === 'done') { isDone = true; finalize(); return; }
      if (data.type === 'response') {
        const textChunk = (data.content || '');
        responseText += textChunk;
        const frags = fragmentsMap.get(tempDiv) || [];
        frags.push({ type: 'text', value: textChunk });
        fragmentsMap.set(tempDiv, frags);
      } else if (data.type === 'tool_result') {
        const prettyStr = (() => { try { return JSON.stringify(data.data, null, 2); } catch (_) { return String(data.data || ''); } })();
        const duration = data.metadata && typeof data.metadata.duration_ms === 'number' ? `${data.metadata.duration_ms} ms` : '';
        const safe = (s) => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        let summary = data.tool_name;
        try {
          if (data.tool_name === 'retrieve_relevant_docs') {
            const n = (data.data && (data.data.num_chunks || (data.data.chunks && data.data.chunks.length))) || 0;
            if (n) summary += ` • ${n} chunk${n > 1 ? 's' : ''}`;
          }
          if (data.data && typeof data.data.total_lpd !== 'undefined') {
            summary += ` • ${data.data.total_lpd} L/day`;
          }
        } catch (_) { }
        if (duration) summary += ` • ${duration}`;
        const panel = `<details class="dehum-tool-panel"><summary>${summary}</summary><pre class="dehum-tool-pre">${safe(prettyStr)}</pre></details>`;
        const frags = fragmentsMap.get(tempDiv) || [];
        frags.push({ type: 'tool', html: panel });
        fragmentsMap.set(tempDiv, frags);
      }
      updateMessage(tempDiv, responseText);
      smartScroll(tempDiv);
    }

    function finalize() {
      try { if (ws) ws.close(); } catch (_) { }
      try { if (currentSource) currentSource.close(); } catch (_) { }
      if (responseText && responseText.trim().length > 0) {
        saveConversationWithRetry(text, responseText);
      }
      finalizeStream();
    }

    function fail() {
      fragmentsMap.delete(tempDiv);
      updateMessage(tempDiv, 'Connection failed. Please try again later.', '', false, false);
      finalizeStream();
    }

    (async () => {
      const token = await fetchWSToken();
      wsUrl = wsUrlFor(token);
      if (wsUrl) {
        try {
          ws = new WebSocket(wsUrl);
          ws.onopen = () => {
            ws.send(JSON.stringify({ session_id: sessionId, message: text }));
          };
          wireHandlers({ onChunk: handleData, onClose: finalize, onError: () => { try { ws.close(); } catch (_) { } fail(); } }, ws);
        } catch (_) {
          fail();
        }
      } else {
        updateMessage(tempDiv, 'Chat service not configured. Please contact support.', '', false, false);
        finalizeStream();
      }
    })();
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

  function updateMessage(div, main, tool, hasTool, persist = true) {
    const bubble = div.querySelector('.dehum-message__bubble');
    // If we have fragments, render in order and persist text-only
    const frags = fragmentsMap.get(div);
    if (Array.isArray(frags) && frags.length > 0) {
      let html = '';
      let textOnly = '';
      let textBuffer = '';
      if (thinkingMap.get(div)) html += '<div class="dehum-tool-thinking">Working…</div>';
      for (const frag of frags) {
        if (frag.type === 'text') {
          const v = frag.value || '';
          textOnly += v;
          textBuffer += v;
        } else if (frag.type === 'tool') {
          if (textBuffer) {
            html += parseMarkdown(textBuffer);
            textBuffer = '';
          }
          html += frag.html || '';
        }
      }
      if (textBuffer) {
        html += parseMarkdown(textBuffer);
        textBuffer = '';
      }
      bubble.innerHTML = html;
      addCopyButton(bubble, textOnly.trim());
      if (!isRestoring && persist) updateLastAssistant(textOnly);
      return;
    }
    // Fallback: legacy path
    let html = '';
    if (thinkingMap.get(div)) html += '<div class="dehum-tool-thinking">Working…</div>';
    if (hasTool) html += renderTool(tool);
    const panels = toolPanels.get(div) || [];
    if (panels.length) html += panels.join('');
    html += parseMarkdown(main);
    bubble.innerHTML = html;
    addCopyButton(bubble, main ? main.trim() : '');
    if (!isRestoring && persist && main) updateLastAssistant(main);
  }

  function renderTool(toolText) { return ''; }

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