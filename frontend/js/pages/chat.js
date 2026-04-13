import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

const SESSIONS = [
  { id: 'session-001', title: 'NVDA ESG Deep-Dive', preview: 'Why is NVDA ranked #1…', ts: '10:24 AM', msgs: 6 },
  { id: 'session-002', title: 'Tech Sector Momentum', preview: 'Compare MSFT vs AAPL…', ts: 'Yesterday', msgs: 4 },
  { id: 'session-003', title: 'Portfolio Risk Review', preview: 'What factors explain…', ts: 'Yesterday', msgs: 9 },
  { id: 'session-004', title: 'ESG Scoring Changes', preview: 'How did governance…', ts: 'Mon', msgs: 3 },
];

const QUICK_PROMPTS = [
  'Why is NVDA ranked highly in the current ESG stack?',
  'Compare ESG scores for MSFT vs AAPL vs GOOGL',
  'What factors are driving today\'s top alpha signals?',
  'Explain the current regime classification and its impact',
  'Which sectors have the best ESG momentum right now?',
  'What is the overfit risk of the current strategy?',
];

const CONTEXT_ITEMS = [
  { label: 'Active Portfolio', value: 'ESG Multi-Factor', color: 'var(--green)' },
  { label: 'Regime', value: 'Bull Market', color: 'var(--amber)' },
  { label: 'P1 Signals', value: '24 active', color: 'var(--cyan)' },
  { label: 'Top Signal', value: 'NVDA +2.14σ', color: 'var(--green)' },
  { label: 'Universe', value: 'S&P 500 ESG', color: 'var(--text-secondary)' },
  { label: 'Last Update', value: '2 min ago', color: 'var(--text-dim)' },
];

let _messages = [];
let _activeSession = 'session-001';
let _streaming = false;

export function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  loadWelcomeMessages();
  renderMessages(container);
}

export function destroy() {
  _messages = [];
  _streaming = false;
}

