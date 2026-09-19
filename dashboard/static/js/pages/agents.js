/* Agents page (/agents): per-agent tier assignment table (ia framework).
   Rows show the effective tier (override > default), the resolved model and
   a drift marker when an override diverges from the agent default. */

function renderAgentTiersTable() {
  const atbody = document.getElementById('tier-agents-tbody');
  if (!atbody) return;
  const tiers = STATE.tiers || {};
  const agents = (STATE.agents || []).slice().sort(function (a, b) {
    return a.name < b.name ? -1 : 1;
  });
  if (!agents.length) {
    atbody.innerHTML = '<tr><td colspan="5" class="empty-state" style="padding:24px"><p>No agents discovered</p></td></tr>';
    return;
  }
  atbody.innerHTML = agents.map(function (a) {
    const drift = a.drift
      ? ' <span class="drift-badge drift">override</span>'
      : (a.override ? ' <span class="drift-badge ok">set</span>' : '');
    const model = a.model
      ? '<span class="mono text-muted text-xs">' + escapeHtml(a.model) + '</span>' + (a.model_active ? '' : ' <span class="drift-badge drift">needs key</span>')
      : '<span class="text-muted">—</span>';
    return '<tr>' +
      '<td><div class="agent-name">@' + escapeHtml(a.name) + drift + '</div>' +
      (a.source ? '<div class="agent-path mono">' + escapeHtml(a.source) + '</div>' : '') + '</td>' +
      '<td><span class="agent-desc">' + escapeHtml((a.description || '').slice(0, 120) || '—') + '</span>' +
      (a.default_tier ? '<div class="text-xs text-muted">default: ' + escapeHtml(a.default_tier) + '</div>' : '') +
      (a.recommended_model ? '<div class="text-xs text-muted">recommended: <span class="mono">' + escapeHtml(a.recommended_model) + '</span></div>' : '') + '</td>' +
      '<td><select id="tier-agent-tier-' + escapeAttr(a.name) + '" style="background:var(--bg-base);color:var(--text-primary);border:1px solid var(--border-default);border-radius:var(--radius-sm);padding:6px 10px;font-size:12px;font-family:var(--font-sans);cursor:pointer;width:100%;max-width:200px;">' +
      '<option value="">— default —</option>' + tierOptionHtml(tiers, a.override || '') + '</select></td>' +
      '<td>' + model + (a.steps ? '<div class="text-xs text-muted mt-1">max steps: <span class="mono">' + a.steps + '</span></div>' : '') + '</td>' +
      '<td class="flex gap-2 flex-wrap">' +
      '<button class="btn btn-primary btn-sm" onclick="saveAgentTier(\'' + escapeAttr(a.name) + '\')">Save</button>' +
      '<button class="btn btn-secondary btn-sm" onclick="resetAgentTier(\'' + escapeAttr(a.name) + '\')">Reset</button>' +
      '</td></tr>';
  }).join('');
}

async function saveAgentTier(name) {
  const sel = document.getElementById('tier-agent-tier-' + name);
  if (!sel.value) { toast('Select a tier first', 'error'); return; }
  try {
    const r = await apiPut('/agents/' + encodeURIComponent(name), { tier: sel.value });
    if (!r.ok) { toast(r.detail || 'Save failed', 'error'); return; }
    toast('@' + name + ' → ' + r.tier, 'success');
    await loadDashboard();
  } catch (e) { toast(e.message, 'error'); }
}

async function resetAgentTier(name) {
  try {
    const r = await apiPost('/agents/' + encodeURIComponent(name) + '/reset');
    if (!r.ok) { toast(r.detail || 'Reset failed', 'error'); return; }
    toast('@' + name + ' reset' + (r.tier ? ' → ' + r.tier : ' to default'), 'success');
    await loadDashboard();
  } catch (e) { toast(e.message, 'error'); }
}

registerPageLoader(loadDashboard);
