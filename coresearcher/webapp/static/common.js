const PAGE_INFO = {
  dashboard: { path: '/', title: '概览' },
  chat: { path: '/chat', title: '对话' },
  workspace: { path: '/workspace', title: '工作区' },
  sessions: { path: '/sessions', title: '会话' },
  memory: { path: '/memory', title: '记忆' },
  config: { path: '/config', title: '配置' },
};

export async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  return text ? JSON.parse(text) : {};
}

export async function putJSON(url, payload) {
  return fetchJSON(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function escapeHtml(input = '') {
  return String(input).replace(/[&<>]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[ch]));
}

export function truncate(text = '', max = 140) {
  const compact = String(text).replace(/\s+/g, ' ').trim();
  if (compact.length <= max) return compact;
  return `${compact.slice(0, max - 1)}…`;
}

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

export function relativeTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const diff = Date.now() - date.getTime();
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diff < minute) return '刚刚';
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`;
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`;
  return `${Math.floor(diff / day)} 天前`;
}

export function getStoredSessionId() {
  return localStorage.getItem('coresearcher_session_id') || `web-${Date.now()}`;
}

export function setStoredSessionId(sessionId) {
  localStorage.setItem('coresearcher_session_id', sessionId);
}

export function setStatus(element, message = '', type = 'info') {
  if (!element) return;
  element.className = `status-line ${type === 'info' ? '' : type}`.trim();
  element.textContent = message;
}

export async function initShell(activePage) {
  const state = await fetchJSON('/api/state');
  document.querySelectorAll('.nav-link').forEach((link) => {
    link.classList.toggle('is-active', link.dataset.nav === activePage);
  });
  document.querySelectorAll('[data-shell-workspace]').forEach((el) => {
    el.textContent = state.workspace;
  });
  document.querySelectorAll('[data-shell-memory]').forEach((el) => {
    el.textContent = state.memory_dir;
  });
  document.querySelectorAll('[data-shell-provider]').forEach((el) => {
    const providers = state.config?.providers || {};
    el.textContent = `${providers.default || 'unknown'} / ${providers.default_model || 'unknown'}`;
  });
  document.querySelectorAll('[data-shell-channels]').forEach((el) => {
    const channels = Object.entries(state.config?.channels || {})
      .filter(([, cfg]) => cfg && cfg.enabled)
      .map(([name]) => name)
      .join(', ');
    el.textContent = channels || 'none';
  });
  document.title = `coresearcher · ${PAGE_INFO[activePage]?.title || '页面'}`;
  return state;
}

export function renderMessageTimeline(container, messages) {
  container.innerHTML = '';
  if (!messages || messages.length === 0) {
    container.appendChild(createEmptyState('暂无消息', '这个会话还没有可展示的消息记录。'));
    return;
  }
  for (const message of messages) {
    const card = document.createElement('article');
    const role = message.role || 'message';
    card.className = `message message-${role} ${role}`;

    const header = document.createElement('div');
    header.className = 'message-role';
    header.innerHTML = `<span class="badge ${role === 'user' ? 'info' : role === 'assistant' ? 'success' : 'warning'}">${escapeHtml(role)}</span>`;
    card.appendChild(header);

    const body = document.createElement('div');
    body.className = 'message-content';
    body.textContent = typeof message.content === 'string'
      ? message.content
      : JSON.stringify(message.content, null, 2);
    card.appendChild(body);

    if (message.tool_calls) {
      const extra = document.createElement('pre');
      extra.textContent = JSON.stringify(message.tool_calls, null, 2);
      card.appendChild(extra);
    }
    container.appendChild(card);
  }
}

export function renderTraceEvent(container, event) {
  const wrapper = document.createElement('article');
  wrapper.className = `trace-event trace-${String(event.kind || 'event').replace(/[^a-z0-9_-]+/gi, '-')}`;

  const title = document.createElement('div');
  title.className = 'trace-title';
  const kind = event.kind || 'event';
  title.innerHTML = `<strong>${escapeHtml(labelForTrace(kind))}</strong><span class="badge ${traceTone(kind)}">${escapeHtml(kind)}</span>`;
  wrapper.appendChild(title);

  const body = document.createElement('div');
  body.className = 'message-content';
  body.textContent = summarizeTrace(event);
  wrapper.appendChild(body);

  const detail = document.createElement('pre');
  detail.textContent = JSON.stringify(event, null, 2);
  wrapper.appendChild(detail);

  container.appendChild(wrapper);
  container.scrollTop = container.scrollHeight;
}

