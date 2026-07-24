# Code review
- [HARD] Reject patches that hardcode secrets/API keys/tokens in source.
- [HARD] Reject patches that disable or weaken security controls (auth, validation, CSP).
- [HARD] Flag any new dependency — check license compatibility and known CVEs.
- [SOFT] Prefer pure functions and immutability; minimize side effects.
- [SOFT] Public APIs need a docstring/JSDoc + at least one usage example in comments.
- [SOFT] No commented-out dead code; remove it.
