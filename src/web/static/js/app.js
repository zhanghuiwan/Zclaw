/**
 * Zclaw Web UI - Frontend Application
 *
 * 处理 WebSocket 通信、聊天交互、文件浏览和工具可视化。
 */

// ============================================================
// State Management
// ============================================================

const state = {
    ws: null,
    connected: false,
    connecting: false,
    generating: false,
    currentAssistantContent: '',
    currentToolCards: {},
    currentLoopRound: 0,
    currentPermRequestId: null,
    currentFilePath: '.',
    agentStatus: null,
    reconnectTimer: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 20,
    messages: [],
};

// ============================================================
// DOM References
// ============================================================

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
    connectionStatus: $('#connectionStatus'),
    modelInfo: $('#modelInfo'),
    chatMessages: $('#chatMessages'),
    welcomeMessage: $('#welcomeMessage'),
    chatInput: $('#chatInput'),
    btnSend: $('#btnSend'),
    btnCancel: $('#btnCancel'),
    tokenInfo: $('#tokenInfo'),
    sidebar: $('#sidebar'),
    fileList: $('#fileList'),
    toolList: $('#toolList'),
    sessionList: $('#sessionList'),
    currentPath: $('#currentPath'),
    permissionDialog: $('#permissionDialog'),
    permToolName: $('#permToolName'),
    permArgs: $('#permArgs'),
    permTitle: $('#permTitle'),
    permIcon: $('#permIcon'),
    permAllow: $('#permAllow'),
    permDeny: $('#permDeny'),
    fileViewerModal: $('#fileViewerModal'),
    fileViewerTitle: $('#fileViewerTitle'),
    fileViewerContent: $('#fileViewerContent'),
    settingsModal: $('#settingsModal'),
    settingsContent: $('#settingsContent'),
};

// ============================================================
// Utility Functions
// ============================================================

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}

function getFileIcon(name, isDir) {
    if (isDir) return '📁';
    const ext = name.split('.').pop().toLowerCase();
    const icons = {
        py: '🐍', js: '📜', ts: '🔷', tsx: '⚛️', jsx: '⚛️',
        json: '📋', yaml: '⚙️', yml: '⚙️', toml: '⚙️',
        md: '📝', txt: '📄', csv: '📊',
        html: '🌐', css: '🎨', scss: '🎨',
        rs: '🏹', go: '🔵', java: '☕', c: '🔧', cpp: '🔧', h: '🔧',
        sh: '🖥️', bash: '🖥️',
        png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️', svg: '🖼️',
        lock: '🔒', env: '🔐',
    };
    return icons[ext] || '📄';
}

function simpleMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);

    // Code blocks
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        return `<pre><code>${code}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');

    // Blockquote
    html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

    // Unordered lists
    html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
    // Deduplicate nested <ul>
    html = html.replace(/<\/ul>\s*<ul>/g, '');

    // Ordered lists
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // Paragraphs (double newline)
    html = html.replace(/\n\n/g, '</p><p>');
    // Single newlines
    html = html.replace(/\n/g, '<br>');

    // Wrap in paragraph
    html = '<p>' + html + '</p>';
    // Clean up empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');
    // Clean up pre/code inside p
    html = html.replace(/<p>(<pre>)/g, '$1');
    html = html.replace(/(<\/pre>)<\/p>/g, '$1');
    html = html.replace(/<p>(<h[234]>)/g, '$1');
    html = html.replace(/(<\/h[234]>)<\/p>/g, '$1');
    html = html.replace(/<p>(<ul>)/g, '$1');
    html = html.replace(/(<\/ul>)<\/p>/g, '$1');
    html = html.replace(/<p>(<blockquote>)/g, '$1');
    html = html.replace(/(<\/blockquote>)<\/p>/g, '$1');

    return html;
}

// ============================================================
// WebSocket Connection
// ============================================================

function connectWebSocket() {
    if (state.connecting) return;
    state.connecting = true;
    updateConnectionStatus('connecting');

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/api/ws`;

    try {
        state.ws = new WebSocket(wsUrl);
    } catch (e) {
        state.connecting = false;
        updateConnectionStatus('disconnected');
        scheduleReconnect();
        return;
    }

    state.ws.onopen = () => {
        state.connected = true;
        state.connecting = false;
        state.reconnectAttempts = 0;
        updateConnectionStatus('connected');
        loadStatus();
        loadFiles('.');
        loadTools();
    };

    state.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleWSMessage(msg);
        } catch (e) {
            console.error('Failed to parse WS message:', e);
        }
    };

    state.ws.onclose = () => {
        state.connected = false;
        state.connecting = false;
        updateConnectionStatus('disconnected');
        scheduleReconnect();
    };

    state.ws.onerror = () => {
        state.connecting = false;
    };
}

