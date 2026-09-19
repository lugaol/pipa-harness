# Security
- [HARD] Never log secrets, tokens, passwords, or PII.
- [HARD] Never hardcode secrets/API keys/tokens in source.
- [HARD] Validate and sanitize all external input (URL params, env, file paths).
- [HARD] Use parameterized queries; never string-concatenate SQL/shell commands.
- [HARD] No `eval`, `Function()`, `exec()` on untrusted input.
- [HARD] Never disable or weaken security controls (auth, validation, CSP).
- [HARD] Flag any new dependency — check license compatibility and known CVEs.
- [SOFT] Prefer allowlists over blocklists for input validation.
- [SOFT] Fail closed (deny by default), not open.
