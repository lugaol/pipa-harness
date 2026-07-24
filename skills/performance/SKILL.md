---
name: performance
description: "Diagnose and fix performance issues: slow, latency, profiling, bottleneck, memory, CPU, optimization. Triggers: slow, performance, latency, optimize, bottleneck, memory leak, profiling."
---
# Performance triage

Diagnose performance issues with measurement, not guessing.

## Step 1 — Measure first
- Never optimize without a measurement. Identify the bottleneck before touching code.
- Find the project's profiler/benchmark tool (language-specific):
  - Node: `node --prof`, `clinic`, or the project's benchmark script.
  - Python: `cProfile`, `py-spy`, `pytest-benchmark`.
  - Rust: `cargo bench`, `flamegraph`.
  - Go: `go test -bench`, `pprof`.
- If no tool exists, ask the user how they want to measure, or suggest timing the suspect code path.

## Step 2 — Isolate
- Use graphify query to understand the call path and blast radius of the hot code.
- Confirm the hypothesis: does the profile point to the suspected function/loop?

## Step 3 — Optimize
- Make the smallest change that addresses the measured bottleneck.
- Prefer algorithmic improvements (O(n²)→O(n)) over micro-optimizations.
- Keep the code readable — a 5% speedup isn't worth obfuscation unless the path is truly hot.

## Step 4 — Verify
- Re-run the measurement. Report before/after numbers.
- Ensure tests still pass. "Done" = measured improvement + green tests, not "feels faster".
