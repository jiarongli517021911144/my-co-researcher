import { escapeHtml, fetchJSON, initShell, renderMemoryEntries, setStatus } from '/static/common.js';

const searchInput = document.getElementById('memoryQueryInput');
const resultsEl = document.getElementById('memorySearchResults');
const statusEl = document.getElementById('memoryStatus');
const longTermEl = document.getElementById('longTermMemory');
const longTermStatus = document.getElementById('longTermStatus');
const recentMemoryList = document.getElementById('recentMemoryList');

await initShell('memory');
await Promise.all([loadLongTermMemory(), loadRecentMemory()]);

document.getElementById('memorySearchBtn').onclick = searchMemory;
searchInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') searchMemory();
});

async function searchMemory() {
  const query = searchInput.value.trim();
  if (!query) {
    setStatus(statusEl, '请输入检索关键词。', 'warning');
    return;
  }
  setStatus(statusEl, '正在搜索向量记忆...', 'info');
  try {
    const payload = await fetchJSON(`/api/memory-search?q=${encodeURIComponent(query)}&limit=8`);
    const results = payload.results || [];
    if (results.length === 0) {
      resultsEl.innerHTML = '<div class="empty-state"><strong>没有命中结果</strong><div>可以换个关键词再试试。</div></div>';
      setStatus(statusEl, '没有找到相关记忆。', 'warning');
      return;
    }
    resultsEl.innerHTML = results.map((item) => `
      <article class="card">
        <div class="card-top">
          <div>
            <h3>${escapeHtml(item.metadata?.session_key || 'memory result')}</h3>
            <div class="card-subtitle">score=${Number(item.score || 0).toFixed(3)} · distance=${Number(item.distance || 0).toFixed(3)}</div>
          </div>
          <span class="badge info">Vector</span>
        </div>
        <div class="content-block">${escapeHtml(item.text || '')}</div>
      </article>
    `).join('');
    setStatus(statusEl, `搜索完成，共 ${results.length} 条结果。`, 'success');
  } catch (error) {
    setStatus(statusEl, `搜索失败：${error.message}`, 'danger');
  }
}

async function loadLongTermMemory() {
  try {
    const payload = await fetchJSON('/api/file?path=MEMORY.md');
    longTermEl.textContent = payload.content || '(empty)';
    setStatus(longTermStatus, `已加载 MEMORY.md，长度 ${(payload.content || '').length} 字符。`, 'success');
  } catch (error) {
    longTermEl.textContent = '未找到 MEMORY.md';
    setStatus(longTermStatus, `读取失败：${error.message}`, 'warning');
  }
}

async function loadRecentMemory() {
  const payload = await fetchJSON('/api/memory-recent?days=7');
  renderMemoryEntries(recentMemoryList, payload.entries || []);
}
