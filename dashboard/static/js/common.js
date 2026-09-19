/* Shared helpers for every dashboard page: API wrappers, toasts, modal,
   sidebar/clock chrome, global status pill polling, refresh-all.
   Extracted verbatim (or trivially guarded) from the former inline <script>
   block of static/index.html. */
const API = '/api';
let STATE = { orchestrator: null, agents: [], catalog: [], tiers: {} };

async function apiGet(path) {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), 30000);
  try {
    const r = await fetch(`${API}${path}`, { signal: ctrl.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  } finally { clearTimeout(tid); }
}
async function apiPost(path, body = {}) {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), 60000);
  try {
    const r = await fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctrl.signal });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    return data;
  } finally { clearTimeout(tid); }
}
async function apiPut(path, body = {}) {
  const r = await fetch(`${API}${path}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}
async function apiDelete(path) {
  const r = await fetch(`${API}${path}`, { method: 'DELETE' });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}

function toast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = {
    success: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    error: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    warning: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  };
  el.innerHTML = `${icons[type] || icons.info}`;
  const span = document.createElement('span');
  span.textContent = message;
  el.appendChild(span);
  container.appendChild(el);
  setTimeout(() => { el.style.animation = 'toastOut 250ms ease-out forwards'; setTimeout(() => el.remove(), 250); }, 3000);
}

function showModal(title, body, onConfirm) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = body;
  document.getElementById('modal-confirm-btn').onclick = () => { onConfirm(); closeModal(); };
  document.getElementById('confirm-modal').classList.add('open');
}
function closeModal() { document.getElementById('confirm-modal').classList.remove('open'); }

function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent = now.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  const toggle = document.querySelector('.sidebar-toggle');
  const isOpen = sidebar.classList.toggle('open');
  backdrop.classList.toggle('open', isOpen);
  if (toggle) toggle.setAttribute('aria-expanded', String(isOpen));
}

function escapeHtml(str) { const div = document.createElement('div'); div.textContent = str ?? ''; return div.innerHTML; }
function escapeAttr(str) { return (str ?? '').toString().replace(/'/g, '&#39;').replace(/"/g, '&quot;'); }

// ── page registration ────────────────────────────────────────────────────────
// Each pages/<page>.js registers its data loaders here; init() runs them all
// so Refresh and the initial load behave like the old single-page app.
const PAGE_LOADERS = [];
const PAGE_UNLOADERS = [];
function registerPageLoader(fn) { PAGE_LOADERS.push(fn); }
function registerPageUnloader(fn) { PAGE_UNLOADERS.push(fn); }

async function refreshAll() {
  await Promise.all(PAGE_LOADERS.map(fn => fn()));
  await pollStatus();
  toast('Dashboard refreshed', 'success');
}

// ── pipa adaptation: health pill reads pipa's /api/health ─────────────────
// (everything else in this file is verbatim ia_harness chrome: toasts,
// modal, sidebar, clock, tier helpers)
function updateStatusChrome(data) {
  let allOk = true;
  for (const [, info] of Object.entries(data)) if (!info.up) allOk = false;
  const dot = document.getElementById('global-status-dot');
  const txt = document.getElementById('global-status-text');
  if (dot) dot.className = `status-dot ${allOk ? 'online' : 'offline'}`;
  if (txt) txt.textContent = allOk ? 'All systems operational' : 'Some services down';
}

async function pollStatus() {
  try {
    const h = await apiGet('/health');
    const up = !!(h.gateway && h.ollama);
    const dot = document.getElementById('global-status-dot');
    const txt = document.getElementById('global-status-text');
    if (dot) dot.className = `status-dot ${up ? 'online' : 'offline'}`;
    if (txt) txt.textContent = up ? 'All systems operational' : 'Some services down';
  } catch (e) { console.error('status fetch failed', e); }
}

async function restartGateway() {
  showModal('Restart LiteLLM Gateway',
    '<p>The gateway will be restarted with the current configuration. Active sessions may be briefly interrupted.</p>',
    () => {
      const f = document.createElement('form');
      f.method = 'POST';
      f.action = '/api/services/gateway/restart';
      document.body.appendChild(f);
      f.submit();
    }
  );
}

// Shared /api/dashboard bootstrap loader. Pages override the two render
// hooks they own; missing hooks are skipped on pages without that markup.
async function loadDashboard() {
  try {
    const data = await apiGet('/dashboard');
    STATE = data;
    if (typeof renderTierModelsTable === 'function') renderTierModelsTable();
    if (typeof renderTierCatalogTable === 'function') renderTierCatalogTable();
    if (typeof renderAgentTiersTable === 'function') renderAgentTiersTable();
    if (typeof renderCatalog === 'function') renderCatalog();
  } catch (e) { console.error('dashboard fetch failed', e); toast('Failed to load dashboard: ' + e.message, 'error'); }
}

async function init() {
  updateClock();
  setInterval(updateClock, 1000);
  await Promise.all([pollStatus(), ...PAGE_LOADERS.map(fn => fn())]);
  setInterval(pollStatus, 5000);
  window.addEventListener('resize', () => {
    if (window.innerWidth > 900) {
      const sidebar = document.getElementById('sidebar');
      if (sidebar && sidebar.classList.contains('open')) toggleSidebar();
    }
  });
}
document.addEventListener('DOMContentLoaded', init);
window.addEventListener('beforeunload', () => { PAGE_UNLOADERS.forEach(fn => fn()); });

// ── shared across pages (extracted during D2 split) ──
function tierBadge(tier) {
  if (!tier) return '<span class="text-muted">—</span>';
  const colors = { lowest: '#6B7280', low: '#10B981', mid: '#3B82F6', high: '#F59E0B', xhigh: '#EF4444' };
  return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;color:#0b0e14;background:${colors[tier] || '#9CA3AF'}">${escapeHtml(tier)}</span>`;
}

function tierOptionHtml(tiers, current) {
  const order = (tiers.tier_order && tiers.tier_order.length) ? tiers.tier_order : TIER_ORDER;
  return order.map(t => `<option value="${escapeAttr(t)}" ${t === current ? 'selected' : ''}>${escapeHtml(t)}${tiers.tiers[t] && tiers.tiers[t].label ? ' — ' + escapeHtml(tiers.tiers[t].label) : ''}</option>`).join('');
}

function buildCatalogOptions(currentId) {
  const groups = {};
  for (const c of STATE.catalog || []) (groups[c.provider] = groups[c.provider] || []).push(c);
  return Object.entries(groups).map(([provider, items]) => {
    const label = providerBadge(provider).name;
    const opts = items.map(c => `<option value="${escapeAttr(c.id)}" ${c.id === currentId ? 'selected' : ''}>${escapeHtml(c.id)}${c.description ? ' — ' + escapeHtml(c.description.slice(0, 60)) : ''}</option>`).join('');
    return `<optgroup label="${escapeAttr(label)}">${opts}</optgroup>`;
  }).join('');
}

function providerBadge(provider) {
  if (provider === 'local-ollama' || provider === 'eldorado') return { name: provider, cls: 'local' };
  if (provider === 'openai') return { name: 'Azure (proxy)', cls: 'cloud' };
  if (provider === 'anthropic') return { name: 'Anthropic (direct)', cls: 'cloud' };
  if (provider === 'github-copilot') return { name: 'GitHub Copilot', cls: 'free' };
  return { name: provider, cls: 'cloud' };
}