/* ── Shell ── */
function buildShell() {
  return `
  <div class="page-header" style="margin-bottom:0">
    <div>
      <div class="page-header__title">Research Chat</div>
      <div class="page-header__sub">ESG Alpha Agent · Multi-turn Analysis · Context-Aware Reasoning</div>
    </div>
    <div class="page-header__actions">
      <button class="btn btn-ghost btn-sm" id="btn-new-session">+ New Session</button>
    </div>
  </div>

  <div class="chat-layout">
    <!-- LEFT: Sessions sidebar -->
    <div class="chat-sidebar">
      <div class="chat-sidebar-label">SESSIONS</div>
      <div class="session-list" id="session-list">
        ${SESSIONS.map(s => `
          <div class="session-item${s.id === _activeSession ? ' active' : ''}" data-sid="${s.id}">
            <div class="session-item-top">
              <span class="session-item-title">${s.title}</span>
              <span class="session-item-ts">${s.ts}</span>
            </div>
            <div class="session-item-preview">${s.preview}</div>
            <span class="session-item-badge">${s.msgs}</span>
          </div>`).join('')}
      </div>

      <!-- Context Panel -->
      <div class="chat-sidebar-label" style="margin-top:18px">LIVE CONTEXT</div>
      <div style="display:flex;flex-direction:column;gap:0;background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:8px;overflow:hidden">
        ${CONTEXT_ITEMS.map(c => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:7px 12px;border-bottom:1px solid rgba(255,255,255,0.03)">
            <span style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono);letter-spacing:0.06em">${c.label}</span>
            <span style="font-size:10px;font-family:var(--f-mono);color:${c.color}">${c.value}</span>
          </div>`).join('')}
      </div>

      <!-- Quick Prompts -->
      <div class="chat-sidebar-label" style="margin-top:18px">QUICK PROMPTS</div>
      <div id="quick-prompts" style="display:flex;flex-direction:column;gap:4px">
        ${QUICK_PROMPTS.map(p => `
          <button class="quick-prompt-btn" data-prompt="${p.replace(/"/g,'&quot;')}">${p}</button>
        `).join('')}
      </div>
    </div>

    <!-- CENTER: Chat -->
    <div class="chat-main">
      <!-- Session header -->
      <div class="chat-session-header">
        <div>
          <div style="font-family:var(--f-display);font-size:13px;font-weight:700;color:var(--text-primary)">ESG Alpha Research Agent</div>
          <div style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">Session: <span id="active-session-id">${_activeSession}</span> · Context-aware · Multi-turn</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <div class="live-dot"></div>
          <span style="font-size:10px;color:var(--green);font-family:var(--f-mono)">ONLINE</span>
          <button class="btn btn-ghost btn-sm" id="btn-clear-chat">Clear</button>
        </div>
      </div>

      <!-- Viewport -->
      <div class="chat-viewport" id="chat-body"></div>

      <!-- Input -->
      <div class="chat-input-bar">
        <textarea class="chat-textarea" id="chat-question" rows="3"
          placeholder="Ask about a stock, factor, sector, regime, or signal rationale… (Ctrl+Enter to send)"></textarea>
        <div class="chat-input-actions">
          <div style="display:flex;gap:6px;align-items:center">
            <input class="form-input" id="chat-session" value="${window.__ESG_USER_ID__ || 'user_123'}"
              style="width:130px;height:26px;font-size:10px" placeholder="Session ID">
            <span style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">Ctrl+↵ to send</span>
          </div>
          <button class="btn btn-primary" id="send-btn" style="min-width:90px">▶ Send</button>
        </div>
      </div>
    </div>
  </div>`;
}

function loadWelcomeMessages() {
  _messages = [
    {
      role: 'assistant', ts: new Date(Date.now() - 120000).toISOString(),
      content: 'Hello! I\'m your ESG Alpha Research Agent. I have access to your current portfolio, live P1/P2 model signals, ESG scores, and market regime data.\n\nYou can ask me about:\n• **Specific stocks** — ESG scores, factor exposures, signal rationale\n• **Portfolio analysis** — Risk attribution, factor breakdown\n• **Market regime** — Current state, impact on strategy\n• **Strategy insights** — Why certain trades are ranked highly\n\nWhat would you like to explore?',
      meta: null, isWelcome: true,
    }
  ];
}

/* ── Events ── */
function bindEvents(container) {
  container.querySelector('#send-btn').addEventListener('click', () => sendQuestion(container));
  container.querySelector('#btn-clear-chat').addEventListener('click', () => {
    loadWelcomeMessages();
    renderMessages(container);
  });
  container.querySelector('#btn-new-session').addEventListener('click', () => {
    _activeSession = 'session-new-' + Date.now();
    container.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
    loadWelcomeMessages();
    renderMessages(container);
    toast.info('New session started');
  });
  container.querySelector('#chat-question').addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      sendQuestion(container);
    }
  });

  // Session list
  container.querySelector('#session-list').addEventListener('click', e => {
    const item = e.target.closest('.session-item');
    if (!item) return;
    _activeSession = item.dataset.sid;
    container.querySelectorAll('.session-item').forEach(el => el.classList.toggle('active', el.dataset.sid === _activeSession));
    container.querySelector('#active-session-id').textContent = _activeSession;
    loadWelcomeMessages();
    renderMessages(container);
  });

  // Quick prompts
  container.querySelector('#quick-prompts').addEventListener('click', e => {
    const btn = e.target.closest('.quick-prompt-btn');
    if (!btn) return;
    container.querySelector('#chat-question').value = btn.dataset.prompt;
    container.querySelector('#chat-question').focus();
  });
}

/* ── Send ── */
async function sendQuestion(container) {
  if (_streaming) return;
  const questionEl = container.querySelector('#chat-question');
  const sessionEl  = container.querySelector('#chat-session');
  const sendBtn    = container.querySelector('#send-btn');
  const question   = questionEl.value.trim();
  if (!question) { toast.warning('Enter a question first'); return; }

  const sessionId = sessionEl.value.trim() || _activeSession;
  _messages.push({ role: 'user', content: question, ts: new Date().toISOString() });
  questionEl.value = '';
  renderMessages(container);
  scrollChat(container);

  _streaming = true;
  sendBtn.disabled = true; sendBtn.textContent = '● Thinking…';

  // Add a streaming placeholder
  const streamId = 'stream-' + Date.now();
  _messages.push({ role: 'assistant', content: '', ts: new Date().toISOString(), streamId });
  renderMessages(container);
  scrollChat(container);

  try {
    const response = await api.agent.analyze({ question, session_id: sessionId });
    const answer = response.answer || response.analysis_summary || 'No answer returned.';
    // Replace streaming placeholder
    const idx = _messages.findIndex(m => m.streamId === streamId);
    if (idx >= 0) {
      _messages[idx] = {
        role: 'assistant', content: answer,
        meta: response.esg_scores || response.metadata || null,
        sources: response.sources || response.citations || null,
        ts: new Date().toISOString(),
      };
    }
    renderMessages(container);
    scrollChat(container);
  } catch(err) {
    const idx = _messages.findIndex(m => m.streamId === streamId);
    if (idx >= 0) {
      _messages[idx] = {
        role: 'assistant',
        content: mockAgentResponse(question),
        ts: new Date().toISOString(),
        isMock: true,
      };
    }
    renderMessages(container);
    scrollChat(container);
    toast.error('API error', err.message + ' — showing mock response');
  } finally {
    _streaming = false;
    sendBtn.disabled = false; sendBtn.textContent = '▶ Send';
  }
}

function mockAgentResponse(question) {
  const q = question.toLowerCase();
  if (q.includes('nvda') || q.includes('nvidia')) {
    return `**NVDA — ESG Alpha Analysis**\n\nNVIDIA ranks #1 in our current ESG Multi-Factor stack for several reasons:\n\n**ESG Scores (as of latest update):**\n• Environmental: 78/100 — Renewable energy commitment, chip efficiency leadership\n• Social: 82/100 — Workforce diversity, community investment\n• Governance: 85/100 — Board independence, executive compensation alignment\n\n**Factor Exposures:**\n• Quality: +2.14σ (top decile)\n• Momentum: +1.87σ (12-month)\n• ESG Composite: +1.92σ\n\n**Signal Rationale:**\nThe Alpha Ranker assigned NVDA a composite score of 0.87 (max 1.0). Key drivers: accelerating AI infrastructure demand intersects with ESG efficiency narrative. Data center power efficiency metrics improved 31% YoY, boosting Environmental score.\n\n**Risk Flags:**\n⚠ Valuation (P/E 45x) creates mean-reversion risk at current levels\n⚠ Geopolitical exposure (Taiwan supply chain) flagged by GNN model`;
  }
  if (q.includes('regime') || q.includes('market')) {
    return `**Current Market Regime Analysis**\n\nThe Regime Detector (HMM 4-state) is currently classifying markets as **Bull Market** with 87% confidence.\n\n**Regime Characteristics:**\n• Trend: Upward, SPY +18.4% YTD\n• Volatility: VIX at 14.2 (Low regime)\n• Breadth: 72% of S&P 500 above 200MA\n\n**Strategy Implications:**\n• Momentum factor tilt increased: +40% weight\n• Position sizing: 1.2x normal (risk-on)\n• ESG Growth stocks outperforming ESG Value by 340bps\n\n**Transition Risk:**\n The model assigns 12% probability of regime shift to High-Vol within 30 days, based on options market signals and macro indicators.`;
  }
  if (q.includes('sector') || q.includes('esg momentum')) {
    return `**Sector ESG Momentum Rankings**\n\n| Sector | ESG Score | 3M Change | Alpha Score |\n|--------|-----------|-----------|-------------|\n| Technology | 76.2 | +3.1 | 0.84 |\n| Healthcare | 71.8 | +2.4 | 0.76 |\n| Industrials | 68.4 | +1.8 | 0.71 |\n| Consumer Disc | 65.1 | +0.9 | 0.64 |\n| Energy | 42.3 | -1.2 | 0.38 |\n\n**Leaders:** Technology sector leads on Environmental and Governance sub-scores. Clean energy transition investments boosted Industrials.\n\n**Laggards:** Traditional Energy sector continues to underperform on ESG metrics despite some improvement in emissions reporting.`;
  }
  return `**Research Analysis**\n\nBased on the current state of the ESG Multi-Factor portfolio and P1 Alpha Stack:\n\n**Key Findings:**\n• The Alpha Ranker has identified 24 active signals across 12 sectors\n• Top-decile ESG stocks are outperforming the benchmark by 280bps YTD\n• The Regime Detector classifies current conditions as **Bull Market** (87% confidence)\n\n**Recommendation:**\nContinue with current positioning. Monitor the ESG score update cycle (next: 5 days) for any material changes to top holdings.\n\n*This is a mock response. Connect the API for live analysis.*`;
}

