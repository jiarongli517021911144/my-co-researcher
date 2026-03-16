import {
  fetchJSON,
  initShell,
  renderMessageTimeline,
  renderSessionList,
  renderTraceEvent,
  setStatus,
  getStoredSessionId,
  setStoredSessionId,
} from '/static/common.js';

const state = {
  sessionId: getStoredSessionId(),
  sessions: [],
};

const listEl = document.getElementById('sessionList');
const filterEl = document.getElementById('sessionSearch');
const sessionIdInput = document.getElementById('sessionIdInput');
const chatInput = document.getElementById('chatInput');
const chatHistory = document.getElementById('chatHistory');
const traceStream = document.getElementById('traceStream');
const chatStatus = document.getElementById('chatStatus');
const currentSessionBadge = document.getElementById('currentSessionBadge');
const subagentActiveBadge = document.getElementById('subagentActiveBadge');
const subagentTotalBadge = document.getElementById('subagentTotalBadge');
const subagentCompletedBadge = document.getElementById('subagentCompletedBadge');

await initShell('chat');
sessionIdInput.value = state.sessionId;
currentSessionBadge.textContent = state.sessionId;
await loadSessions();
await loadSession(state.sessionId);

filterEl.addEventListener('input', () => renderSessions());
sessionIdInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') loadSession(sessionIdInput.value.trim() || state.sessionId);
});
chatInput.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
    event.preventDefault();
    sendMessage();
  }
});

document.getElementById('newSessionBtn').onclick = async () => {
  const newId = `web-${Date.now()}`;
  await loadSession(newId, true);
};
document.getElementById('loadSessionBtn').onclick = () => loadSession(sessionIdInput.value.trim() || state.sessionId);
document.getElementById('refreshChatBtn').onclick = () => loadSession(state.sessionId);
document.getElementById('sendBtn').onclick = sendMessage;
document.getElementById('clearTraceBtn').onclick = () => { traceStream.innerHTML = ''; resetSubagentBadges(); };

async function loadSessions() {
  const payload = await fetchJSON('/api/sessions?limit=50');
  state.sessions = payload.sessions || [];
  renderSessions();
}

function renderSessions() {
  const keyword = filterEl.value.trim().toLowerCase();
  const visible = state.sessions.filter((item) => item.session_id.toLowerCase().includes(keyword));
  renderSessionList(listEl, visible, state.sessionId, (sessionId) => loadSession(sessionId));
}

async function loadSession(sessionId, resetTrace = false) {
  state.sessionId = sessionId;
  setStoredSessionId(sessionId);
  sessionIdInput.value = sessionId;
  currentSessionBadge.textContent = sessionId;
  if (resetTrace) {
    traceStream.innerHTML = '';
    resetSubagentBadges();
  }
  setStatus(chatStatus, '正在加载会话...', 'info');
  try {
    const payload = await fetchJSON(`/api/session/${encodeURIComponent(sessionId)}?limit=100`);
    renderMessageTimeline(chatHistory, payload.messages || []);
    setStatus(chatStatus, `已加载 ${payload.total_count} 条消息，last_consolidated=${payload.last_consolidated}`, 'success');
    renderSessions();
  } catch (error) {
    chatHistory.innerHTML = '';
    setStatus(chatStatus, `加载失败：${error.message}`, 'danger');
  }
}

async function sendMessage() {
  const message = chatInput.value.trim();
  if (!message) {
    setStatus(chatStatus, '请输入消息内容。', 'warning');
    return;
  }
  state.sessionId = sessionIdInput.value.trim() || state.sessionId;
  setStoredSessionId(state.sessionId);
  currentSessionBadge.textContent = state.sessionId;
  chatInput.value = '';
  traceStream.innerHTML = '';
  resetSubagentBadges();
  setStatus(chatStatus, '正在连接 Agent 并等待实时事件...', 'info');

  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/chat`);
  ws.onopen = () => ws.send(JSON.stringify({ session_id: state.sessionId, message }));
  ws.onmessage = async (evt) => {
    const event = JSON.parse(evt.data);
    if (event.kind === 'done') {
      ws.close();
      await loadSessions();
      await loadSession(state.sessionId);
      setStatus(chatStatus, '执行完成。', 'success');
      return;
    }
    if (event.kind === 'error') {
      ws.close();
      setStatus(chatStatus, event.message || '执行失败。', 'danger');
      return;
    }
    if (event.kind === 'subagent_status') {
      updateSubagentBadges(event);
    }
    renderTraceEvent(traceStream, event);
  };
  ws.onerror = () => setStatus(chatStatus, 'WebSocket 连接失败。', 'danger');
}


function resetSubagentBadges() {
  subagentActiveBadge.textContent = 'active 0';
  subagentTotalBadge.textContent = 'total 0';
  subagentCompletedBadge.textContent = 'done 0';
}

function updateSubagentBadges(event) {
  subagentActiveBadge.textContent = `active ${event.active_count ?? 0}`;
  subagentTotalBadge.textContent = `total ${event.total_spawned ?? 0}`;
  subagentCompletedBadge.textContent = `done ${event.completed_count ?? 0}`;
}
