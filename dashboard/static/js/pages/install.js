/* Install page (/install): staged component setup (ia framework).
   One job at a time — the backend refuses while a job runs. */
let installPollTimer = null;
let installLogFailures = 0;
const INSTALL_LOG_MAX_RETRIES = 3;

async function loadInstallState(opts) {
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
  let data;
  try {
    data = await apiGet('/install/state');
  } catch (e) {
    // An empty stage table reads as "nothing is installed and there is nothing
    // to install" — the truth is "could not ask".
    console.error('install state fetch failed', e);
    renderErrorRow(tbody, 4, 'Could not load install stages', e.message);
    if (!(opts && opts.silent)) toast('Install stages unavailable: ' + e.message, 'error');
    return;
  }
  const stages = data.stages || [];
  if (!stages.length) {
    renderEmptyRow(tbody, 4, 'No install stages reported', 'Run a discovery from the Providers page, then reload.');
    return;
  }
  tbody.innerHTML = stages.map(function (s) {
    return '<tr>' +
      '<td><div class="agent-name mono">' + escapeHtml(s.slug) + '</div>' +
      '<div class="agent-path">' + escapeHtml(meta[s.slug] || '') + '</div></td>' +
      '<td class="agent-desc">' + escapeHtml(s.detail || '') + '</td>' +
      '<td>' + (s.ready ? '<span class="drift-badge ok">ready</span>' : '<span class="drift-badge">missing</span>') + '</td>' +
      '<td>' + actionButton('runInstallStage', s.slug, 'Run', 'secondary') + '</td>' +
      '</tr>';
  }).join('');
}

async function runInstallStage(component) {
  try {
    const r = await apiPost('/install/run', { component: component });
    if (!r.ok) { toast(r.detail || r.error || 'Run failed', 'error'); return; }
    toast('Job started: install ' + component, 'success');
    pollInstallLog();
  } catch (e) { toast(e.message, 'error'); }
}

function setJobState(text) {
  const label = document.getElementById('job-state');
  if (label) label.textContent = text;
}

async function pollInstallLog() {
  const el = document.getElementById('job-log');
  if (!el) return;
  if (installPollTimer) clearTimeout(installPollTimer);
  try {
    const j = await apiGet('/install/log');
    installLogFailures = 0;
    el.textContent = (j.lines || []).join('\n') || '(empty)';
    el.scrollTop = el.scrollHeight;
    setJobState(j.running ? 'running: ' + (j.label || '') :
      (j.label ? 'last: ' + j.label + ' (exit ' + j.exit_code + ')' : 'no job yet'));
    if (j.running) installPollTimer = setTimeout(pollInstallLog, 1500);
    else loadInstallState({ silent: true });
  } catch (e) {
    // #job-state used to be left on its markup text ("no job yet") while the
    // log said "(log unavailable)" — so a failed probe looked like an idle
    // page. Both regions now report the failure and stay honest.
    console.error('install log fetch failed', e);
    installLogFailures += 1;
    const giveUp = installLogFailures >= INSTALL_LOG_MAX_RETRIES;
    el.textContent = '(log unavailable) ' + (e.message || String(e));
    setJobState(giveUp
      ? 'log unreachable after ' + installLogFailures + ' attempts'
      : 'log unreachable — retrying (' + installLogFailures + '/' + INSTALL_LOG_MAX_RETRIES + ')');
    if (!giveUp) installPollTimer = setTimeout(pollInstallLog, 1500);
    else toast('Install log unreachable: ' + (e.message || e), 'error');
  }
}

registerPageLoader(loadInstallState);
registerPageLoader(pollInstallLog);