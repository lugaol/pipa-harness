# HS-008: A strict CSP silently kills every inline handler while tests stay green

- 2026-10-04 (dashboard buttons): the new same-origin/CSP work shipped
  `script-src 'self' https://cdn.jsdelivr.net` with no `'unsafe-inline'`.
  Browsers refuse every inline `on*` attribute under that policy, so **every
  button on the dashboard did nothing** — save tiers, save agent tier, reset,
  sidebar, refresh. Backend routes were fine, so API tests (TestClient) all
  passed; the failure existed only in the delivered HTML.
- Rule: a security header that changes what the browser executes must ship
  with a compatibility test over the *rendered output*, not just the guard's
  behaviour. Inline handlers are code that CSP can refuse.
- Fix: actions are declared as `data-action="fn"` (+ optional `data-arg`) and
  dispatched by one delegated listener in `common.js`; selects use
  `data-submit-form`. CSP stays strict.
- Enforced by `tests/test_dashboard_security.py::test_no_inline_event_handlers_under_csp`,
  which scans templates and JS for `on*=` and fails the build.
- Context: the older scan only flagged inline handlers that *interpolated user
  data*; static `onclick="foo()"` passed it while being equally dead.
