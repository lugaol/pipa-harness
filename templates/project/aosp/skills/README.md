# AOSP skills (project overlay)

Project-local skills extend the global `skills/` catalog. Keep each
SKILL.md small and point at the global skill for shared mechanics.

- `skills/emulator/SKILL.md` — boot/manage the AOSP emulator, log
  monitoring, screen navigation helpers.
- `skills/build-and-test/SKILL.md` — full emulator/sample image builds,
  adb smoke suite, evidence-backed verdicts.
- `skills/radb/SKILL.md` — remote-device bridge: list, reserve, deploy
  (UPDATED_SYSTEM_APP gotcha: a naive `/system` push + reboot silently
  doesn't deploy).
