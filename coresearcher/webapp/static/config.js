import { escapeHtml, fetchJSON, initShell, putJSON, setStatus, truncate } from '/static/common.js';

const configEditor = document.getElementById('configEditor');
const configSummary = document.getElementById('configSummary');
const cronJobList = document.getElementById('cronJobList');
const statusEl = document.getElementById('configStatus');

await initShell('config');
await loadAll();

document.getElementById('reloadConfigBtn').onclick = loadAll;
document.getElementById('saveConfigBtn').onclick = saveConfig;

async function loadAll() {
  const [statePayload, configPayload, cronPayload] = await Promise.all([
    fetchJSON('/api/state'),
    fetchJSON('/api/config'),
    fetchJSON('/api/cron'),
  ]);
  configEditor.value = configPayload.content || '{}\n';
  renderSummary(statePayload);
  renderCron(cronPayload.jobs || []);
  setStatus(statusEl, '配置摘要与 cron 列表已刷新。', 'success');
}

async function saveConfig() {
  try {
    await putJSON('/api/config', { content: configEditor.value });
    setStatus(statusEl, '配置保存成功。', 'success');
    await loadAll();
  } catch (error) {
    setStatus(statusEl, `保存失败：${error.message}`, 'danger');
  }
}

function renderSummary(state) {
  const providers = state.config?.providers || {};
  const channels = Object.entries(state.config?.channels || {}).filter(([, cfg]) => cfg?.enabled).map(([name]) => name).join(', ') || 'none';
  const items = [
    ['默认 Provider', providers.default || 'unknown'],
    ['默认模型', providers.default_model || 'unknown'],
    ['已启用频道', channels],
    ['Workspace', state.workspace],
    ['Memory Dir', state.memory_dir],
    ['Session Dir', state.session_dir],
  ];
  configSummary.innerHTML = items.map(([key, value]) => `
    <div class="kv-card">
      <span class="key">${escapeHtml(key)}</span>
      <span class="value">${escapeHtml(truncate(String(value), 40))}</span>
    </div>
  `).join('');
}

function renderCron(jobs) {
  if (jobs.length === 0) {
    cronJobList.innerHTML = '<div class="empty-state"><strong>暂无定时任务</strong><div>可以通过 CLI 或 cron 工具添加任务。</div></div>';
    return;
  }
  cronJobList.innerHTML = jobs.map((job) => `
    <div class="list-item">
      <div class="list-item-title">
        <span>${escapeHtml(job.name)}</span>
        <span class="badge">${escapeHtml(job.schedule)}</span>
      </div>
      <div class="list-item-preview">${escapeHtml(truncate(job.payload?.message || JSON.stringify(job.payload || {}), 120))}</div>
    </div>
  `).join('');
}
