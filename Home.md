# pipa_harness — Home

Project-agnostic agent harness, installed once at `~/.pipa-harness`, shared by every project.

## Map of content
- [[README]] — install (`bootstrap.sh` / `make -C install`) and full usage guide: overlay, CLI, models, dashboard
- [[AGENTS]] — always-loaded router: philosophy, golden rules, routing, model tiers
- [[WORKFLOW]] — workflow reference: layered loading + patterns A–L
- [[docs/ARCHITECTURE]] — planes, precedence rules, data flows
- [[vault/decisions/000-template|Decision template]] — architectural memory
- [[state/SESSION]] — warm session resume · [[state/PLAN]] — in-session work ledger

## Quick start
1. Install: `bash bootstrap.sh`, then `pipa up`
2. Adopt a project: `cd any-project && pipa init`
3. Run: `opencode` or `dsh web` · Dashboard: http://localhost:8080

Open this repo root as an Obsidian vault; start here at `Home.md`. Generated
graph notes live in `graphify-out/obsidian/` (gitignored — regenerate with
`graphify export obsidian`).
