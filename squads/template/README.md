# Squad / Project Extension Template — DEPRECATED

**DEPRECATED**: Use `.harness_extension/` in each project instead. See `README.md` for migration steps.

Copy this folder to `squads/projects/<your-project>/` and fill it in.
Run `harness/bin/pipa-extend.sh squads/projects/<your-project>` to merge it
into the base harness.

## Structure (all optional — include only what you need)
```
<your-project>/
├── AGENTS.md          # project-specific facts, commands, repo map (appended to base)
├── rules/             # project-specific path-scoped rules
│   └── <domain>.md
├── skills/            # project-specific trigger-loaded skills
│   └── <skill-name>/
│       └── SKILL.md
├── agents/            # project-specific subagents
│   └── <agent-name>.md
└── config/            # extra config (e.g. project-specific LiteLLM models)
    └── <name>.yaml
```

## AGENTS.md format
This file is *appended* to the base AGENTS.md between markers. Put here:
- Project name + one-line description
- Build/test/deploy commands
- Repo map (key directories)
- Any project-specific golden rules

Example:
```markdown
# My Android Audio App

## Commands
- Build: `./gradlew assembleDebug`
- Tests: `./gradlew testDebugUnitTest`

## Repo map
`app/src/main/cpp/` (Oboe/sfizz JNI) · `app/src/main/java/` (Kotlin UI) ·
`model/` (TFLite) · `tools/` (Python training)

## Project rules
- [HARD] No memory allocation in the audio callback.
- [HARD] Fixed 48 kHz; buffers in multiples of 192 frames.
```
