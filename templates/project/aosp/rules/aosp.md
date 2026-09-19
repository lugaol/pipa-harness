# AOSP conventions (project overlay)
#
# Put checkout facts (tree path, lunch target, modules) in .pipa/AGENTS.md
# placeholders — this file owns AOSP-local policy only.
- [HARD] Never patch AOSP platform, framework, or lower-HAL sources.
  Vendor overlay code only (e.g. `vendor/vw/*`); platform is read-only.
- [HARD] Full system build validates every change; module-only builds
  are for iteration, never for verification.
- [SOFT] Query the code graph before grepping for symbols that cross
  module boundaries.
- [SOFT] Centralize vehicle property IDs; no per-app duplicates.
- [SOFT] Minimal diff: skip → reuse (graph) → platform API →
  installed lib → one line → minimum.
- [SOFT] A nested `vendor/vw/apps/*/AGENTS.md` (when present) wins for
  module-local build commands and gotchas (closest-wins).
