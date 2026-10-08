---
name: security-hardening
description: "Security checks beyond the always-loaded prohibitions. Triggers: adding a dependency, handling user input, URL params, env vars, file paths, SQL, shell commands, auth, secrets, new endpoint, validating input, sanitizing."
---

# Security hardening

The map carries the three hard prohibitions (no `eval`/`exec` on untrusted
input, never log secrets, never hardcode secrets). This skill carries
everything else — loaded when the work actually touches a risk surface.

## Input validation

- **Validate and sanitize every external input**: URL params, env vars, file
  paths, headers, request bodies.
- **Prefer allowlists over blocklists.** A blocklist is a losing game; an
  allowlist has a finite surface you can reason about.
- **Fail closed.** Deny by default. An unparseable input is a rejection, not
  a pass-through.

## Injection

- **Use parameterized queries.** Never string-concatenate SQL.
- **Never shell-concatenate.** Use argv arrays, not `sh -c` with interpolation.
- **Path handling:** resolve, then verify the result is inside the intended
  root. `../` traversal is the default assumption, not an edge case.

## Controls

- **Never disable or weaken security controls** — auth, validation, CSP,
  rate limits, signature checks. If a control blocks the task, report it; do
  not route around it.
- **Least privilege.** A helper that only reads should not be able to write.
  Scope file and tool access to the actual job.

## Dependencies

- **Flag any new dependency** before adding it:
  - license compatibility with the project
  - known CVEs
  - transitive count and install scripts
  - is it actually needed, or is one line of local code enough?
- A dependency is permanent maintenance debt, not a one-time cost.

## Secrets

- Never log or store secrets, tokens, passwords, certificates, or PII —
  including in error messages, stack traces, and test fixtures.
- Use env vars or the `{file:}` indirection. Never inline.
- When adding a secret-consuming code path, verify the failure mode is a
  clear error, not a null that silently disables the check.

## Threat modeling, briefly

Before hardening, answer in one line each:

1. What is the trust boundary you are adding?
2. Who can reach it?
3. What is the worst thing that happens if it fails open?

If you cannot answer, the control is probably in the wrong place.