function disconnectWebSocket() {
    if (state.reconnectTimer) {
        clearTimeout(state.reconnectTimer);
        state.reconnectTimer = null;
    }
    state.reconnectAttempts = state.maxReconnectAttempts;
    if (state.ws) {
        state.ws.close();
        state.ws = null;
    }
    state.connected = false;
    state.connecting = false;
    updateConnectionStatus('disconnected');
}

function scheduleReconnect() {
    if (state.reconnectAttempts >= state.maxReconnectAttempts) return;
    const delay = Math.min(1000 * Math.pow(2, state.reconnectAttempts), 30000);
    state.reconnectAttempts++;
    state.reconnectTimer = setTimeout(() => {
        connectWebSocket();
    }, delay);
}

function sendWS(data) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify(data));
        return true;
    }
    return false;
}

function updateConnectionStatus(status) {
    const dot = dom.connectionStatus.querySelector('.status-dot');
    const text = dom.connectionStatus.querySelector('.status-text');

    dot.className = 'status-dot ' + status;
    const labels = {
        connected: '已连接',
        disconnected: '未连接',
        connecting: '连接中...',
    };
    text.textContent = labels[status] || status;
}

// ============================================================
// WebSocket Message Handler
// ============================================================

function handleWSMessage(msg) {
    const { type, data } = msg;

    switch (type) {
        case 'stream_delta':
            handleStreamDelta(data);
            break;
        case 'tool_start':
            handleToolStart(data);
            break;
        case 'tool_end':
            handleToolEnd(data);
            break;
        case 'loop_start':
            handleLoopStart(data);
            break;
        case 'usage':
            handleUsage(data);
            break;
        case 'done':
            handleDone();
            break;
        case 'error':
            handleError(data);
            break;
        case 'info':
            handleInfo(data);
            break;
        case 'permission':
            handlePermission(data);
            break;
        default:
            console.log('Unknown WS message type:', type);
    }
}

// ============================================================
// Chat Message Handlers
// ============================================================

function handleStreamDelta(data) {
    state.generating = true;
    updateInputState();

    // Hide welcome
    if (dom.welcomeMessage) {
        dom.welcomeMessage.remove();
    }

    state.currentAssistantContent += (data.content || '');

    // Find or create assistant message
    let assistantMsg = dom.chatMessages.querySelector('.message.assistant:last-of-type');
    if (!assistantMsg) {
        assistantMsg = createAssistantMessage();
        dom.chatMessages.appendChild(assistantMsg);
    }

    // Update content
    const body = assistantMsg.querySelector('.message-body');
    body.innerHTML = simpleMarkdown(state.currentAssistantContent);
    scrollToBottom();
}

function handleToolStart(data) {
    const { id, name } = data;
    state.currentToolCards[id] = {
        name,
        status: 'running',
        content: '',
        startTime: Date.now(),
    };

    // Hide welcome
    if (dom.welcomeMessage) {
        dom.welcomeMessage.remove();
    }

    // Create or update tool card
    let assistantMsg = dom.chatMessages.querySelector('.message.assistant:last-of-type');
    if (!assistantMsg) {
        assistantMsg = createAssistantMessage();
        dom.chatMessages.appendChild(assistantMsg);
    }

    const body = assistantMsg.querySelector('.message-body');
    const card = createToolCard(id, name, 'running');
    body.appendChild(card);
    scrollToBottom();
}

function handleToolEnd(data) {
    const { id, name, success, error } = data;
    const cardInfo = state.currentToolCards[id];
    if (cardInfo) {
        cardInfo.status = success ? 'success' : 'error';
    }

    const card = dom.chatMessages.querySelector(`.tool-card[data-tool-id="${id}"]`);
    if (card) {
        const statusEl = card.querySelector('.tool-status');
        if (statusEl) {
            statusEl.className = 'tool-status ' + (success ? 'success' : 'error');
            statusEl.textContent = success ? '✓ 完成' : '✗ 失败';
        }
        if (error) {
            const body = card.querySelector('.tool-card-body');
            if (body) {
                body.innerHTML = `<pre>${escapeHtml(error)}</pre>`;
            }
        }
    }
    scrollToBottom();
}

