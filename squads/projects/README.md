# squads/projects/ — DEPRECATED

**DEPRECATED**: Use `.harness_extension/` in each project instead. See `README.md` for migration steps.

One bundle per project that adopts the harness. A bundle may contain:
`AGENTS.md` (appended between markers), `rules/`, `skills/`, `agents/`,
`config/` — see `squads/template/` for the format.

A bundle can also be a **symlink to an in-repo `harness/` directory**, which
keeps the extension versioned together with its own project:

```bash
ln -s /path/to/project/harness squads/projects/<name>
```

Manage merged extensions:

```bash
bin/pipa-extend.sh squads/projects/<name>   # merge (additive)
bin/pipa-extend.sh --update <name>          # re-copy from the bundle
bin/pipa-extend.sh --remove <name>          # unmerge completely
bin/pipa-extend.sh --list                   # show installed extensions
```
