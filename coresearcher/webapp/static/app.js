const state = {
  currentFile: null,
  sessionId: localStorage.getItem('coresearcher_session_id') || `web-${Date.now()}`,
};

const els = {
  fileList: document.getElementById('fileList'),
  fileEditor: document.getElementById('fileEditor'),
  currentFile: document.getElementById('currentFile'),
  configEditor: document.getElementById('configEditor'),
  workspaceMeta: document.getElementById('workspaceMeta'),
  memoryQuery: document.getElementById('memoryQuery'),
  memoryResults: document.getElementById('memoryResults'),
  chatHistory: document.getElementById('chatHistory'),
  traceStream: document.getElementById('traceStream'),
  chatInput: document.getElementById('chatInput'),
  sessionId: document.getElementById('sessionId'),
};

els.sessionId.value = state.sessionId;

async function fetchJSON(url, options={}) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function loadState() {
  const payload = await fetchJSON('/api/state');
  els.workspaceMeta.textContent = `workspace: ${payload.workspace}\nmemory: ${payload.memory_dir}`;
  renderFiles(payload.workspace_files);
  const configPayload = await fetchJSON('/api/config');
  els.configEditor.value = configPayload.content;
}

function renderFiles(files) {
  els.fileList.innerHTML = '';
  for (const path of files) {
    const div = document.createElement('div');
    div.className = 'file-item' + (state.currentFile === path ? ' active' : '');
    div.textContent = path;
    div.onclick = () => loadFile(path);
    els.fileList.appendChild(div);
  }
}

async function loadFile(path) {
  const payload = await fetchJSON(`/api/file?path=${encodeURIComponent(path)}`);
  state.currentFile = path;
  els.currentFile.textContent = path;
  els.fileEditor.value = payload.content;
  await loadState();
}

async function saveFile() {
  if (!state.currentFile) return;
  await fetchJSON('/api/file', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({path: state.currentFile, content: els.fileEditor.value}),
  });
}

async function saveConfig() {
  await fetchJSON('/api/config', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({content: els.configEditor.value}),
  });
  await loadState();
}

async function memorySearch() {
  const q = els.memoryQuery.value.trim();
  if (!q) return;
  const payload = await fetchJSON(`/api/memory-search?q=${encodeURIComponent(q)}`);
  els.memoryResults.textContent = JSON.stringify(payload.results, null, 2);
}

function appendChat(role, content) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.innerHTML = `<div class="role">${role}</div><div>${escapeHtml(content)}</div>`;
  els.chatHistory.appendChild(div);
  els.chatHistory.scrollTop = els.chatHistory.scrollHeight;
}

function appendTrace(event) {
  const div = document.createElement('div');
  div.className = 'trace-event';
  const kind = event.kind || 'event';
  div.innerHTML = `<div class="kind">${kind}</div><pre>${escapeHtml(JSON.stringify(event, null, 2))}</pre>`;
  els.traceStream.appendChild(div);
  els.traceStream.scrollTop = els.traceStream.scrollHeight;
}

async function loadSession() {
  state.sessionId = els.sessionId.value.trim() || state.sessionId;
  localStorage.setItem('coresearcher_session_id', state.sessionId);
  const payload = await fetchJSON(`/api/session/${encodeURIComponent(state.sessionId)}`);
  els.chatHistory.innerHTML = '';
  for (const msg of payload.messages) {
    if (msg.role === 'user' || msg.role === 'assistant') appendChat(msg.role, msg.content || '');
  }
}

async function sendMessage() {
  const message = els.chatInput.value.trim();
  if (!message) return;
  state.sessionId = els.sessionId.value.trim() || state.sessionId;
  localStorage.setItem('coresearcher_session_id', state.sessionId);
  appendChat('user', message);
  els.chatInput.value = '';
  els.traceStream.innerHTML = '';

  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/chat`);
  ws.onopen = () => ws.send(JSON.stringify({session_id: state.sessionId, message}));
  ws.onmessage = (evt) => {
    const event = JSON.parse(evt.data);
    if (event.kind === 'final_response') {
      appendChat('assistant', event.content || '');
    } else if (event.kind !== 'done') {
      appendTrace(event);
    }
    if (event.kind === 'done' || event.kind === 'error') {
      ws.close();
    }
  };
}

function escapeHtml(input) {
  return (input || '').replace(/[&<>]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[ch]));
}

document.getElementById('refreshStateBtn').onclick = loadState;
document.getElementById('saveFileBtn').onclick = saveFile;
document.getElementById('saveConfigBtn').onclick = saveConfig;
document.getElementById('memorySearchBtn').onclick = memorySearch;
document.getElementById('sendBtn').onclick = sendMessage;
document.getElementById('loadSessionBtn').onclick = loadSession;

loadState();
loadSession();
