/* Tier Manager page (/tiers): tier -> model assignment table (ia framework). */

const TIER_ORDER = ['lowest', 'low', 'mid', 'high', 'xhigh'];

function renderTierModelsTable() {
  const tbody = document.getElementById('tier-tbody');
  if (!tbody) return;
  const tiers = STATE.tiers || {};
  const defined = Object.keys(tiers.tiers || {});
  const order = Array.from(new Set([].concat(tiers.tier_order || TIER_ORDER, defined)));
  const catalog = STATE.catalog || [];
  const byId = {};
  catalog.forEach(function (c) { byId[c.id] = c; });
  tbody.innerHTML = order.map(function (t) {
    const def = tiers.tiers[t] || {};
    const resolved = (tiers.resolved && tiers.resolved[t]) || '';
    const entry = byId[resolved];
    const opts = catalog.map(function (c) {
      return '<option value="' + escapeAttr(c.id) + '"' + (c.id === resolved ? ' selected' : '') + '>' +
        escapeHtml(c.id) + (c.name && c.name !== c.id ? ' — ' + escapeHtml(c.name) : '') + '</option>';
    }).join('');
    return '<tr>' +
      '<td><div class="agent-name">' + tierBadge(t) + ' <span class="ml-1">' + escapeHtml(def.label || t) + '</span></div>' +
      '<div class="agent-path mono text-muted">' + escapeHtml((def.description || '').slice(0, 90)) + '</div></td>' +
      '<td><select id="tier-model-' + escapeAttr(t) + '" style="background:var(--bg-base);color:var(--text-primary);border:1px solid var(--border-default);border-radius:var(--radius-sm);padding:6px 10px;font-size:12px;font-family:var(--font-sans);cursor:pointer;min-width:0;width:100%;max-width:300px;">' +
      '<option value="">— not set —</option>' + opts + '</select>' +
      '<div class="agent-path mono text-muted" style="margin-top:4px">current: ' +
      (resolved ? '<span class="mono">' + escapeHtml(resolved) + '</span>' + (entry ? ' · ' + escapeHtml(entry.name || '') : '') : '<span class="text-muted">none</span>') +
      '</div></td>' +
      '<td><input type="number" id="tier-steps-' + escapeAttr(t) + '" value="' + (def.max_steps != null ? def.max_steps : '') + '" min="1" style="width:80px;background:var(--bg-base);color:var(--text-primary);border:1px solid var(--border-default);border-radius:var(--radius-sm);padding:6px 8px;font-size:12px"></td>' +
      '</tr>';
  }).join('');
}

function renderTierCatalogTable() {
  const tbody = document.getElementById('tier-catalog-tbody');
  if (!tbody) return;
  const catalog = STATE.catalog || [];
  if (!catalog.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state" style="padding:24px"><p>Catalog unavailable — run a discovery from the Models page.</p></td></tr>';
    return;
  }
  const holders = {};
  const resolved = (STATE.tiers && STATE.tiers.resolved) || {};
  Object.entries(resolved).forEach(function (entry) {
    const t = entry[0], id = entry[1];
    (holders[id] = holders[id] || []).push(t);
  });
  tbody.innerHTML = catalog.map(function (c) {
    return '<tr>' +
      '<td><div class="mono text-xs">' + escapeHtml(c.id) + ((holders[c.id] || []).length ? ' <span class="drift-badge ok">tier</span>' : '') + '</div></td>' +
      '<td class="text-xs">' + escapeHtml(c.name || '') + '</td>' +
      '<td>' + ((holders[c.id] || []).map(tierBadge).join(' ') || '<span class="text-muted">—</span>') + '</td>' +
      '<td class="text-xs">' + escapeHtml(c.provider || '') + '</td>' +
      '</tr>';
  }).join('');
}

async function saveTierModels() {
  const tiers = STATE.tiers || {};
  const defined = Object.keys(tiers.tiers || {});
  const order = Array.from(new Set([].concat(tiers.tier_order || TIER_ORDER, defined)));
  const payload = {};
  for (const t of order) {
    const modelSel = document.getElementById('tier-model-' + t);
    const stepsEl = document.getElementById('tier-steps-' + t);
    if (!modelSel || !modelSel.value) { toast('Pick a model for the ' + t + ' tier', 'error'); return; }
    payload[t] = { model: modelSel.value };
    if (stepsEl && stepsEl.value) payload[t].max_steps = parseInt(stepsEl.value, 10);
  }
  try {
    const result = await apiPut('/tier-models', { tiers: payload });
    toast(result.detail || 'Tier models saved and gateway restarted', result.ok ? 'success' : 'error');
    if (result.ok && result.warnings && result.warnings.length) toast('Check: ' + result.warnings.join(' · '), 'warning');
    await loadDashboard();
  } catch (e) { toast(e.message, 'error'); }
}

async function rebuildTierConfig() {
  showModal('Rebuild gateway config + restart',
    '<p>Recomposes <code class="mono">models/.effective.yaml</code> from live discovery + tier assignments, then restarts the LiteLLM gateway.</p>',
    async function () {
      try {
        const r = await apiPost('/gateway/rebuild');
        toast(r.detail || (r.ok ? 'Rebuilt and restarted' : 'Rebuild may have failed'), r.ok ? 'success' : 'error');
        setTimeout(function () { loadDashboard(); }, 1500);
      } catch (e) { toast(e.message, 'error'); }
    }
  );
}

registerPageLoader(loadDashboard);
