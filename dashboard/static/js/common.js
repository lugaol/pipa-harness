/* Shared helpers for every dashboard page: API wrappers, toasts, modal,
   sidebar/clock chrome, global status pill polling.
   Extracted verbatim (or trivially guarded) from the former inline <script>
   block of static/index.html. */
const API = '/api';
const READ_TIMEOUT_MS = 30000;
const WRITE_TIMEOUT_MS = 60000;
let STATE = { orchestrator: null, agents: [], catalog: [], tiers: {} };

// Every request is bounded by an AbortController, so a hung PUT fails like any
// other error instead of leaving a spinner up with no way out. Without this a
// stalled /api/tier-models froze the Tier Manager permanently.
function timedFetch(path, init, timeoutMs) {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), timeoutMs);
  const opts = Object.assign({}, init, { signal: ctrl.signal });
  return fetch(`${API}${path}`, opts)
    .catch((e) => {
      if (e && e.name === 'AbortError') throw new Error(`timed out after ${Math.round(timeoutMs / 1000)}s`);
      throw e;
    })
    .finally(() => clearTimeout(tid));
}
const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function apiGet(path) {
  const r = await timedFetch(path, { method: 'GET' }, READ_TIMEOUT_MS);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
async function apiPost(path, body = {}) {
  const r = await timedFetch(path, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }, WRITE_TIMEOUT_MS);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}
// Writes get the write budget, not the read budget: a tier save restarts the
// gateway on success, so 30s would abort a request that was about to work.
async function apiPut(path, body = {}) {
  const r = await timedFetch(path, { method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify(body) }, WRITE_TIMEOUT_MS);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}

function toast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  // Toasts are the only feedback channel on most panels, so they have to be
  // announced. Set from JS (base.html owns the markup) on first use: the
  // container is a polite live region and errors interrupt it.
  if (!container.hasAttribute('aria-live')) {
    container.setAttribute('role', 'status');
    container.setAttribute('aria-live', 'polite');
    container.setAttribute('aria-relevant', 'additions');
  }
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  if (type === 'error') el.setAttribute('role', 'alert');
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

const MODAL_FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
let MODAL_LAST_FOCUS = null;

// `body` is escaped unless the caller opts in with { html: true }. Both callers
// pass literals today, so the raw innerHTML was latent — but an interpolated
// value reaching this function is how a data field becomes markup.
function showModal(title, body, onConfirm, opts) {
  const modal = document.getElementById('confirm-modal');
  const bodyEl = document.getElementById('modal-body');
  const confirmBtn = document.getElementById('modal-confirm-btn');
  if (!modal || !bodyEl || !confirmBtn) return;
  const titleEl = document.getElementById('modal-title');
  if (titleEl) titleEl.textContent = title;
  if (opts && opts.html) bodyEl.innerHTML = body == null ? '' : String(body);
  else bodyEl.textContent = body == null ? '' : String(body);
  MODAL_LAST_FOCUS = document.activeElement;
  // Close first, then run the action: a synchronous throw in onConfirm used to
  // wedge the dialog open with no way out.
  confirmBtn.onclick = () => {
    closeModal();
    try { if (typeof onConfirm === 'function') onConfirm(); }
    catch (e) { console.error('modal action failed', e); toast(e.message || String(e), 'error'); }
  };
  modal.classList.add('open');
  // base.html ships the overlay unlabelled; role/aria-modal are added here so
  // the dialog is announced as one and focus stays inside it.
  if (!modal.hasAttribute('role')) {
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    if (titleEl && titleEl.id) modal.setAttribute('aria-labelledby', titleEl.id);
  }
  const first = bodyEl.querySelector(MODAL_FOCUSABLE) || confirmBtn;
  first.focus();
}
function closeModal() {
  const modal = document.getElementById('confirm-modal');
  if (modal) modal.classList.remove('open');
  const back = MODAL_LAST_FOCUS;
  MODAL_LAST_FOCUS = null;
  if (back && typeof back.focus === 'function' && document.contains(back)) back.focus();
}
function modalFocusables(modal) {
  return Array.from(modal.querySelectorAll(MODAL_FOCUSABLE))
    .filter((el) => !el.disabled && el.getClientRects().length);
}
document.addEventListener('keydown', (ev) => {
  const modal = document.getElementById('confirm-modal');
  if (!modal || !modal.classList.contains('open')) return;
  if (ev.key === 'Escape') { ev.preventDefault(); closeModal(); return; }
  if (ev.key !== 'Tab') return;
  const items = modalFocusables(modal);
  if (!items.length) return;
  const first = items[0], last = items[items.length - 1];
  const active = document.activeElement;
  if (ev.shiftKey && (active === first || !modal.contains(active))) { ev.preventDefault(); last.focus(); }
  else if (!ev.shiftKey && (active === last || !modal.contains(active))) { ev.preventDefault(); first.focus(); }
});

