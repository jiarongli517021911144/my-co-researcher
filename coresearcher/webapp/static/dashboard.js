import { escapeHtml, fetchJSON, formatDateTime, initShell, truncate } from '/static/common.js';

const recentSessions = document.getElementById('recentSessions');
const recentMemory = document.getElementById('recentMemory');
const recentFiles = document.getElementById('recentFiles');
const cronJobs = document.getElementById('cronJobs');

const shellState = await initShell('dashboard');
const sessionsPayload = await fetchJSON('/api/sessions?limit=6');
const memoryPayload = await fetchJSON('/api/memory-recent?days=5');
const cronPayload = await fetchJSON('/api/cron');

const files = shellState.workspace_files || [];
const sessions = sessionsPayload.sessions || [];
const memoryEntries = memoryPayload.entries || [];
const jobs = cronPayload.jobs || [];

setStat('statFiles', files.length);
setStat('statSessions', sessions.length);
setStat('statMemories', memoryEntries.length);
setStat('statCron', jobs.length);

renderSummary(shellState, sessions, memoryEntries, jobs);
renderRecentSessions(sessions);
renderRecentMemory(memoryEntries);
renderRecentFiles(files);
renderCronJobs(jobs);

function setStat(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(value);
}

function renderRecentSessions(items) {
  if (items.length === 0) {
    recentSessions.innerHTML = '<div class="empty-state"><strong>暂无会话</strong><div>可以去对话页创建一条新的消息。</div></div>';
    return;
  }
  recentSessions.innerHTML = items.map((item) => `
    <a class="list-item" href="/sessions">
      <div class="list-item-title"><span>${escapeHtml(item.session_id)}</span><span class="badge">${item.total_count} 条</span></div>
      <div class="list-item-meta">${formatDateTime(item.updated_at)}</div>
      <div class="list-item-preview">${escapeHtml(truncate(item.preview || '无预览'))}</div>
    </a>
  `).join('');
}

function renderRecentMemory(items) {
  if (items.length === 0) {
    recentMemory.innerHTML = '<div class="empty-state"><strong>暂无日记忆</strong><div>当历史消息被压缩到 memory 目录后，这里会出现内容。</div></div>';
    return;
  }
  recentMemory.innerHTML = items.map((entry) => `
    <a class="list-item" href="/memory">
      <div class="list-item-title"><span>${escapeHtml(entry.date)}</span><span class="badge">${entry.line_count} 行</span></div>
      <div class="list-item-preview">${escapeHtml(truncate(entry.preview || ''))}</div>
    </a>
  `).join('');
}

function renderRecentFiles(items) {
  const top = items.slice(0, 8);
  recentFiles.innerHTML = top.map((path) => `
    <a class="list-item" href="/workspace">
      <div class="list-item-title"><span>${escapeHtml(path.split('/').pop())}</span></div>
      <div class="list-item-meta">${escapeHtml(path)}</div>
    </a>
  `).join('') || '<div class="empty-state"><strong>暂无文件</strong></div>';
}

function renderCronJobs(items) {
  if (items.length === 0) {
    cronJobs.innerHTML = '<div class="empty-state"><strong>暂无任务</strong><div>可以用 CLI 或 cron 工具添加任务。</div></div>';
    return;
  }
  cronJobs.innerHTML = items.map((job) => `
    <div class="list-item">
      <div class="list-item-title"><span>${escapeHtml(job.name)}</span><span class="badge">${escapeHtml(job.schedule)}</span></div>
      <div class="list-item-preview">${escapeHtml(truncate(job.payload?.message || JSON.stringify(job.payload || {}), 90))}</div>
    </div>
  `).join('');
}