/* ── Render ── */
function renderMessages(container) {
  const body = container.querySelector('#chat-body');
  if (!body) return;

  if (!_messages.length) {
    body.innerHTML = `
      <div class="empty-state">
        <div class="empty-state__icon">🤖</div>
        <div class="empty-state__title">Start a conversation</div>
        <div class="empty-state__text">Ask about stocks, signals, sectors, or strategy rationale.</div>
      </div>`;
    return;
  }

  body.innerHTML = _messages.map(msg => buildMessage(msg)).join('');
}

function buildMessage(msg) {
  const isUser = msg.role === 'user';
  const time = new Date(msg.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const isStreaming = !!msg.streamId && !msg.content;

  // Format markdown-lite (bold, tables, bullets)
  const formatted = formatContent(msg.content);

  const metaHtml = msg.meta && Object.keys(msg.meta).length ? `
    <div class="chat-msg-meta">
      ${Object.entries(msg.meta).slice(0,6).map(([k,v]) => `
        <div class="chat-meta-chip"><span>${k}</span><strong>${v}</strong></div>`).join('')}
    </div>` : '';

  const sourcesHtml = msg.sources?.length ? `
    <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
      ${msg.sources.slice(0,3).map(s => `
        <span style="font-size:9px;padding:2px 7px;border-radius:3px;background:rgba(0,229,255,0.08);color:var(--cyan);font-family:var(--f-mono)">${s}</span>
      `).join('')}
    </div>` : '';

  const mockBadge = msg.isMock ? `<span style="font-size:8px;color:var(--amber);font-family:var(--f-mono);margin-left:8px">MOCK</span>` : '';
  const welcomeBadge = msg.isWelcome ? `<span style="font-size:8px;color:var(--green);font-family:var(--f-mono);margin-left:8px;letter-spacing:0.08em">WELCOME</span>` : '';

  if (isUser) {
    return `
    <div class="chat-msg chat-msg--user">
      <div class="chat-msg-bubble chat-msg-bubble--user">
        <div class="chat-msg-content">${formatted}</div>
        <div class="chat-msg-time">${time}</div>
      </div>
      <div class="chat-msg-avatar chat-msg-avatar--user">YOU</div>
    </div>`;
  }

  return `
  <div class="chat-msg chat-msg--agent">
    <div class="chat-msg-avatar chat-msg-avatar--agent">AI</div>
    <div class="chat-msg-bubble chat-msg-bubble--agent">
      <div class="chat-msg-header">
        <span style="font-size:9px;font-family:var(--f-display);letter-spacing:0.12em;color:var(--green)">ESG ALPHA AGENT</span>
        ${mockBadge}${welcomeBadge}
        <span class="chat-msg-time">${time}</span>
      </div>
      ${isStreaming ? `
        <div class="chat-typing">
          <span></span><span></span><span></span>
        </div>` : `
        <div class="chat-msg-content">${formatted}</div>
        ${metaHtml}
        ${sourcesHtml}`}
    </div>
  </div>`;
}

function formatContent(text) {
  if (!text) return '';
  // Escape HTML
  let s = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  // Bold **text**
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong style="color:var(--text-primary)">$1</strong>');
  // Tables (| col | col |)
  if (s.includes('|')) {
    const lines = s.split('\n');
    let inTable = false;
    s = lines.map(line => {
      if (line.trim().startsWith('|')) {
        if (line.includes('---')) return inTable ? '' : '';
        if (!inTable) { inTable = true; return '<div class="chat-table-wrap"><table class="chat-table"><tbody><tr>' + line.split('|').filter(Boolean).map(c=>`<td>${c.trim()}</td>`).join('') + '</tr>'; }
        return '<tr>' + line.split('|').filter(Boolean).map(c=>`<td>${c.trim()}</td>`).join('') + '</tr>';
      }
      if (inTable) { inTable = false; return '</tbody></table></div>' + line; }
      return line;
    }).join('\n');
    if (inTable) s += '</tbody></table></div>';
  }
  // Bullet points
  s = s.replace(/^[•·]\s(.+)$/gm, '<div class="chat-bullet"><span class="chat-bullet-dot"></span><span>$1</span></div>');
  s = s.replace(/^⚠\s(.+)$/gm, '<div class="chat-bullet warn"><span>⚠</span><span>$1</span></div>');
  // Headers **H:**
  s = s.replace(/^\*\*(.+)\*\*$/gm, '<div class="chat-section-header">$1</div>');
  // Newlines
  s = s.replace(/\n\n/g, '</p><p class="chat-para">').replace(/\n/g, '<br>');
  return `<p class="chat-para">${s}</p>`;
}

function scrollChat(container) {
  const body = container.querySelector('#chat-body');
  if (body) requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
}
