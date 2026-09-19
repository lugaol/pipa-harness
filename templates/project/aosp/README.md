# AOSP project template (`pipa init --type aosp`)

AOSP/Automotive specialization ported from ia_harness (which is
AOSP-specific). Installs only for AOSP checkouts — never in core.
Select with `pipa init --type aosp`.

Included overlays (merged over `templates/project_scaffold/`):

- `rules/aosp.md` — edit-scope policy (vendor overlay writable, framework
  and AOSP platform read-only), full-build rule, MOC-first memory pointers.
- `skills/` — pointers to the emulator, build-and-test, and code-review
  skills with AOSP specifics (adb via RADB, UPdated-system-app gotcha).
