"""Pure data readers for the dashboard — no HTML, no routing.

Each module wraps one source of truth (gateway HTTP, session log, spend
ledger, agent files, service probes, project registry). All readers fail
soft: callers get empty results, never exceptions.
"""