function handleLoopStart(data) {
    state.currentLoopRound = data.round;
    if (data.round > 1) {
        let assistantMsg = dom.chatMessages.querySelector('.message.assistant:last-of-type');
        if (assistantMsg) {
            const body = assistantMsg.querySelector('.message-body');
            const indicator = document.createElement('div');
            indicator.className = 'loop-indicator';
            indicator.innerHTML = `<span class="dot"></span>第 ${data.round} 轮工具调用`;
            body.appendChild(indicator);
            scrollToBottom();
        }
    }
}

function handleUsage(data) {
    const { prompt_tokens, completion_tokens, total_tokens } = data;
    dom.tokenInfo.textContent = `Tokens: ${prompt_tokens} + ${completion_tokens} = ${total_tokens}`;
}

function handleDone() {
    state.generating = false;
    updateInputState();

    // If there was assistant content, make sure the message is finalized
    if (state.currentAssistantContent) {
        let assistantMsg = dom.chatMessages.querySelector('.message.assistant:last-of-type');
        if (assistantMsg) {
            const body = assistantMsg.querySelector('.message-body');
            body.innerHTML = simpleMarkdown(state.currentAssistantContent);
        }
    }

    // Reset state
    state.currentAssistantContent = '';
    state.currentToolCards = {};
    state.currentLoopRound = 0;
    scrollToBottom();
}

function handleError(data) {
    state.generating = false;
    updateInputState();

    if (dom.welcomeMessage) {
        dom.welcomeMessage.remove();
    }

    const errorMsg = data?.message || '发生未知错误';
    const msgEl = document.createElement('div');
    msgEl.className = 'message assistant';
    msgEl.innerHTML = `
        <div class="message-avatar">🏹</div>
        <div class="message-content">
            <div class="message-role">助手 · 错误</div>
            <div class="message-body" style="color: var(--accent-danger);">${escapeHtml(errorMsg)}</div>
        </div>
    `;
    dom.chatMessages.appendChild(msgEl);
    scrollToBottom();
}

function handleInfo(data) {
    const infoMsg = data?.message || '';
    if (!infoMsg) return;

    const msgEl = document.createElement('div');
    msgEl.className = 'message assistant';
    msgEl.innerHTML = `
        <div class="message-avatar">ℹ️</div>
        <div class="message-content">
            <div class="message-role">系统</div>
            <div class="message-body" style="color: var(--text-secondary);">${escapeHtml(infoMsg).replace(/\n/g, '<br>')}</div>
        </div>
    `;
    dom.chatMessages.appendChild(msgEl);
    scrollToBottom();
}

function handlePermission(data) {
    const { request_id, tool_name, arguments: args, danger_level } = data;
    state.currentPermRequestId = request_id;

    dom.permToolName.textContent = tool_name;
    dom.permArgs.textContent = JSON.stringify(args, null, 2);

    if (danger_level === 'dangerous') {
        dom.permTitle.textContent = '⚠️ 危险操作需要确认';
        dom.permIcon.textContent = '🚨';
    } else {
        dom.permTitle.textContent = '🔐 操作需要确认';
        dom.permIcon.textContent = '⚠️';
    }

    dom.permissionDialog.classList.remove('hidden');
}

// ============================================================
// DOM Creation Helpers
// ============================================================

function createUserMessage(text) {
    const el = document.createElement('div');
    el.className = 'message user';
    el.innerHTML = `
        <div class="message-avatar">👤</div>
        <div class="message-content">
            <div class="message-role">你</div>
            <div class="message-body">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
        </div>
    `;
    return el;
}

function createAssistantMessage() {
    const el = document.createElement('div');
    el.className = 'message assistant';
    el.innerHTML = `
        <div class="message-avatar">🏹</div>
        <div class="message-content">
            <div class="message-role">助手</div>
            <div class="message-body"><div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div></div>
        </div>
    `;
    return el;
}

