# squads/ — DEPRECATED

**DEPRECATED**: Use `.harness_extension/` in each project instead. See `README.md` for migration steps.

The `squads/` directory documented the old `pipa-extend.sh` extension model. Projects should migrate to `.harness_extension/`.

Two kinds of extensions live here:

## projects/
Per-project extension bundles. Each contains project-specific AGENTS.md
section, rules, skills, and/or agents that layer on top of the base harness.

```bash
# Create a project extension
cp -r squads/template squads/projects/my-project
# Edit the files...
# Merge into the harness:
harness/bin/pipa-extend.sh squads/projects/my-project
```

## Domain bundles (squads)
Modular agent teams for non-software or specialized domains (creative writing,
business, data, DevOps, etc.). Same structure as project extensions — the
difference is intent: a *project* extension customizes the harness for one repo;
a *squad* adds capabilities reusable across projects.

To create a squad, copy `squads/template/`, fill it in, and extend:
```bash
harness/bin/pipa-extend.sh squads/my-squad
```

Extensions are **additive only** — they never replace base harness files.
`pipa-extend.sh` uses `cp -n` and appends AGENTS.md sections between markers.
