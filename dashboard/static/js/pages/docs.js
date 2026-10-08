/* Docs page (/docs): rules & skills browser + markdown viewer/editor. */
let DOCS = [];
let CURRENT_DOC = null;

function renderDocsList() {
  const list = document.getElementById('docs-list');
  if (!list) return;
  if (!DOCS.length) { renderEmpty(list, 'No docs found'); return; }
  // Null-prototype: root/group come from a directory scan, and a path named
  // "constructor/" would otherwise resolve to Object.prototype.constructor.
  const groups = Object.create(null);
  for (const d of DOCS) {
    if (!groups[d.root]) groups[d.root] = Object.create(null);
    if (!groups[d.root][d.group]) groups[d.root][d.group] = [];
    groups[d.root][d.group].push(d);
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
        html += `<button class="docs-list-item${active}" data-action="openDoc" data-arg="${escapeDataAttr(d.path)}">${escapeHtml(d.name)}</button>`;
      }
    }
  }
  list.innerHTML = html;
}

async function loadDocs() {
  try {
    DOCS = await apiGet('/docs');
  } catch (e) {
    // "No docs found" here is a false negative about the repo's own rules and
    // skills: the files exist, the request did not succeed.
    console.error('docs fetch failed', e);
    DOCS = [];
    renderError(document.getElementById('docs-list'), 'Could not load the rules & skills list', e.message);
    toast('Docs unavailable: ' + e.message, 'error');
    return;
  }
  renderDocsList();
}

async function openDoc(path) {
  try {
    const data = await apiGet(`/docs/content?path=${encodeURIComponent(path)}`);
    CURRENT_DOC = { path: data.path, content: data.content, editing: false };
    renderDocsList();
    renderDocViewer();
  } catch (e) {
    // The viewer keeps whatever it had; say why nothing changed.
    console.error('doc fetch failed', e);
    renderError(document.getElementById('docs-viewer-body'), 'Could not load ' + path, e.message);
    toast(e.message, 'error');
  }
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
  title.textContent = (CURRENT_DOC.path || '').split('/').pop();
  pathEl.textContent = CURRENT_DOC.path;
  if (CURRENT_DOC.editing) {
    actions.innerHTML = `
      <button class="btn btn-primary btn-sm" data-action="saveDoc">Save</button>
      <button class="btn btn-secondary btn-sm" data-action="cancelEditDoc">Cancel</button>
    `;
    body.innerHTML = `<textarea id="docs-editor" class="docs-editor mono"></textarea>`;
    document.getElementById('docs-editor').value = CURRENT_DOC.content || '';
  } else {
    actions.innerHTML = `<button class="btn btn-secondary btn-sm" data-action="editDoc">Edit</button>`;
    body.innerHTML = `<div class="docs-preview" id="docs-preview"></div>`;
    renderMarkdown(CURRENT_DOC.content || '', document.getElementById('docs-preview'));
  }
}

// ── markdown sanitizing ──────────────────────────────────────────────────────
// ALLOWLIST, not blocklist. The old version removed script/iframe/object/embed/
// link/meta, on* attributes and javascript: URLs, which left three live holes:
// <style> (a CSS beacon that fires on selector match), <form>/<button>/<input>
// (a rules file can render a credential-phishing form inside the viewer), and
// SVG/MathML foreign content (parsed once, re-serialized differently — mXSS).
// A blocklist only names what someone already thought of.
//
// So: parse, then REBUILD from known-safe parts. Every element is recreated
// with document.createElement in the HTML namespace, so nothing survives
// through a parser quirk — only tags on the list, only attributes on the list,
// only URLs that pass isSafeDocUrl. An element that is not allowed takes its
// children with it when it is in DOC_DROP_SUBTREE (script/style/form/…);
// anything else unknown is unwrapped, so its prose stays readable.
const DOC_SAFE_TAGS = new Set([
  'a', 'abbr', 'b', 'blockquote', 'br', 'caption', 'code', 'dd', 'del',
  'details', 'div', 'dl', 'dt', 'em', 'figcaption', 'figure', 'h1', 'h2',
  'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins', 'kbd', 'li', 'mark',
  'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strong', 'sub',
  'summary', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr',
  'u', 'ul', 'var', 'wbr'
]);
// Elements whose *content* goes too — unwrapping these would leak exactly what
// they exist to smuggle (script text, CSS, input controls, foreign content).
const DOC_DROP_SUBTREE = new Set([
  'applet', 'audio', 'base', 'basefont', 'button', 'canvas', 'dialog',
  'embed', 'fieldset', 'form', 'frame', 'frameset', 'head', 'html',
  'iframe', 'input', 'isindex', 'keygen', 'link', 'listing', 'math', 'meta',
  'noembed', 'noframes', 'noscript', 'object', 'optgroup', 'option',
  'output', 'param', 'plaintext', 'portal', 'progress', 'script', 'select',
  'source', 'style', 'svg', 'template', 'textarea', 'title', 'track',
  'video', 'xmp'
]);
const DOC_GLOBAL_ATTRS = new Set(['title', 'lang', 'dir']);
const DOC_TAG_ATTRS = {
  a: ['href', 'target', 'rel', 'name'],
  img: ['src', 'alt', 'width', 'height'],
  td: ['colspan', 'rowspan', 'headers', 'align'],
  th: ['colspan', 'rowspan', 'scope', 'align'],
  ol: ['start', 'reversed', 'type'],
  li: ['value', 'type'],
  table: ['align'],
  details: ['open'],
  del: ['cite', 'datetime'],
  ins: ['cite', 'datetime'],
  q: ['cite'],
  blockquote: ['cite']
};
const DOC_CLASS_TAGS = new Set(['code', 'pre', 'span', 'div']);
const DOC_URL_ATTRS = new Set(['href', 'src', 'cite']);
const DOC_ID_RE = /^[A-Za-z][\w.:-]*$/;
const DOC_CLASS_RE = /^[A-Za-z0-9 _-]{0,120}$/;