function createToolCard(id, name, status) {
    const el = document.createElement('div');
    el.className = 'tool-card';
    el.dataset.toolId = id;
    el.innerHTML = `
        <div class="tool-card-header">
            <span class="tool-icon">🔧</span>
            <span class="tool-name">${escapeHtml(name)}</span>
            <span class="tool-status ${status}">${status === 'running' ? '⏳ 执行中...' : (status === 'success' ? '✓ 完成' : '✗ 失败')}</span>
        </div>
        <div class="tool-card-body" style="display:none;"></div>
    `;
    return el;
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
    });
}

// ============================================================
// User Actions
// ============================================================

function sendMessage() {
    const text = dom.chatInput.value.trim();
    if (!text || state.generating) return;

    // Add user message to chat
    if (dom.welcomeMessage) {
        dom.welcomeMessage.remove();
    }
    const userMsg = createUserMessage(text);
    dom.chatMessages.appendChild(userMsg);

    // Clear input
    dom.chatInput.value = '';
    autoResizeInput();

    // Send via WebSocket
    sendWS({
        type: 'chat',
        data: { message: text },
    });

    scrollToBottom();
}

function cancelGeneration() {
    sendWS({ type: 'cancel', data: {} });
}

function respondPermission(allowed) {
    if (state.currentPermRequestId) {
        sendWS({
            type: 'permission',
            data: {
                request_id: state.currentPermRequestId,
                allowed: allowed,
            },
        });
        state.currentPermRequestId = null;
    }
    dom.permissionDialog.classList.add('hidden');
}

function updateInputState() {
    dom.btnSend.disabled = state.generating;
    dom.btnCancel.disabled = !state.generating;
    dom.chatInput.disabled = state.generating;

    if (state.generating) {
        dom.chatInput.placeholder = '生成中...';
    } else {
        dom.chatInput.placeholder = '输入消息... (Enter 发送, Shift+Enter 换行)';
    }
}

function autoResizeInput() {
    dom.chatInput.style.height = 'auto';
    dom.chatInput.style.height = Math.min(dom.chatInput.scrollHeight, 200) + 'px';
}

// ============================================================
// API Calls
// ============================================================

async function apiGet(path) {
    try {
        const resp = await fetch('/api' + path);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || resp.statusText);
        }
        return await resp.json();
    } catch (e) {
        console.error(`API GET ${path} failed:`, e);
        return null;
    }
}

async function apiPost(path, body) {
    try {
        const resp = await fetch('/api' + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || resp.statusText);
        }
        return await resp.json();
    } catch (e) {
        console.error(`API POST ${path} failed:`, e);
        return null;
    }
}

// ============================================================
// Status & Config
// ============================================================

async function loadStatus() {
    const data = await apiGet('/status');
    if (data) {
        state.agentStatus = data;
        dom.modelInfo.textContent = `${data.provider} / ${data.model}`;
    }
}

async function loadConfig() {
    const data = await apiGet('/config');
    if (!data) return;

    let html = '';

    // LLM Section
    html += '<div class="settings-section">';
    html += '<div class="settings-section-header">🤖 LLM 配置</div>';
    html += settingsRow('默认 Provider', data.llm.default_provider);
    html += settingsRow('温度', data.llm.temperature);
    html += settingsRow('最大 Tokens', data.llm.max_tokens);
    html += settingsRow('回退 Providers', data.llm.fallback_providers.join(', ') || '无');
    for (const [name, pc] of Object.entries(data.llm.providers)) {
        html += `<div class="settings-row" style="background:var(--bg-primary);margin:0 8px;border-radius:4px;padding:6px 8px;">
            <span class="settings-key" style="color:var(--accent-primary);font-weight:500;">${escapeHtml(name)}</span>
            <span class="settings-value">${escapeHtml(pc.model)}</span>
        </div>`;
        html += settingsRow('  Base URL', pc.base_url, true);
        html += settingsRow('  API Key', pc.api_key, true);
        html += settingsRow('  上下文', pc.max_context_tokens + ' tokens', true);
    }
    html += '</div>';

    // Agent Section
    html += '<div class="settings-section">';
    html += '<div class="settings-section-header">🏹 Agent 配置</div>';
    html += settingsRow('最大循环轮次', data.agent.max_loop_rounds);
    html += settingsRow('规划模式', data.agent.planning_mode);
    html += '</div>';

    // Web Section
    html += '<div class="settings-section">';
    html += '<div class="settings-section-header">🌐 Web 配置</div>';
    html += settingsRow('监听地址', data.web.host);
    html += settingsRow('监听端口', data.web.port);
    html += '</div>';

    dom.settingsContent.innerHTML = html;
}

