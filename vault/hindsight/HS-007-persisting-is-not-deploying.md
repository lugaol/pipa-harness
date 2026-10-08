# HS-007: Persisting a decision is not deploying it

- 2026-10-04 (dashboard agent tiers): saving an agent's tier wrote
  `state/agent_llm_overrides.json` and returned `{"ok":true}` — but the agent
  reads `~/.config/opencode/agent/*.md`, which only re-rendered on `pipa up`.
  The dashboard toasted success while every agent kept its old tier. Fixed with
  `pipa.runtime.refresh_agents()` as the single owner, called by every
  dashboard write path after the save (once per batch).
- Rule: when the store is not the artifact the consumer reads, the writer must
  trigger the render — or the save is a lie with a success toast. Put the
  render behind one owner in `pipa/`; the dashboard calls it, never copies it.
- Test: `test_api.py::test_agent_tier_roundtrip` asserts one render per save
  and one per batch; the endpoint tests monkeypatch `refresh_agents` so they
  never touch the developer's real `~/.config/opencode`.
- Context: the render function's own docstring said the dashboard picker "was
  a no-op" — it had fixed the symlink, but only `pipa up` ran the render.
