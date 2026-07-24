# Testing
- [HARD] New behavior ships with a test. Bug fixes ship with a regression test.
- [HARD] Never skip or weaken tests to make CI pass; fix the code instead.
- [SOFT] Tests should be deterministic: no real network, no wall-clock, no random without a seed.
- [SOFT] Prefer the project's existing test framework; don't introduce a new one.
- [SOFT] Name tests by behavior, not by implementation: "returns 404 for missing user", not "test_fn_3".