function settingsRow(key, value, indent = false) {
    const prefix = indent ? '  ' : '';
    return `<div class="settings-row${indent ? ' sub-row' : ''}">
        <span class="settings-key">${prefix}${escapeHtml(String(key))}</span>
        <span class="settings-value" title="${escapeHtml(String(value))}">${escapeHtml(String(value))}</span>
    </div>`;
}

// ============================================================
// File Browser
// ============================================================

async function loadFiles(path) {
    state.currentFilePath = path;
    dom.currentPath.querySelector('.path-text').textContent = path;

    const data = await apiGet(`/files/list?path=${encodeURIComponent(path)}`);
    if (!data) {
        dom.fileList.innerHTML = '<div class="empty-state">加载失败</div>';
        return;
    }

    if (data.length === 0) {
        dom.fileList.innerHTML = '<div class="empty-state">空目录</div>';
        return;
    }

    dom.fileList.innerHTML = '';
    for (const item of data) {
        const el = document.createElement('div');
        el.className = 'file-item';
        el.innerHTML = `
            <span class="file-icon">${getFileIcon(item.name, item.is_dir)}</span>
            <span class="file-name ${item.is_dir ? 'dir' : ''}">${escapeHtml(item.name)}</span>
            <span class="file-meta">${item.is_dir ? '' : formatSize(item.size)}</span>
        `;

        if (item.is_dir) {
            el.addEventListener('click', () => loadFiles(item.path));
        } else {
            el.addEventListener('click', () => viewFile(item.path, item.name));
        }

        dom.fileList.appendChild(el);
    }
}

async function viewFile(path, name) {
    const data = await apiGet(`/files/read?path=${encodeURIComponent(path)}`);
    if (!data) {
        alert('无法读取文件');
        return;
    }

    dom.fileViewerTitle.textContent = name;
    dom.fileViewerContent.textContent = data.content;
    dom.fileViewerModal.classList.remove('hidden');
}

// ============================================================
// Tool List
// ============================================================

async function loadTools() {
    const data = await apiGet('/tools');
    if (!data) {
        dom.toolList.innerHTML = '<div class="empty-state">加载失败</div>';
        return;
    }

    if (data.length === 0) {
        dom.toolList.innerHTML = '<div class="empty-state">无已注册工具</div>';
        return;
    }

    dom.toolList.innerHTML = '';
    for (const tool of data) {
        const el = document.createElement('div');
        el.className = 'tool-item';
        el.innerHTML = `
            <span class="tool-icon">🔧</span>
            <div class="tool-info">
                <div class="tool-name">${escapeHtml(tool.name)}</div>
                <div class="tool-desc">${escapeHtml(tool.description)}</div>
            </div>
            <span class="tool-badge ${tool.danger_level}">${tool.danger_level}</span>
        `;
        dom.toolList.appendChild(el);
    }
}

// ============================================================
// Sessions
// ============================================================

async function loadSessions() {
    const data = await apiGet('/sessions');
    if (!data || !data.sessions || data.sessions.length === 0) {
        dom.sessionList.innerHTML = '<div class="empty-state">无保存的会话</div>';
        return;
    }

    dom.sessionList.innerHTML = '';
    for (const session of data.sessions) {
        const el = document.createElement('div');
        el.className = 'session-item';
        el.innerHTML = `
            <span class="session-id">${escapeHtml(session.session_id)}</span>
            <span class="session-meta">${session.created_at} · ${session.message_count} 条消息</span>
        `;
        el.addEventListener('click', async () => {
            const result = await apiPost(`/sessions/${session.session_id}/load`);
            if (result && result.success) {
                // Reload chat history
                loadHistory();
                // Close sidebar on mobile
                dom.sidebar.classList.add('collapsed');
            }
        });
        dom.sessionList.appendChild(el);
    }
}

