# Briefing — Simplify pipa_harness

## Problem

pipa_harness works but has grown complex in ways that hurt new users:

- **10 dashboard pages** — most users only need 2 (Status + Models). Graph, Evals, and Spend are dev-only but occupy top-level nav slots.
- **238-line AGENTS.md** — mixes the always-loaded router with operational details (compaction budgets, sandbox paths, tracing) that belong in docs. New users face 22 sections before they understand the workflow.
- **Model config is 7 clicks** — 5 individual Save forms, manual Refresh, manual gateway restart on a different page. Auto-seed exists in CLI but never fires from the dashboard alone.
- **3 Python modules (845 lines) to route one model ID** — discovery → registry → composer, with 4 label normalizers, string-interpolated `os.environ/...`, and a heuristic tier seeder that's arbitrary but deterministic.
- **Layering is correct but not obvious** — the harness already separates global (low layer) from `.pipa/` (high layer), but AGENTS.md hardcodes absolute paths, legacy compat covers 3 layouts, and `ui-ux-pro-max` ships 1.7 MB of CSVs into every install.

## Goals

1. A new user configures models and runs an agent in **under 2 minutes**, without reading docs.
2. The dashboard has **5–6 top nav items**, not 10. Each page has one job.
3. `AGENTS.md` fits on one screen (~100 lines): router + workflow + golden rules. Everything else loads on demand.
4. Model setup is **one page, one save, one restart** — with auto-seed as the default.
5. Project overlay (`.pipa/`) is the only thing in a project. Uninstall = `rm -rf .pipa/ graphify-out/ && rm AGENTS.md`.

## Non-goals

- No new runtimes, providers, or skills. The 4 providers and 5 tiers stay.
- No breaking change to the session bus (`session.log.ndjson`) or spend ledger contracts.
- No rewrite of the LiteLLM gateway or graphify — only how pipa wires them.

## Constraints

- Runtime configs stay machine-global (`~/.config/opencode/`, `~/.dsh/`) — never in projects.
- Free-tier-only policy for model discovery stays.
- Existing projects with `.pipa/` must keep working after the refactor (migration, not recreation).
