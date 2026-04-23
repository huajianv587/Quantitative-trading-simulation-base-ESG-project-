import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, getLocale, onLangChange } from '../i18n.js?v=8';

const SESSION_STORAGE_KEY = 'qt.chat.sessions.v2';
const QUICK_PROMPTS = [
  'Why is NVDA ranked highly in the current ESG stack?',
  'Compare ESG scores for MSFT vs AAPL vs GOOGL',
  'What factors are driving today\'s top alpha signals?',
  'Explain the current regime classification and its impact',
  'Which sectors have the best ESG momentum right now?',
  'What is the overfit risk of the current strategy?',
];

let _messages = [];
let _sessions = [];
let _activeSession = '';
let _streaming = false;
let _container = null;
let _disposeLang = null;

function c(key) {
  const copy = {
    en: {
      pageTitle: 'Research Chat',
      pageSub: 'ESG Alpha Agent / Multi-turn Analysis / Context-aware Reasoning',
      newSession: '+ New Session',
      sessions: 'SESSIONS',
      liveContext: 'LIVE CONTEXT',
      quickPrompts: 'QUICK PROMPTS',
      headerTitle: 'ESG Alpha Research Agent',
      headerMetaTail: 'Context-aware / Multi-turn',
      clear: 'Clear',
      online: 'ONLINE',
      inputPlaceholder: 'Ask about a stock, factor, sector, regime, or signal rationale... (Ctrl+Enter to send)',
      sendShortcut: 'Ctrl+Enter to send',
      send: 'Send',
      thinking: 'Thinking...',
      emptyTitle: 'Start a conversation',
      emptyText: 'Ask about stocks, signals, sectors, or strategy rationale.',
      welcome:
        'Hello. I can use the current portfolio, live dashboard state, and saved session history to answer research questions. Ask about a stock, a factor, the current regime, or a specific signal rationale.',
      noHistory: 'No prior messages in this session yet.',
      enterQuestion: 'Enter a question first',
      apiError: 'Analysis failed',
      newSessionReady: 'New session ready',
      historyUnavailable: 'History unavailable',
      contextUnavailable: 'Context unavailable',
      sessionId: 'Session',
      sources: 'SOURCES',
      contextUniverse: 'Universe',
      contextPortfolio: 'Portfolio',
      contextSignals: 'Signals',
      contextTopSignal: 'Top Signal',
      contextDataSource: 'Data Source',
      contextUpdatedAt: 'Updated',
      errorResponse: 'The backend did not return an answer. Please retry or inspect the service health.',
      errorBanner: 'The backend returned an error instead of an analysis result.',
    },
    zh: {
      pageTitle: '研究对话',
      pageSub: 'ESG Alpha 智能体 / 多轮分析 / 上下文感知推理',
      newSession: '+ 新建会话',
      sessions: '会话',
      liveContext: '实时上下文',
      quickPrompts: '快捷提问',
      headerTitle: 'ESG Alpha 研究智能体',
      headerMetaTail: '上下文感知 / 多轮',
      clear: '清空',
      online: '在线',
      inputPlaceholder: '可以询问个股、因子、板块、市场状态或信号逻辑……（Ctrl+Enter 发送）',
      sendShortcut: 'Ctrl+Enter 发送',
      send: '发送',
      thinking: '思考中…',
      emptyTitle: '开始一段研究对话',
      emptyText: '可以直接问股票、信号、板块或策略逻辑。',
      welcome:
        '你好。我会结合当前组合、实时控制台状态和已保存的会话历史来回答研究问题。你可以直接问个股、因子、当前市场状态，或某条信号为什么进入前排。',
      noHistory: '这个会话还没有历史消息。',
      enterQuestion: '请先输入问题',
      apiError: '分析失败',
      newSessionReady: '新会话已创建',
      historyUnavailable: '历史消息暂不可用',
      contextUnavailable: '上下文暂不可用',
      sessionId: '会话',
      sources: '来源',
      contextUniverse: '股票池',
      contextPortfolio: '组合',
      contextSignals: '活跃信号',
      contextTopSignal: '头号信号',
      contextDataSource: '数据源',
      contextUpdatedAt: '更新时间',
      errorResponse: '后端没有返回可用回答。请重试，或先检查服务状态。',
      errorBanner: '后端返回了错误，而不是可用分析结果。',
    },
  };
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return copy[lang][key] || copy.en[key] || key;
}