async function loadHistory() {
    const data = await apiGet('/history');
    if (!data) return;

    // Clear existing messages
    dom.chatMessages.innerHTML = '';
    if (data.count === 0) {
        // Re-add welcome
        const welcome = createWelcomeMessage();
        dom.chatMessages.appendChild(welcome);
        return;
    }

    for (const msg of data.messages) {
        if (msg.role === 'user') {
            const el = createUserMessage(msg.content || '');
            dom.chatMessages.appendChild(el);
        } else if (msg.role === 'assistant') {
            const el = document.createElement('div');
            el.className = 'message assistant';
            el.innerHTML = `
                <div class="message-avatar">🏹</div>
                <div class="message-content">
                    <div class="message-role">助手</div>
                    <div class="message-body">${simpleMarkdown(msg.content || '')}</div>
                </div>
            `;
            dom.chatMessages.appendChild(el);
        } else if (msg.role === 'tool') {
            // Skip tool messages for now
        }
    }

    scrollToBottom();
}

function createWelcomeMessage() {
    const el = document.createElement('div');
    el.className = 'welcome-message';
    el.id = 'welcomeMessage';
    el.innerHTML = `
        <div class="welcome-icon">🏹</div>
        <h2>欢迎使用 Zclaw</h2>
        <p>Claude Code 风格 AI 编程助手</p>
        <div class="welcome-hints">
            <div class="hint-card"><span class="hint-icon">💬</span><span>直接输入你的问题或指令</span></div>
            <div class="hint-card"><span class="hint-icon">📁</span><span>使用左侧文件浏览器浏览项目</span></div>
            <div class="hint-card"><span class="hint-icon">🔧</span><span>查看已注册的工具列表</span></div>
        </div>
    `;
    return el;
}

// ============================================================
// Event Bindings
// ============================================================

function bindEvents() {
    // Chat input
    dom.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    dom.chatInput.addEventListener('input', autoResizeInput);

    // Send/Cancel buttons
    dom.btnSend.addEventListener('click', sendMessage);
    dom.btnCancel.addEventListener('click', cancelGeneration);

    // Permission buttons
    dom.permAllow.addEventListener('click', () => respondPermission(true));
    dom.permDeny.addEventListener('click', () => respondPermission(false));

    // Sidebar toggle
    $('#btnToggleSidebar').addEventListener('click', () => {
        dom.sidebar.classList.toggle('collapsed');
    });

    // Clear history
    $('#btnClearHistory').addEventListener('click', async () => {
        if (state.generating) return;
        await apiPost('/clear');
        dom.chatMessages.innerHTML = '';
        dom.chatMessages.appendChild(createWelcomeMessage());
        dom.tokenInfo.textContent = '';
    });

    // Settings
    $('#btnSettings').addEventListener('click', () => {
        loadConfig();
        dom.settingsModal.classList.remove('hidden');
    });

    $('#settingsModalClose').addEventListener('click', () => {
        dom.settingsModal.classList.add('hidden');
    });

    // File viewer
    $('#fileViewerClose').addEventListener('click', () => {
        dom.fileViewerModal.classList.add('hidden');
    });

    // Close modals on overlay click
    dom.fileViewerModal.addEventListener('click', (e) => {
        if (e.target === dom.fileViewerModal) {
            dom.fileViewerModal.classList.add('hidden');
        }
    });

    dom.settingsModal.addEventListener('click', (e) => {
        if (e.target === dom.settingsModal) {
            dom.settingsModal.classList.add('hidden');
        }
    });

    // Close modals on Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            dom.fileViewerModal.classList.add('hidden');
            dom.settingsModal.classList.add('hidden');
            dom.permissionDialog.classList.add('hidden');
        }
    });

    // Sidebar tabs
    $$('.sidebar-tab').forEach((tab) => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;

            $$('.sidebar-tab').forEach((t) => t.classList.remove('active'));
            tab.classList.add('active');

            $$('.sidebar-panel').forEach((p) => p.classList.remove('active'));
            $(`#panel-${targetTab}`).classList.add('active');

            // Load data on tab switch
            if (targetTab === 'sessions') {
                loadSessions();
            }
        });
    });

    // File navigation
    $('#btnRefreshFiles').addEventListener('click', () => loadFiles(state.currentFilePath));
    $('#btnGoUp').addEventListener('click', () => {
        const parent = state.currentFilePath.split('/').slice(0, -1).join('/') || '.';
        loadFiles(parent);
    });

    $('#btnRefreshSessions').addEventListener('click', loadSessions);
}

// ============================================================
// Initialization
// ============================================================

function init() {
    bindEvents();
    connectWebSocket();
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
