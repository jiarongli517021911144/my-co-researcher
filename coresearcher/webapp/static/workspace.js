import { fetchJSON, initShell, putJSON, renderFileList, setStatus } from '/static/common.js';

const state = {
  files: [],
  currentFile: '',
};

const fileList = document.getElementById('fileList');
const fileFilterInput = document.getElementById('fileFilterInput');
const fileEditor = document.getElementById('fileEditor');
const pathInput = document.getElementById('pathInput');
const editorTitle = document.getElementById('editorTitle');
const editorMeta = document.getElementById('editorMeta');
const statusEl = document.getElementById('workspaceStatus');

await initShell('workspace');
await loadState();

fileFilterInput.addEventListener('input', renderFiles);
document.getElementById('refreshFilesBtn').onclick = loadState;
document.getElementById('openPathBtn').onclick = () => openPath(pathInput.value.trim());
document.getElementById('reloadFileBtn').onclick = () => state.currentFile && loadFile(state.currentFile);
document.getElementById('saveFileBtn').onclick = saveFile;
pathInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') openPath(pathInput.value.trim());
});

async function loadState() {
  const payload = await fetchJSON('/api/state');
  state.files = payload.workspace_files || [];
  if (!state.currentFile && state.files.length > 0) {
    state.currentFile = state.files[0];
    await loadFile(state.currentFile);
  }
  renderFiles();
}

function renderFiles() {
  renderFileList(fileList, state.files, state.currentFile, loadFile, fileFilterInput.value);
}

async function openPath(path) {
  if (!path) {
    setStatus(statusEl, '请输入要打开的相对路径。', 'warning');
    return;
  }
  state.currentFile = path;
  await loadFile(path, true);
  renderFiles();
}

async function loadFile(path, allowMissing = false) {
  state.currentFile = path;
  editorTitle.textContent = path;
  editorMeta.textContent = '正在读取文件内容...';
  try {
    const payload = await fetchJSON(`/api/file?path=${encodeURIComponent(path)}`);
    fileEditor.value = payload.content || '';
    editorMeta.textContent = '文件已加载，可以直接编辑并保存。';
    setStatus(statusEl, `已加载 ${path}`, 'success');
  } catch (error) {
    if (allowMissing && /file not found/i.test(error.message)) {
      fileEditor.value = '';
      editorMeta.textContent = '文件尚不存在；编辑后点击保存即可创建。';
      setStatus(statusEl, `将创建新文件：${path}`, 'warning');
    } else {
      setStatus(statusEl, `读取失败：${error.message}`, 'danger');
    }
  }
  renderFiles();
}

async function saveFile() {
  if (!state.currentFile) {
    setStatus(statusEl, '请先选择或输入文件路径。', 'warning');
    return;
  }
  try {
    await putJSON('/api/file', { path: state.currentFile, content: fileEditor.value });
    setStatus(statusEl, `保存成功：${state.currentFile}`, 'success');
    await loadState();
  } catch (error) {
    setStatus(statusEl, `保存失败：${error.message}`, 'danger');
  }
}
