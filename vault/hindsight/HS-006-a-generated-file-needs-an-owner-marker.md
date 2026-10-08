# HS-006: A generated file needs an explicit owner marker, not a substring guess

- 2026-10-03 (opencode wiring): the re-render guard was
  `if "pipa" in gcfg.read_text()`. Every config pipa writes contains that
  substring — in `sk-pipa-local`, in the instruction globs, in a comment — so
  the guard always matched and the file was **never regenerated again**. Tier
  changes reached the gateway but not the runtime, from the first write on.
  Use a machine-readable key (`_pipa_generated`) in the output.
- 2026-10-03 (write-through): `~/.config/opencode/agent` was a symlink to the
  harness `agents/` dir, so rendering agent tiers **rewrote the harness's own
  source files** and reported success. Refuse to write through a symlinked
  output dir.
- Rule: generated output needs (a) a marker that distinguishes "mine" from
  "yours", (b) idempotent regeneration, (c) a guard against writing through a
  link. Miss (a) and the file freezes; miss (c) and the render eats its input.
