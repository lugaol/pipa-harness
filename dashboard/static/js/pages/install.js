/* Install page (/install): staged component setup (ia framework).
   One job at a time — the backend refuses while a job runs. */
let installPollTimer = null;

async function loadInstallState() {
  const tbody = document.getElementById('install-stages-tbody');
  if (!tbody) return;
  const meta = {
    uv: 'Python package manager shim used by setup scripts',
    'py-deps': 'Python dependencies for the gateway and dashboard',
    ollama: 'Local model server (free-tier inference)',
    litellm: 'Model gateway binary on PATH',
    graphify: 'Codebase graph CLI for structural search',
    opencode: 'OpenCode agent runner',
    dsh: 'DeepSeek Harness browser UI',
    apps: 'GUI helpers (Obsidian, emdash) — skipped with --no-apps',
    verify: 'pipa doctor diagnostics — install is done when this is green',
  };
  try {
    const data = await apiGet('/install/state');
    tbody.innerHTML = (data.stages || []).map(function (s) {
      return '<tr>' +
        '<td><div class="agent-name mono">' + escapeHtml(s.slug) + '</div>' +
        '<div class="agent-path">' + escapeHtml(meta[s.slug] || '') + '</div></td>' +
        '<td class="agent-desc">' + escapeHtml(s.detail || '') + '</td>' +
        '<td>' + (s.ready ? '<span class="drift-badge ok">ready</span>' : '<span class="drift-badge">missing</span>') + '</td>' +
        '<td><button class="btn btn-secondary btn-sm" onclick="runInstallStage(\'' + escapeAttr(s.slug) + '\')">Run</button></td>' +
        '</tr>';
    }).join('');
  } catch (e) { console.error('install state fetch failed', e); }
}

async function runInstallStage(component) {
  try {
    const r = await apiPost('/install/run', { component: component });
    if (!r.ok) { toast(r.detail || r.error || 'Run failed', 'error'); return; }
    toast('Job started: install ' + component, 'success');
    pollInstallLog();
  } catch (e) { toast(e.message, 'error'); }
}

async function pollInstallLog() {
  const el = document.getElementById('job-log');
  if (!el) return;
  if (installPollTimer) clearTimeout(installPollTimer);
  try {
    const j = await apiGet('/install/log');
    el.textContent = (j.lines || []).join('\n') || '(empty)';
    el.scrollTop = el.scrollHeight;
    const label = document.getElementById('job-state');
    if (label) {
      label.textContent = j.running ? 'running: ' + (j.label || '') :
        (j.label ? 'last: ' + j.label + ' (exit ' + j.exit_code + ')' : 'no job yet');
    }
    if (j.running) installPollTimer = setTimeout(pollInstallLog, 1500);
    else loadInstallState();
  } catch (e) {
    el.textContent = '(log unavailable)';
  }
}

registerPageLoader(loadInstallState);
registerPageLoader(pollInstallLog);