function updateClock() {
  const el = document.getElementById('clock');
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  const toggle = document.querySelector('.sidebar-toggle');
  // Missing chrome must not throw: an exception here escapes an inline
  // onclick handler and leaves the overlay half-open.
  if (!sidebar || !backdrop) return;
  const isOpen = sidebar.classList.toggle('open');
  backdrop.classList.toggle('open', isOpen);
  if (toggle) toggle.setAttribute('aria-expanded', String(isOpen));
}

function escapeHtml(str) { const div = document.createElement('div'); div.textContent = str ?? ''; return div.innerHTML; }
function escapeAttr(str) { return (str ?? '').toString().replace(/'/g, '&#39;').replace(/"/g, '&quot;'); }

// Values passed to data-arg are entity-decoded by the browser before dataset
// reads them, so escape the entities fully: `"` cannot terminate the attribute
// and the handler receives the original string. This replaces building an
// inline JS call out of user data (HTML-decoded before evaluation).
function escapeDataAttr(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// The inline-action button appears across several pages. One builder, so the
// escaping and the class names cannot drift apart per page.
function actionButton(fn, arg, label, variant, extra) {
  const cls = 'btn btn-' + (variant || 'primary') + ' btn-sm';
  const dataArg = (arg === undefined || arg === null) ? ''
    : ' data-arg="' + escapeDataAttr(arg) + '"';
  return '<button class="' + cls + '"' + (extra ? ' ' + extra : '') +
    ' data-action="' + escapeDataAttr(fn) + '"' + dataArg + '>' + label + '</button>';
}

// Every panel must be able to say "could not load" instead of rendering empty:
// an empty grid reads as "you have no keys", which is the opposite of the truth.
function errorStateHtml(message, detail) {
  return '<div class="flash error">' + escapeHtml(message) +
    (detail ? ' <span class="text-muted">' + escapeHtml(detail) + '</span>' : '') + '</div>';
}
function renderError(el, message, detail) { if (el) el.innerHTML = errorStateHtml(message, detail); }
// The other half of the pair — a region that genuinely has nothing, stated
// explicitly so it cannot be mistaken for the failed-load state above.
function renderEmpty(el, message, detail) {
  if (!el) return;
  el.innerHTML = '<div class="empty-state"><p>' + escapeHtml(message) +
    (detail ? '<br><span class="text-xs">' + escapeHtml(detail) + '</span>' : '') + '</p></div>';
}
// <tbody> variant: a div inside a table body is hoisted out of the table by the
// parser, so both states have to arrive as a row.
function renderEmptyRow(tbody, colspan, message, detail) {
  if (tbody) tbody.innerHTML = '<tr><td colspan="' + (colspan > 0 ? colspan : 1) + '">' +
    '<div class="empty-state"><p>' + escapeHtml(message) +
    (detail ? '<br><span class="text-xs">' + escapeHtml(detail) + '</span>' : '') + '</p></div></td></tr>';
}
function renderErrorRow(tbody, colspan, message, detail) {
  if (tbody) tbody.innerHTML = '<tr><td colspan="' + (colspan > 0 ? colspan : 1) + '" style="padding:24px">' +
    errorStateHtml(message, detail) + '</td></tr>';
}

// ── page registration ────────────────────────────────────────────────────────
// Each pages/<page>.js registers its data loaders here; init() runs them all
// so the initial load behaves like the old single-page app. (Refresh in the
// top bar is a full location.reload() — base.html — so there is no refreshAll.)
const PAGE_LOADERS = [];
const PAGE_UNLOADERS = [];
function registerPageLoader(fn) { PAGE_LOADERS.push(fn); }
function registerPageUnloader(fn) { PAGE_UNLOADERS.push(fn); }

// A loader that throws (sync or async) must not reject init() and take the rest
// of the page with it; each one is isolated and the first failure is reported.
async function runLoaders() {
  const failed = (await Promise.all(PAGE_LOADERS.map(async (fn) => {
    try { await fn(); return null; }
    catch (e) { console.error('page loader failed', e); return e.message || String(e); }
  }))).filter(Boolean);
  if (failed.length) toast('Could not load part of this page: ' + failed[0], 'error');
}

// ── pipa adaptation: health pill reads pipa's /api/health ─────────────────
// (everything else in this file is verbatim ia_harness chrome: toasts,
// modal, sidebar, clock, tier helpers)
async function pollStatus() {
  const dot = document.getElementById('global-status-dot');
  const txt = document.getElementById('global-status-text');
  try {
    const h = await apiGet('/health');
    const up = !!(h.gateway && h.ollama);
    if (dot) dot.className = `status-dot ${up ? 'online' : 'offline'}`;
    if (txt) txt.textContent = up ? 'All systems operational' : 'Some services down';
  } catch (e) {
    // Never leave the pill on its initial "Checking…": unreachable is a verdict
    // the user needs, and a failed probe is exactly when silence lies. No toast
    // — this runs every 5s and a toast per tick would bury the page.
    console.error('status fetch failed', e);
    if (dot) dot.className = 'status-dot offline';
    if (txt) { txt.textContent = 'Dashboard API unreachable'; txt.title = e.message || String(e); }
  }
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
    },
    { html: true }
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
  } catch (e) {
    console.error('dashboard fetch failed', e);
    toast('Failed to load dashboard: ' + e.message, 'error');
    // The tables read STATE.catalog/STATE.tiers, so on failure they render
    // "nothing here" rather than "could not load". Say so in each one.
    const note = 'Could not load dashboard data';
    renderErrorRow(document.getElementById('tier-tbody'), 3, note, e.message);
    renderErrorRow(document.getElementById('tier-catalog-tbody'), 4, note, e.message);
    renderErrorRow(document.getElementById('tier-agents-tbody'), 5, note, e.message);
  }
}

async function init() {
  installConfirmGuards();
  updateClock();
  setInterval(updateClock, 1000);
  await Promise.all([pollStatus(), runLoaders()]);
  setInterval(pollStatus, 5000);
  window.addEventListener('resize', () => {
    if (window.innerWidth > 900) {
      const sidebar = document.getElementById('sidebar');
      if (sidebar && sidebar.classList.contains('open')) toggleSidebar();
    }
  });
}

// ── CSP-safe action dispatch ────────────────────────────────────────────────
// The dashboard runs under `script-src 'self'` with no 'unsafe-inline', so a
// browser refuses every inline on* attribute — a button carrying one is dead.
// Actions are declared as data attributes and dispatched here instead.
//   data-action="fn"              -> fn()
//   data-action="fn" data-arg="x" -> fn('x')
document.addEventListener('click', (ev) => {
  const el = ev.target.closest('[data-action]');
  if (!el || el.disabled) return;
  const fn = window[el.dataset.action];
  if (typeof fn !== 'function') return;
  fn(el.dataset.arg === undefined ? undefined : el.dataset.arg);
});

// A <select data-submit-form> submits its form on change (project pickers).
document.addEventListener('change', (ev) => {
  const el = ev.target.closest('[data-submit-form]');
  if (el && el.form) el.form.submit();
});

function reloadPage() { location.reload(); }

/**
 * Confirm destructive submits from a data attribute instead of inline JS.
 *
 * The old markup put a `confirm('Delete {{ path }}?')` call in an inline on*
 * submit handler. Jinja escapes the apostrophe to `&#39;`, then the HTML
 * parser DECODES it back to a quote before the JS parser ever runs — so a note
 * named `it's-bad.md` produced a JS syntax error, `confirm()` never ran, and
 * the form submitted anyway. The file was deleted with no prompt. Keeping the
 * path in `data-confirm` means no user-controlled string is ever part of a
 * script.
 */
function installConfirmGuards() {
  document.addEventListener('submit', (ev) => {
    const form = ev.target;
    if (!form || !form.dataset || !form.dataset.confirm) return;
    if (!window.confirm(form.dataset.confirm)) {
      ev.preventDefault();
      ev.stopPropagation();
    }
  }, true);
}

document.addEventListener('DOMContentLoaded', () => {
  init().catch((e) => { console.error('init failed', e); toast('Dashboard failed to initialise: ' + (e.message || e), 'error'); });
});
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