export function renderSessionList(container, sessions, activeId, onSelect) {
  container.innerHTML = '';
  if (!sessions || sessions.length === 0) {
    container.appendChild(createEmptyState('暂无会话', '当前 session 目录里还没有历史记录。'));
    return;
  }
  for (const session of sessions) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `list-item list-item-session clickable ${session.session_id === activeId ? 'is-active' : ''}`.trim();
    item.innerHTML = `
      <div class="list-item-title">
        <span>${escapeHtml(session.session_id)}</span>
        <span class="badge">${session.total_count} 条</span>
      </div>
      <div class="list-item-meta">${escapeHtml(relativeTime(session.updated_at))} · consolidated ${session.last_consolidated}</div>
      <div class="list-item-preview">${escapeHtml(session.preview || '无可用预览')}</div>
    `;
    item.onclick = () => onSelect(session.session_id);
    container.appendChild(item);
  }
}

export function renderFileList(container, files, activePath, onSelect, filterText = '') {
  container.innerHTML = '';
  const filtered = (files || []).filter((path) => path.toLowerCase().includes(filterText.trim().toLowerCase()));
  if (filtered.length === 0) {
    container.appendChild(createEmptyState('没有匹配文件', '可以清空筛选条件，或输入新的路径来创建文件。'));
    return;
  }
  for (const path of filtered) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `file-entry file-entry-archive clickable ${path === activePath ? 'is-active' : ''}`.trim();
    const parts = path.split('/');
    const name = parts.pop();
    const dir = parts.join('/') || 'workspace';
    item.innerHTML = `
      <span class="nav-icon">📄</span>
      <span>
        <span class="file-entry-path">${escapeHtml(name)}</span>
        <span class="file-entry-dir">${escapeHtml(dir)}</span>
      </span>
    `;
    item.onclick = () => onSelect(path);
    container.appendChild(item);
  }
}

export function createEmptyState(title, description) {
  const wrapper = document.createElement('div');
  wrapper.className = 'empty-state';
  wrapper.innerHTML = `<strong>${escapeHtml(title)}</strong><div>${escapeHtml(description)}</div>`;
  return wrapper;
}

export function renderMemoryEntries(container, entries) {
  container.innerHTML = '';
  if (!entries || entries.length === 0) {
    container.appendChild(createEmptyState('暂无日记忆', '目前还没有可展示的按天记忆文件。'));
    return;
  }
  for (const entry of entries) {
    const card = document.createElement('article');
    card.className = 'card';
    card.innerHTML = `
      <div class="card-top">
        <div>
          <h3>${escapeHtml(entry.date)}</h3>
          <div class="card-subtitle">${entry.line_count} 行记录</div>
        </div>
        <span class="badge">Daily Memory</span>
      </div>
      <div class="content-block">${escapeHtml(entry.content || '')}</div>
    `;
    container.appendChild(card);
  }
}

function summarizeTrace(event) {
  const kind = event.kind || 'event';
  if (kind === 'tool_call') return `调用工具 ${event.tool || ''}，参数已附在详情里。`;
  if (kind === 'tool_result') return `工具 ${event.tool || ''} 返回了结果。`;
  if (kind === 'reasoning') return truncate(event.content || '');
  if (kind === 'plan_generated') return '已生成执行计划。';
  if (kind === 'plan_batch') return `准备并行执行 ${event.parallelism || 0} 个步骤。`;
  if (kind === 'plan_step_finished') return `步骤 ${event.step_id || ''} 已完成，状态：${event.status || ''}`;
  if (kind === 'plan_replanned') return '计划已根据中间结果动态调整。';
  if (kind === 'reflexion_critic') return `Critic 评分 ${event.score ?? '-'}，通过=${event.passed}`;
  if (kind === 'final_response') return '最终回复已生成。';
  if (kind === 'subagent_status') return `Subagent 状态：active=${event.active_count ?? 0} / total=${event.total_spawned ?? 0} / completed=${event.completed_count ?? 0}`;
  return truncate(JSON.stringify(event), 140);
}

function labelForTrace(kind) {
  return {
    tool_call: '工具调用',
    tool_result: '工具结果',
    reasoning: '推理片段',
    plan_generated: '计划生成',
    plan_batch: '批次执行',
    plan_step_finished: '步骤完成',
    plan_replanned: '动态重规划',
    reflexion_critic: '反思评审',
    subagent_status: 'Subagent 状态',
    final_response: '最终回复',
  }[kind] || '事件';
}

function traceTone(kind) {
  if (['tool_call', 'plan_generated', 'plan_batch'].includes(kind)) return 'info';
  if (['tool_result', 'plan_step_finished', 'final_response'].includes(kind)) return 'success';
  if (['plan_replanned', 'reflexion_critic', 'subagent_status'].includes(kind)) return 'warning';
  return 'info';
}
