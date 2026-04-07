/**
 * ESG Chat 页面
 * 用户与 AI 进行对话，分析企业 ESG 表现
 */

import { api } from '../api.js';
import { store } from '../store.js';
import { createScoreCard } from '../components/score-card.js';
import { toastError } from '../components/toast.js';
import { getStorage, setStorage, removeStorage, formatDate } from '../utils.js';

let isLoading = false;
let cleanup = [];
let pageRoot = null;
let messagesContainer = null;
let inputEl = null;
let sendBtnEl = null;

const RECENT_QUERY_KEY = 'esg_recent_queries';
const PENDING_PROMPT_KEY = 'esg_pending_prompt';
const PENDING_PROMPT_AUTOSEND_KEY = 'esg_pending_prompt_autosend';
const HOT_QUESTIONS = [
  '特斯拉的环保政策评分是多少？',
  '苹果与微软的社会责任表现如何对比？',
  '最近 ESG 相关风险事件有哪些？',
  '微软最新的多样性报告释放了什么信号？',
];

export async function render(container) {
  pageRoot = container;
  container.innerHTML = buildHTML();
  setupEventListeners(container);
  renderQueryCockpit(container);
  await loadMessages();
  applyPendingPrompt();
}

export function destroy() {
  cleanup.forEach(fn => fn());
  cleanup = [];
  pageRoot = null;
  messagesContainer = null;
  inputEl = null;
  sendBtnEl = null;
  isLoading = false;
}

// ============================================
// HTML 构建
// ============================================

function buildHTML() {
  return `
    <div class="page-stack h-full">
      <section class="page-hero">
        <div>
          <h2>ESG 智能对话</h2>
          <p>围绕企业环境、社会与治理表现发问，快速得到分析、结论与评分摘要。</p>
        </div>
        <div class="text-sm text-[var(--text-secondary)]">支持连续提问与会话历史恢复</div>
      </section>

      <section class="query-interface-panel card" data-hover-glow="true">
        <div class="overview-section-head">
          <div>
            <div class="overview-section-head__kicker">Query Cockpit</div>
            <h2>输入问题，或从最近搜索继续</h2>
          </div>
          <p>把热门问题、复用查询和当前输入区合成一个更像智能工作台的对话入口。</p>
        </div>

        <div class="chat-query-grid">
          <div class="chat-query-feature">
            <div class="query-chip-group__title">热门问题</div>
            <div id="chat-hot-questions" class="query-chip-list"></div>
          </div>

          <div class="chat-query-history">
            <div class="query-history-panel__eyebrow">Recent Search</div>
            <div id="chat-recent-queries" class="query-history-list"></div>
          </div>
        </div>
      </section>

      <!-- 聊天区域 -->
      <div data-hover-glow="true" class="chat-stage flex-1 overflow-y-auto bg-[#0b1220] rounded-[22px] border border-[var(--bg-border)] p-5 lg:p-6 min-h-[520px]">
        <div id="messages-container" class="space-y-4 flex flex-col">
          <!-- 消息由 JS 动态插入 -->
        </div>
      </div>

      <!-- 输入区域 -->
      <div data-hover-glow="true" class="chat-composer bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-[22px] p-4">
        <div id="input-area" class="flex flex-col gap-3 md:flex-row">
          <textarea
            id="chat-input"
            class="flex-1 min-h-[108px] bg-[#1C2333] border border-[var(--bg-border)] rounded-2xl p-4 text-[#F0F4F8] resize-none focus:outline-none"
            placeholder="输入问题...（例如：分析特斯拉的ESG表现）"
            rows="4"
          ></textarea>
          <button
            id="send-btn"
            class="btn-primary px-6 py-3 w-full md:w-auto self-stretch md:self-end min-w-[92px]"
          >
            发送
          </button>
        </div>
        <div id="send-hint" class="text-xs text-[#64748B] mt-2">
          按 Shift+Enter 换行，Enter 发送
        </div>
      </div>

    </div>
  `;
}

// ============================================
// 事件监听
// ============================================

function setupEventListeners(container) {
  inputEl = container.querySelector('#chat-input');
  sendBtnEl = container.querySelector('#send-btn');
  messagesContainer = container.querySelector('#messages-container');
  const hotQuestionsEl = container.querySelector('#chat-hot-questions');
  const recentQueriesEl = container.querySelector('#chat-recent-queries');

  // 发送按钮
  sendBtnEl.addEventListener('click', () => sendMessage());

  // 回车发送 (Shift+Enter 换行)
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // 监听 store 消息变化
  const onStoreChange = (e) => {
    if (e.detail.key === 'chatMessages') {
      renderMessages(messagesContainer);
    }
  };

  store.addEventListener('change', onStoreChange);
  cleanup.push(() => store.removeEventListener('change', onStoreChange));

  const onPromptClick = (e) => {
    const button = e.target.closest('[data-prompt]');
    if (!button) return;
    inputEl.value = button.dataset.prompt || '';
    inputEl.focus();
  };

  const onRecentClick = (e) => {
    const button = e.target.closest('[data-recent-query]');
    if (!button) return;
    inputEl.value = button.dataset.recentQuery || '';
    inputEl.focus();
  };

  hotQuestionsEl.addEventListener('click', onPromptClick);
  recentQueriesEl.addEventListener('click', onRecentClick);
  cleanup.push(() => hotQuestionsEl.removeEventListener('click', onPromptClick));
  cleanup.push(() => recentQueriesEl.removeEventListener('click', onRecentClick));
}