// Only these schemes, and only when they are the whole prefix of the value.
// Control characters and whitespace are stripped first because a browser
// ignores them inside a URL: "java&#9;script:x" is still a javascript: URL.
// A relative reference gets a character allowlist of its own — the HTML
// serializer does not escape < and > inside a quoted attribute value, so a
// relative href is kept boring: no quotes, no angle brackets, no backslash.
function isSafeDocUrl(raw) {
  const v = String(raw == null ? '' : raw).replace(/[\u0000-\u0020\u00a0\u2028\u2029]/g, '');
  if (!v || v.startsWith('//')) return false;
  if (/^[a-z][a-z0-9+.-]*:/i.test(v)) return /^(?:https?|mailto|tel):/i.test(v);
  return /^[#A-Za-z0-9._~!$&()*+,;=:@%/?-]*$/.test(v);
}

function sanitizeDocAttrs(el, node, tag) {
  for (const attr of Array.from(node.attributes)) {
    const name = attr.localName.toLowerCase();
    const allowed = DOC_TAG_ATTRS[tag] || [];
    const isClass = name === 'class' && DOC_CLASS_TAGS.has(tag);
    const isId = name === 'id';
    if (!DOC_GLOBAL_ATTRS.has(name) && !allowed.includes(name) && !isClass && !isId) continue;
    const value = attr.value;
    if (DOC_URL_ATTRS.has(name)) {
      if (!isSafeDocUrl(value)) continue;
      el.setAttribute(name, value);
    } else if (isId) {
      if (DOC_ID_RE.test(value)) el.setAttribute('id', value);
    } else if (isClass) {
      if (DOC_CLASS_RE.test(value)) el.setAttribute('class', value);
    } else if (name === 'target') {
      el.setAttribute('target', '_blank');
    } else {
      el.setAttribute(name, value);
    }
  }
  if (tag === 'a') {
    const href = el.getAttribute('href');
    if (href === null) el.setAttribute('href', '#'); // rejected URL → inert anchor
    if (el.getAttribute('target')) el.setAttribute('rel', 'noopener noreferrer');
  }
  if (tag === 'img') el.setAttribute('loading', 'lazy');
  return el;
}

function rebuildSafeNode(node, parent) {
  if (node.nodeType === Node.TEXT_NODE) {
    parent.appendChild(document.createTextNode(node.nodeValue));
    return;
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return; // comments, PIs, doctype
  const tag = node.localName.toLowerCase();
  if (DOC_DROP_SUBTREE.has(tag)) return;
  if (!DOC_SAFE_TAGS.has(tag)) {
    for (const child of Array.from(node.childNodes)) rebuildSafeNode(child, parent);
    return;
  }
  const el = sanitizeDocAttrs(document.createElement(tag), node, tag);
  if (tag === 'img' && !el.getAttribute('src')) return; // src was rejected
  for (const child of Array.from(node.childNodes)) rebuildSafeNode(child, el);
  parent.appendChild(el);
}

function sanitizeHtml(html) {
  const doc = new DOMParser().parseFromString(String(html ?? ''), 'text/html');
  const out = document.createElement('div');
  for (const child of Array.from(doc.body.childNodes)) rebuildSafeNode(child, out);
  return out.innerHTML;
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
  if (!CURRENT_DOC) return;
  CURRENT_DOC.editing = true;
  renderDocViewer();
}
function cancelEditDoc() {
  if (!CURRENT_DOC) return;
  CURRENT_DOC.editing = false;
  renderDocViewer();
}
async function saveDoc() {
  const textarea = document.getElementById('docs-editor');
  if (!CURRENT_DOC || !textarea) { toast('That document is no longer open — reopen it', 'error'); return; }
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
