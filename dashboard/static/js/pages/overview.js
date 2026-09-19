/* Status page (/): harness status grid + API Keys panel (ia framework). */
let ollamaStarting = false;

const STATUS_ICONS = {
  'litellm gateway': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>',
  'ollama': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/></svg>',
  'graphify': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>',
};

async function renderStatusGrid() {
  const grid = document.getElementById('status-grid');
  if (!grid) return;
  let data = {};
  try {
    data = await apiGet('/status');
  } catch (e) { console.error('status fetch failed', e); return; }
  grid.innerHTML = '';
  for (const [name, info] of Object.entries(data)) {
    const iconSvg = STATUS_ICONS[name] || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>';
    const card = document.createElement('div');
    card.className = 'status-card';
    let actionHtml = '';
    if (name === 'ollama' && !info.up) {
      actionHtml = ollamaStarting
        ? '<button class="btn btn-primary btn-sm" disabled>Starting…</button>'
        : '<button class="btn btn-primary btn-sm" onclick="startOllama()">Start</button>';
    }
    if (name === 'litellm gateway' && !info.up) {
      actionHtml = '<button class="btn btn-primary btn-sm" onclick="restartGateway()">Start</button>';
    }
    card.innerHTML =
      '<div class="status-card-icon ' + (info.up ? 'green' : 'red') + '">' + iconSvg + '</div>' +
      '<div class="status-card-body">' +
      '<div class="status-card-name">' + escapeHtml(name) + '</div>' +
      '<div class="status-card-detail">' + escapeHtml((info.detail || '').slice(0, 100)) + '</div>' +
      '</div>' +
      '<div class="status-card-dot ' + (info.up ? 'ok' : 'fail') + '"></div>' +
      actionHtml;
    grid.appendChild(card);
  }
  const lastCheck = document.getElementById('last-check');
  if (lastCheck) lastCheck.textContent = 'Last check: ' + new Date().toLocaleTimeString();
}

// ── API Keys panel ───────────────────────────────────────────────────────────

let envOpenKey = null;

async function renderEnvKeys() {
  try {
    const data = await apiGet('/env-keys');
    const grid = document.getElementById('keys-grid');
    if (!grid) return;
    const keys = data.keys || [];
    const groups = data.groups || ['Providers'];
    grid.innerHTML =
      '<div class="agents-table-wrapper"><table class="agents-table" style="width:100%">' +
      '<thead><tr><th>Setting</th><th>Value</th><th>Status</th><th>Action</th></tr></thead>' +
      '<tbody>' +
      groups.map(function (g) {
        const items = keys.filter(function (k) { return k.group === g; });
        if (!items.length) return '';
        return '<tr class="env-group-row"><td colspan="4">' + escapeHtml(g) + '</td></tr>' +
          items.map(envKeyRow).join('');
      }).join('') +
      '</tbody></table></div>';
  } catch (e) { console.error('env keys fetch failed', e); }
}

function envKeyStatus(k) {
  if (k.set && k.placeholder) return { text: 'Placeholder', cls: 'drift' };
  if (k.set) return { text: 'Set', cls: 'ok' };
  return { text: 'Not set', cls: '' };
}

function envKeyRow(k) {
  const status = envKeyStatus(k);
  const open = envOpenKey === k.key;
  const badge = '<span class="drift-badge ' + (status.cls === 'drift' ? 'drift' : status.cls === 'ok' ? 'ok' : '') + '">' + status.text + '</span>';
  const value = k.set
    ? '<span class="mono env-value text-muted" style="max-width:280px">' + escapeHtml(k.masked || '•••') + '</span>'
    : '<span class="text-muted">—</span>';
  const action = k.set
    ? '<button class="btn btn-secondary btn-sm" onclick="toggleEnvRow(\'' + escapeAttr(k.key) + '\')">Change</button>'
    : '<button class="btn btn-primary btn-sm" onclick="toggleEnvRow(\'' + escapeAttr(k.key) + '\')">Set</button>';
  const editRow = open ?
    '<tr class="env-edit-row" id="env-edit-row-' + escapeAttr(k.key) + '">' +
    '<td colspan="4"><div class="env-input-wrap">' +
    '<input id="envkey-' + escapeAttr(k.key) + '" type="password" placeholder="paste the real value">' +
    '<button class="btn btn-secondary btn-sm" type="button" onclick="toggleSecret(\'' + escapeAttr(k.key) + '\')" title="Show/hide"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>' +
    '<button class="btn btn-primary btn-sm" onclick="saveEnvKey(\'' + escapeAttr(k.key) + '\')">Save</button>' +
    '<button class="btn btn-secondary btn-sm" onclick="closeEnvRow()">Cancel</button>' +
    '</div></td></tr>' : '';
  return '<tr><td><div class="agent-name">' + escapeHtml(k.label) + '</div>' +
    '<div class="mono text-xs text-muted">' + escapeHtml(k.key) + (k.hint ? ' · ' + escapeHtml(k.hint) : '') + '</div></td>' +
    '<td>' + value + '</td><td>' + badge + '</td><td>' + action + '</td></tr>' + editRow;
}

function toggleEnvRow(key) {
  envOpenKey = envOpenKey === key ? null : key;
  renderEnvKeys();
  const input = document.getElementById('envkey-' + key);
  if (input) input.focus();
}

function closeEnvRow() {
  envOpenKey = null;
  renderEnvKeys();
}

function toggleSecret(key) {
  const input = document.getElementById('envkey-' + key);
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
}

async function saveEnvKey(key) {
  const input = document.getElementById('envkey-' + key);
  const value = (input.value || '').trim();
  if (!value) { toast('Enter a value first', 'error'); return; }
  try {
    const res = await apiPost('/env-keys', { key: key, value: value });
    if (res.restarted) {
      toast('Saved ' + key + ' and restarted the gateway to apply it', 'success');
    } else {
      toast('Saved ' + key + ', but the gateway restart failed (' + (res.restart_detail || 'see log') + ')', 'error');
    }
    envOpenKey = null;
    renderEnvKeys();
  } catch (e) { toast(e.message, 'error'); }
}

async function startOllama() {
  if (ollamaStarting) return;
  ollamaStarting = true;
  renderStatusGrid();
  try {
    const r = await apiPost('/ollama/start');
    toast(r.detail || (r.ok ? 'Ollama started' : 'Start failed'), r.ok ? 'success' : 'error');
  } catch (e) { toast(e.message, 'error'); }
  finally {
    ollamaStarting = false;
    renderStatusGrid();
  }
}

registerPageLoader(renderStatusGrid);
registerPageLoader(renderEnvKeys);

// Silent status refresh: re-render the grid every 15s while the tab is
// visible. renderStatusGrid never toasts — polls stay invisible.
let statusPollTimer = null;
registerPageLoader(function startStatusPoll() {
  if (statusPollTimer) return;
  statusPollTimer = setInterval(function () {
    if (!document.hidden) renderStatusGrid();
  }, 15000);
});
registerPageUnloader(function stopStatusPoll() {
  if (statusPollTimer) { clearInterval(statusPollTimer); statusPollTimer = null; }
});
document.addEventListener('visibilitychange', function () {
  if (!document.hidden) { renderStatusGrid(); renderEnvKeys(); }
});
