# HS-003: A check that cannot reach its evidence is not a pass

- 2026-10-03 (pipa-check): a check whose evidence is unreachable must return
  a distinct "inconclusive" code, never `0`. `config` and `tiers` both
  returned 0 with the gateway down, so `pipa-check all` printed `PASSED` and
  exited 0 — the invariant "every model in the picker is callable" was
  never once actually evaluated, yet the map listed it as "active".
- 2026-10-03 (tests): never assert a global health total (`fail == 0`) while
  depending on a live service. Stub the probes. A test whose pass/fail
  depends on whether the developer's machine has a gateway running trains
  everyone to ignore red.
- Context: `bin/pipa-check` had two "degraded mode" branches that conflated
  "I could not check" with "nothing is wrong", and `test_bus_contract` read
  the real gateway.