function readStoredSessions() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(SESSION_STORAGE_KEY) || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function saveStoredSessions() {
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(_sessions.slice(0, 10)));
}

function nowIso() {
  return new Date().toISOString();
}

function buildSessionId() {
  return 'chat-' + Date.now();
}

function buildShell() {
  return `
  <div class="page-header" style="margin-bottom:0">
    <div>
      <div class="page-header__title">${c('pageTitle')}</div>
      <div class="page-header__sub">${c('pageSub')}</div>
    </div>
    <div class="page-header__actions">
      <button class="btn btn-ghost btn-sm" id="btn-new-session">${c('newSession')}</button>
    </div>
  </div>

  <div class="chat-layout">
    <div class="chat-sidebar">
      <div class="chat-sidebar-label">${c('sessions')}</div>
      <div class="session-list" id="session-list"></div>

      <div class="chat-sidebar-label" style="margin-top:18px">${c('liveContext')}</div>
      <div style="display:flex;flex-direction:column;gap:0;background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:8px;overflow:hidden" id="chat-context">
        <div style="padding:12px;color:var(--text-dim);font-size:11px">${c('contextUnavailable')}</div>
      </div>

      <div class="chat-sidebar-label" style="margin-top:18px">${c('quickPrompts')}</div>
      <div id="quick-prompts" style="display:flex;flex-direction:column;gap:4px">
        ${QUICK_PROMPTS.map((prompt) => `<button class="quick-prompt-btn" data-prompt="${prompt.replace(/"/g, '&quot;')}">${prompt}</button>`).join('')}
      </div>
    </div>

    <div class="chat-main">
      <div class="chat-session-header">
        <div>
          <div style="font-family:var(--f-display);font-size:13px;font-weight:700;color:var(--text-primary)">${c('headerTitle')}</div>
          <div style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">${c('sessionId')}: <span id="active-session-id">${_activeSession || '-'}</span> / ${c('headerMetaTail')}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <div class="live-dot"></div>
          <span style="font-size:10px;color:var(--green);font-family:var(--f-mono)">${c('online')}</span>
          <button class="btn btn-ghost btn-sm" id="btn-clear-chat">${c('clear')}</button>
        </div>
      </div>

      <div class="chat-viewport" id="chat-body"></div>

      <div class="chat-input-bar">
        <textarea class="chat-textarea" id="chat-question" rows="3" placeholder="${c('inputPlaceholder')}"></textarea>
        <div class="chat-input-actions">
          <div style="display:flex;gap:6px;align-items:center">
            <input class="form-input" id="chat-session" value="${_activeSession || ''}" style="width:160px;height:26px;font-size:10px" placeholder="session id">
            <span style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">${c('sendShortcut')}</span>
          </div>
          <button class="btn btn-primary" id="send-btn" style="min-width:90px">▶ ${c('send')}</button>
        </div>
      </div>
    </div>
  </div>`;
}

export function render(container) {
  _container = container;
  _sessions = readStoredSessions();
  _messages = [];
  _activeSession = _sessions[0]?.id || '';
  container.innerHTML = buildShell();
  bindEvents(container);
  renderSessions(container);
  renderMessages(container);
  boot(container);
  _disposeLang?.();
  _disposeLang = onLangChange(() => {
    if (!_container?.isConnected) return;
    const question = _container.querySelector('#chat-question')?.value || '';
    _container.innerHTML = buildShell();
    bindEvents(_container);
    renderSessions(_container);
    renderMessages(_container);
    renderContext(_container);
    const questionEl = _container.querySelector('#chat-question');
    if (questionEl) questionEl.value = question;
  });
}

export function destroy() {
  _messages = [];
  _sessions = [];
  _streaming = false;
  _activeSession = '';
  _container = null;
  _disposeLang?.();
  _disposeLang = null;
}

async function boot(container) {
  try {
    if (!_activeSession) {
      await createSession();
    }
    await Promise.all([loadContext(container), loadHistory(container, _activeSession)]);
  } catch (error) {
    toast.error(c('historyUnavailable'), error.message || c('historyUnavailable'));
    loadWelcomeMessages();
    renderMessages(container);
  }
}

async function createSession() {
  const sessionId = buildSessionId();
  const userId = window.__ESG_USER_ID__ || 'user_123';
  await api.agent.newSession(sessionId, userId);
  _activeSession = sessionId;
  _sessions.unshift({
    id: sessionId,
    title: sessionId,
    preview: '',
    updated_at: nowIso(),
    msgs: 0,
  });
  saveStoredSessions();
}

function renderSessions(container) {
  const list = container.querySelector('#session-list');
  if (!list) return;
  if (!_sessions.length) {
    list.innerHTML = `<div style="padding:12px;color:var(--text-dim);font-size:11px">${c('noHistory')}</div>`;
    return;
  }
  list.innerHTML = _sessions.map((session) => {
    const timestamp = session.updated_at
      ? new Date(session.updated_at).toLocaleString(getLocale(), { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
      : '--';
    const preview = session.preview || c('noHistory');
    return `
      <div class="session-item${session.id === _activeSession ? ' active' : ''}" data-sid="${session.id}">
        <div class="session-item-top">
          <span class="session-item-title">${session.title}</span>
          <span class="session-item-ts">${timestamp}</span>
        </div>
        <div class="session-item-preview">${preview}</div>
        <span class="session-item-badge">${session.msgs || 0}</span>
      </div>`;
  }).join('');
  const sessionInput = container.querySelector('#chat-session');
  const activeLabel = container.querySelector('#active-session-id');
  if (sessionInput) sessionInput.value = _activeSession;
  if (activeLabel) activeLabel.textContent = _activeSession || '-';
}

async function loadHistory(container, sessionId) {
  if (!sessionId) {
    loadWelcomeMessages();
    renderMessages(container);
    return;
  }
  const response = await api.agent.history(sessionId, 30);
  const history = Array.isArray(response?.messages) ? response.messages : [];
  if (!history.length) {
    loadWelcomeMessages();
    renderMessages(container);
    return;
  }
  _messages = history.map((message) => ({
    role: message.role === 'assistant' ? 'assistant' : 'user',
    content: message.content || '',
    ts: message.created_at || message.ts || nowIso(),
    sources: message.sources || null,
    meta: message.meta || null,
  }));
  updateSessionRecord(sessionId);
  renderMessages(container);
  scrollChat(container);
}

async function loadContext(container) {
  try {
    const [overview, dashboard] = await Promise.all([
      api.platform.overview(),
      api.trading.dashboardState('auto'),
    ]);
    const topSignal = (overview?.top_signals || [])[0] || {};
    const contextItems = [
      { label: c('contextUniverse'), value: `${overview?.universe?.size || 0}`, color: 'var(--text-primary)' },
      { label: c('contextPortfolio'), value: `${(overview?.portfolio_preview?.positions || []).length}`, color: 'var(--green)' },
      { label: c('contextSignals'), value: `${(overview?.top_signals || []).length}`, color: 'var(--cyan)' },
      { label: c('contextTopSignal'), value: topSignal.symbol || '-', color: 'var(--green)' },
      { label: c('contextDataSource'), value: dashboard?.source || dashboard?.provider_status?.provider || 'unavailable', color: 'var(--text-secondary)' },
      { label: c('contextUpdatedAt'), value: dashboard?.generated_at ? new Date(dashboard.generated_at).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit' }) : '--', color: 'var(--text-dim)' },
    ];
    renderContext(container, contextItems);
  } catch (error) {
    renderContext(container, null, error.message || c('contextUnavailable'));
  }
}

function renderContext(container, items, errorMessage) {
  const body = container.querySelector('#chat-context');
  if (!body) return;
  if (!items?.length) {
    body.innerHTML = `<div style="padding:12px;color:var(--text-dim);font-size:11px">${errorMessage || c('contextUnavailable')}</div>`;
    return;
  }
  body.innerHTML = items.map((item) => `
    <div style="display:flex;justify-content:space-between;align-items:center;padding:7px 12px;border-bottom:1px solid rgba(255,255,255,0.03)">
      <span style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono);letter-spacing:0.06em">${item.label}</span>
      <span style="font-size:10px;font-family:var(--f-mono);color:${item.color || 'var(--text-primary)'}">${item.value}</span>
    </div>`).join('');
}

function loadWelcomeMessages() {
  _messages = [
    {
      role: 'assistant',
      ts: nowIso(),
      content: c('welcome'),
      meta: null,
      isWelcome: true,
    },
  ];
}

function bindEvents(container) {
  container.querySelector('#send-btn')?.addEventListener('click', () => sendQuestion(container));
  container.querySelector('#btn-clear-chat')?.addEventListener('click', () => {
    loadWelcomeMessages();
    renderMessages(container);
  });
  container.querySelector('#btn-new-session')?.addEventListener('click', async () => {
    try {
      await createSession();
      loadWelcomeMessages();
      renderSessions(container);
      renderMessages(container);
      toast.success(c('newSessionReady'), _activeSession);
    } catch (error) {
      toast.error(c('apiError'), error.message || c('apiError'));
    }
  });
  container.querySelector('#chat-question')?.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      sendQuestion(container);
    }
  });
  container.querySelector('#session-list')?.addEventListener('click', async (event) => {
    const item = event.target.closest('.session-item');
    if (!item) return;
    _activeSession = item.dataset.sid;
    renderSessions(container);
    try {
      await loadHistory(container, _activeSession);
    } catch (error) {
      loadWelcomeMessages();
      renderMessages(container);
      toast.error(c('historyUnavailable'), error.message || c('historyUnavailable'));
    }
  });
  container.querySelector('#quick-prompts')?.addEventListener('click', (event) => {
    const btn = event.target.closest('.quick-prompt-btn');
    if (!btn) return;
    const question = container.querySelector('#chat-question');
    if (!question) return;
    question.value = btn.dataset.prompt || '';
    question.focus();
  });
}

async function sendQuestion(container) {
  if (_streaming) return;
  const questionEl = container.querySelector('#chat-question');
  const sessionEl = container.querySelector('#chat-session');
  const sendBtn = container.querySelector('#send-btn');
  const question = (questionEl?.value || '').trim();
  if (!question) {
    toast.warning(c('enterQuestion'));
    return;
  }

  if (!_activeSession) {
    try {
      await createSession();
      renderSessions(container);
    } catch (error) {
      toast.error(c('apiError'), error.message || c('apiError'));
      return;
    }
  }

  const sessionId = (sessionEl?.value || _activeSession).trim() || _activeSession;
  _activeSession = sessionId;
  _messages.push({ role: 'user', content: question, ts: nowIso() });
  if (questionEl) questionEl.value = '';
  renderMessages(container);
  scrollChat(container);

  _streaming = true;
  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.textContent = c('thinking');
  }

  const streamId = 'stream-' + Date.now();
  _messages.push({ role: 'assistant', content: '', ts: nowIso(), streamId });
  renderMessages(container);
  scrollChat(container);

  try {
    const response = await api.agent.analyze({ question, session_id: sessionId });
    const answer = response.answer || response.analysis_summary || c('errorResponse');
    const index = _messages.findIndex((msg) => msg.streamId === streamId);
    if (index >= 0) {
      _messages[index] = {
        role: 'assistant',
        content: answer,
        meta: response.esg_scores || response.metadata || null,
        sources: response.sources || response.citations || null,
        ts: nowIso(),
      };
    }
    updateSessionRecord(sessionId, question);
    renderSessions(container);
    renderMessages(container);
    scrollChat(container);
  } catch (error) {
    const index = _messages.findIndex((msg) => msg.streamId === streamId);
    if (index >= 0) {
      _messages[index] = {
        role: 'assistant',
        content: c('errorBanner'),
        ts: nowIso(),
        isError: true,
        meta: { detail: error.message || c('apiError') },
      };
    }
    updateSessionRecord(sessionId, question);
    renderSessions(container);
    renderMessages(container);
    scrollChat(container);
    toast.error(c('apiError'), error.message || c('apiError'));
  } finally {
    _streaming = false;
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.textContent = '▶ ' + c('send');
    }
  }
}

function updateSessionRecord(sessionId, preview) {
  const firstUserPrompt = preview || _messages.find((msg) => msg.role === 'user')?.content || sessionId;
  const existing = _sessions.find((session) => session.id === sessionId);
  if (existing) {
    existing.preview = preview || existing.preview || '';
    existing.title = existing.title || firstUserPrompt.slice(0, 40);
    existing.updated_at = nowIso();
    existing.msgs = _messages.length;
  } else {
    _sessions.unshift({
      id: sessionId,
      title: firstUserPrompt.slice(0, 40),
      preview: preview || '',
      updated_at: nowIso(),
      msgs: _messages.length,
    });
  }
  _sessions = _sessions
    .sort((left, right) => new Date(right.updated_at || 0).getTime() - new Date(left.updated_at || 0).getTime())
    .slice(0, 10);
  saveStoredSessions();
}

function renderMessages(container) {
  const body = container.querySelector('#chat-body');
  if (!body) return;
  if (!_messages.length) {
    body.innerHTML = `
      <div class="empty-state">
        <div class="empty-state__icon">💬</div>
        <div class="empty-state__title">${c('emptyTitle')}</div>
        <div class="empty-state__text">${c('emptyText')}</div>
      </div>`;
    return;
  }
  body.innerHTML = _messages.map((message) => buildMessage(message)).join('');
}

function buildMessage(message) {
  const isUser = message.role === 'user';
  const time = new Date(message.ts).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit' });
  const isStreaming = !!message.streamId && !message.content;
  const metaHtml = message.meta && Object.keys(message.meta).length
    ? `
      <div class="chat-msg-meta">
        ${Object.entries(message.meta).slice(0, 6).map(([key, value]) => `
          <div class="chat-meta-chip"><span>${key}</span><strong>${value}</strong></div>`).join('')}
      </div>`
    : '';
  const sourcesHtml = Array.isArray(message.sources) && message.sources.length
    ? `
      <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
        ${message.sources.slice(0, 4).map((source) => `
          <span style="font-size:9px;padding:2px 7px;border-radius:3px;background:rgba(0,229,255,0.08);color:var(--cyan);font-family:var(--f-mono)">${source}</span>`).join('')}
      </div>`
    : '';
  return `
    <div class="chat-msg ${isUser ? 'user' : 'assistant'}${message.isError ? ' chat-msg--error' : ''}">
      <div class="chat-msg-avatar">${isUser ? 'YOU' : 'AI'}</div>
      <div class="chat-msg-bubble">
        <div class="chat-msg-content">${isStreaming ? '<span class="chat-stream">...</span>' : formatContent(message.content)}</div>
        ${metaHtml}
        ${sourcesHtml}
        <div class="chat-msg-time">${time}</div>
      </div>
    </div>`;
}

function formatContent(content) {
  const escaped = String(content || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escaped
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function scrollChat(container) {
  const body = container.querySelector('#chat-body');
  if (!body) return;
  body.scrollTop = body.scrollHeight;
}