function renderQueryCockpit(container) {
  const hotQuestionsEl = container.querySelector('#chat-hot-questions');
  const recentQueriesEl = container.querySelector('#chat-recent-queries');

  hotQuestionsEl.innerHTML = HOT_QUESTIONS.map((question) => `
    <button class="query-chip" type="button" data-prompt="${escapeHtml(question)}">
      ${escapeHtml(question)}
    </button>
  `).join('');

  renderRecentQueries(recentQueriesEl);
}

function renderRecentQueries(target) {
  if (!target) return;
  const items = getStorage(RECENT_QUERY_KEY, []);

  if (!items.length) {
    target.innerHTML = `
      <div class="query-history-empty">
        这里会显示你最近发起过的 ESG 对话和评分请求。
      </div>
    `;
    return;
  }

  target.innerHTML = items.map((item) => `
    <button class="query-history-item" type="button" data-recent-query="${escapeHtml(item.query)}">
      <div class="query-history-item__icon">${item.mode === 'score' ? '★' : '✓'}</div>
      <div class="query-history-item__body">
        <div class="query-history-item__title">${escapeHtml(item.query)}</div>
        <div class="query-history-item__meta">
          <span>${item.mode === 'score' ? '评分看板' : 'ESG 对话'}</span>
          <span>${escapeHtml(formatDate(item.createdAt, 'YYYY-MM-DD HH:mm'))}</span>
        </div>
      </div>
    </button>
  `).join('');
}

function applyPendingPrompt() {
  const pendingPrompt = getStorage(PENDING_PROMPT_KEY, '');
  const shouldAutoSend = getStorage(PENDING_PROMPT_AUTOSEND_KEY, false);

  if (!pendingPrompt || !inputEl) return;

  inputEl.value = pendingPrompt;
  removeStorage(PENDING_PROMPT_KEY);
  removeStorage(PENDING_PROMPT_AUTOSEND_KEY);

  if (shouldAutoSend) {
    window.setTimeout(() => {
      sendMessage();
    }, 120);
  } else {
    inputEl.focus();
  }
}

// ============================================
// 消息加载和渲染
// ============================================

async function loadMessages() {
  const container = messagesContainer;
  const messages = store.get('chatMessages') || [];

  if (messages.length === 0) {
    container.innerHTML = `
      <div class="flex items-center justify-center h-full text-center">
        <div>
          <div class="text-4xl mb-4">💬</div>
          <p class="text-[#94A3B8]">开始对话，分析企业ESG表现</p>
          <p class="text-xs text-[#64748B] mt-2">例如：分析苹果的环境政策、特斯拉的社会责任...</p>
        </div>
      </div>
    `;
  } else {
    renderMessages(container);
  }
}

function renderMessages(container) {
  const messages = store.get('chatMessages') || [];

  container.innerHTML = '';

  messages.forEach((msg) => {
    const msgEl = document.createElement('div');
    msgEl.className = `flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`;

    const contentEl = document.createElement('div');
    contentEl.className = `chat-bubble chat-bubble-${msg.role}`;

    contentEl.innerHTML = msg.content;

    msgEl.appendChild(contentEl);
    container.appendChild(msgEl);

    // 如果有 ESG 分数，在下方显示评分卡片
    if (msg.esg_scores) {
      const scoreEl = document.createElement('div');
      scoreEl.className = 'flex justify-start';
      scoreEl.innerHTML = createScoreCard(msg.esg_scores);
      container.appendChild(scoreEl);
    }

    // 添加动画类
    msgEl.classList.add(`message-${msg.role}`);
  });

  // 滚动到底部
  container.parentElement.scrollTop = container.parentElement.scrollHeight;
}

// ============================================
// 发送消息
// ============================================

async function sendMessage() {
  if (isLoading) return;

  const input = inputEl;
  const question = input.value.trim();

  if (!question) {
    toastError('请输入问题', '输入为空');
    return;
  }

  recordRecentQuery(question);
  renderRecentQueries(pageRoot?.querySelector('#chat-recent-queries'));

  // 添加用户消息
  store.addMessage({
    role: 'user',
    content: question,
  });

  input.value = '';
  input.focus();

  // 显示思考指示
  showThinking();

  isLoading = true;
  sendBtnEl.disabled = true;
  sendBtnEl.textContent = '思考中...';

  try {
    const sessionId = store.get('currentSession')?.id;
    const result = await api.agent.analyze(question, sessionId);

    // 添加 AI 回复
    store.addMessage({
      role: 'assistant',
      content: result.answer,
      esg_scores: result.esg_scores,
    });

    // 如果有置信度，可以显示
    if (result.confidence < 0.7) {
      toastError(
        `置信度较低 (${(result.confidence * 100).toFixed(0)}%)，结果可能不准确`,
        '置信度警告'
      );
    }

  } catch (error) {
    console.error('发送消息失败:', error);
    store.addMessage({
      role: 'assistant',
      content: `❌ 错误: ${error.message}`,
    });
  } finally {
    isLoading = false;
    sendBtnEl.disabled = false;
    sendBtnEl.textContent = '发送';
  }
}

function recordRecentQuery(query) {
  const items = (getStorage(RECENT_QUERY_KEY, []) || [])
    .filter((item) => item.query !== query);

  items.unshift({
    query,
    mode: 'chat',
    createdAt: new Date().toISOString(),
  });

  setStorage(RECENT_QUERY_KEY, items.slice(0, 6));
}

function showThinking() {
  const container = messagesContainer;
  const msgEl = document.createElement('div');
  msgEl.className = 'flex justify-start';
  msgEl.innerHTML = `
    <div class="chat-bubble chat-bubble-assistant">
      <span class="thinking-dot"></span>
      <span class="thinking-dot"></span>
      <span class="thinking-dot"></span>
    </div>
  `;
  container.appendChild(msgEl);
  container.parentElement.scrollTop = container.parentElement.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
