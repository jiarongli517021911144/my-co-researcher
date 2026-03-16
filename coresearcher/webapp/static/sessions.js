import { fetchJSON, formatDateTime, initShell, renderMessageTimeline, renderSessionList } from '/static/common.js';

const state = {
  sessions: [],
  currentId: '',
};

const listEl = document.getElementById('sessionsList');
const filterEl = document.getElementById('sessionsFilterInput');
const statsEl = document.getElementById('sessionStats');
const messagesEl = document.getElementById('sessionMessages');
const titleEl = document.getElementById('sessionDetailTitle');
const metaEl = document.getElementById('sessionDetailMeta');

await initShell('sessions');
await loadSessions();

filterEl.addEventListener('input', renderSessions);
document.getElementById('refreshSessionsBtn').onclick = loadSessions;

async function loadSessions() {
  const payload = await fetchJSON('/api/sessions?limit=100');
  state.sessions = payload.sessions || [];
  if (!state.currentId && state.sessions[0]) {
    state.currentId = state.sessions[0].session_id;
  }
  renderSessions();
  if (state.currentId) {
    await loadSessionDetail(state.currentId);
  }
}

function renderSessions() {
  const keyword = filterEl.value.trim().toLowerCase();
  const visible = state.sessions.filter((item) => item.session_id.toLowerCase().includes(keyword));
  renderSessionList(listEl, visible, state.currentId, async (sessionId) => {
    state.currentId = sessionId;
    renderSessions();
    await loadSessionDetail(sessionId);
  });
}

async function loadSessionDetail(sessionId) {
  const payload = await fetchJSON(`/api/session/${encodeURIComponent(sessionId)}?limit=120`);
  const session = state.sessions.find((item) => item.session_id === sessionId);
  titleEl.textContent = sessionId;
  metaEl.textContent = session ? `最近更新：${formatDateTime(session.updated_at)} · 预览：${session.preview || '无'}` : '会话详情';
  statsEl.innerHTML = `
    <div class="kv-card"><span class="key">总消息数</span><span class="value">${payload.total_count}</span></div>
    <div class="kv-card"><span class="key">窗口起点</span><span class="value">${payload.start_index}</span></div>
    <div class="kv-card"><span class="key">last_consolidated</span><span class="value">${payload.last_consolidated}</span></div>
    <div class="kv-card"><span class="key">当前窗口</span><span class="value">${(payload.messages || []).length}</span></div>
  `;
  renderMessageTimeline(messagesEl, payload.messages || []);
}
