/* Docs page (/docs): rules & skills browser + markdown viewer/editor. */
let DOCS = [];
let CURRENT_DOC = null;

function renderDocsList() {
  const list = document.getElementById('docs-list');
  if (!list) return;
  if (!DOCS.length) { list.innerHTML = '<div class="empty-state"><p>No docs found</p></div>'; return; }
  const groups = {};
  for (const d of DOCS) {
    groups[d.root] = groups[d.root] || {};
    (groups[d.root][d.group] = groups[d.root][d.group] || []).push(d);
  }
  let html = '';
  const ROOT_LABELS = { agents: 'Entry File', rules: 'Rules', skills: 'Skills', project: 'Project overlay' };
  for (const root of Object.keys(groups).sort()) {
    html += `<div class="docs-root-label">${escapeHtml(ROOT_LABELS[root] || root)}</div>`;
    const byGroup = groups[root];
    for (const group of Object.keys(byGroup).sort()) {
      if (group !== root) html += `<div class="docs-group-label">${escapeHtml(group)}</div>`;
      for (const d of byGroup[group]) {
        const active = CURRENT_DOC && CURRENT_DOC.path === d.path ? ' active' : '';
        html += `<button class="docs-list-item${active}" onclick="openDoc('${escapeAttr(d.path)}')">${escapeHtml(d.name)}</button>`;
      }
    }
  }
  list.innerHTML = html;
}

async function loadDocs() {
  try {
    DOCS = await apiGet('/docs');
    renderDocsList();
  } catch (e) { console.error('docs fetch failed', e); }
}

async function openDoc(path) {
  try {
    const data = await apiGet(`/docs/content?path=${encodeURIComponent(path)}`);
    CURRENT_DOC = { path: data.path, content: data.content, editing: false };
    renderDocsList();
    renderDocViewer();
  } catch (e) { toast(e.message, 'error'); }
}

function renderDocViewer() {
  const title = document.getElementById('docs-viewer-title');
  const pathEl = document.getElementById('docs-viewer-path');
  const actions = document.getElementById('docs-viewer-actions');
  const body = document.getElementById('docs-viewer-body');
  if (!CURRENT_DOC) {
    title.textContent = 'Select a document';
    pathEl.textContent = '';
    actions.innerHTML = '';
    body.innerHTML = '<div class="empty-state"><p>Pick a rule or skill from the list on the left.</p></div>';
    return;
  }
  title.textContent = CURRENT_DOC.path.split('/').pop();
  pathEl.textContent = CURRENT_DOC.path;
  if (CURRENT_DOC.editing) {
    actions.innerHTML = `
      <button class="btn btn-primary btn-sm" onclick="saveDoc()">Save</button>
      <button class="btn btn-secondary btn-sm" onclick="cancelEditDoc()">Cancel</button>
    `;
    body.innerHTML = `<textarea id="docs-editor" class="docs-editor mono"></textarea>`;
    document.getElementById('docs-editor').value = CURRENT_DOC.content;
  } else {
    actions.innerHTML = `<button class="btn btn-secondary btn-sm" onclick="editDoc()">Edit</button>`;
    body.innerHTML = `<div class="docs-preview" id="docs-preview"></div>`;
    renderMarkdown(CURRENT_DOC.content, document.getElementById('docs-preview'));
  }
}

function sanitizeHtml(html) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  doc.querySelectorAll('script, iframe, object, embed, link, meta').forEach(n => n.remove());
  doc.querySelectorAll('*').forEach(n => {
    for (const attr of [...n.attributes]) {
      const name = attr.name.toLowerCase();
      if (name.startsWith('on') || /(javascript|vbscript):/i.test(attr.value)) n.removeAttribute(attr.name);
    }
  });
  return doc.body.innerHTML;
}

function renderMarkdown(md, container) {
  if (window.marked) {
    try { container.innerHTML = sanitizeHtml(window.marked.parse(md)); return; } catch (e) { /* fall through to plain text */ }
  }
  const pre = document.createElement('pre');
  pre.className = 'mono';
  pre.style.whiteSpace = 'pre-wrap';
  pre.textContent = md;
  container.innerHTML = '';
  container.appendChild(pre);
}

function editDoc() {
  CURRENT_DOC.editing = true;
  renderDocViewer();
}
function cancelEditDoc() {
  CURRENT_DOC.editing = false;
  renderDocViewer();
}
async function saveDoc() {
  const textarea = document.getElementById('docs-editor');
  const content = textarea.value;
  try {
    await apiPut('/docs/content', { path: CURRENT_DOC.path, content });
    CURRENT_DOC.content = content;
    CURRENT_DOC.editing = false;
    toast(`Saved ${CURRENT_DOC.path}`, 'success');
    renderDocViewer();
  } catch (e) { toast(e.message, 'error'); }
}

registerPageLoader(loadDocs);
