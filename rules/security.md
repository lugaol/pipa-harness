# Security
- [HARD] Never log secrets, tokens, passwords, or PII.
- [HARD] Validate and sanitize all external input (URL params, env, file paths).
- [HARD] Use parameterized queries; never string-concatenate SQL/shell commands.
- [HARD] No `eval`, `Function()`, `exec()` on untrusted input.
- [SOFT] Prefer allowlists over blocklists for input validation.
- [SOFT] Fail closed (deny by default), not open.
