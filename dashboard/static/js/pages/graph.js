/* Graph page (/graph): code-graph stats, search and rebuild (ia framework). */
let graphRefreshing = false;

async function loadGraphStats() {
  const el = document.getElementById('graph-stats');
  if (!el) return;
  try {
    const st = await apiGet('/graph/stats');
    el.innerHTML =
      '<div class="status-card"><div class="status-card-icon ' + (st.has_graph ? 'green' : 'red') + '">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg></div>' +
      '<div class="status-card-body"><div class="status-card-name">' + (st.has_graph ? st.nodes + ' nodes' : 'no graph yet') + '</div>' +
      '<div class="status-card-detail">' + escapeHtml(st.graph_path || st.root || '') + '</div></div>' +
      '<div class="status-card-dot ' + (st.has_graph ? 'ok' : 'fail') + '"></div></div>';
  } catch (e) {
    el.innerHTML = '<div class="empty-state"><p>Graph status unavailable.</p></div>';
  }
}

async function runGraphSearch() {
  const input = document.getElementById('graph-q');
  const out = document.getElementById('graph-results');
  const q = (input.value || '').trim();
  if (!q) { toast('Enter a symbol or query first', 'error'); return; }
  out.innerHTML = '<div class="empty-state"><p>Searching…</p></div>';
  try {
    const r = await apiGet('/graph/search?q=' + encodeURIComponent(q));
    let html = '';
    if (r.cli_out) html += '<pre class="editor">' + escapeHtml(r.cli_out) + '</pre>';
    if (r.cli_err) html += '<div class="flash error">' + escapeHtml(r.cli_err) + '</div>';
    if ((r.hits || []).length) {
      html += '<div class="agents-table-wrapper"><table class="agents-table"><thead><tr><th>Symbol</th><th>Detail</th><th>Score</th></tr></thead><tbody>' +
        r.hits.map(function (h) {
          return '<tr><td><div class="agent-name mono">' + escapeHtml(h.title) + '</div>' +
            (h.path ? '<div class="agent-path mono">' + escapeHtml(h.path) + '</div>' : '') + '</td>' +
            '<td class="agent-desc">' + escapeHtml(h.detail || '') + '</td>' +
            '<td class="mono text-xs">' + h.score + '</td></tr>';
        }).join('') + '</tbody></table></div>';
    } else if (!r.cli_out) {
      html += '<div class="empty-state"><p>No hits — try a class, method or symbol name.</p></div>';
    }
    out.innerHTML = html;
  } catch (e) { toast(e.message, 'error'); }
}

async function refreshGraph() {
  if (graphRefreshing) return;
  graphRefreshing = true;
  const btn = document.getElementById('graph-refresh-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Rebuilding…'; }
  toast('Rebuilding the code graph — can take a while on large trees', 'info');
  try {
    const r = await apiPost('/graph/refresh');
    toast(r.detail || (r.ok ? 'Graph rebuilt' : 'Rebuild failed'), r.ok ? 'success' : 'error');
    if (r.ok) loadGraphStats();
  } catch (e) { toast(e.message, 'error'); }
  finally {
    graphRefreshing = false;
    if (btn) { btn.disabled = false; btn.textContent = 'Rebuild graph'; }
  }
}

function wireGraphSearch() {
  const input = document.getElementById('graph-q');
  if (input) input.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') runGraphSearch();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', wireGraphSearch);
} else {
  wireGraphSearch();
}

registerPageLoader(loadGraphStats);
