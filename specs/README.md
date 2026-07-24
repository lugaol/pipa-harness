# specs/ — plan → story workflow

Two-phase output directory. Created by planning agents, consumed by build agents.

```
specs/
├── STORY_TEMPLATE.md          # copy this for each new story
└── <feature>/                 # one folder per feature/epic
    ├── briefing.md            # @analyst — problem + stakeholders
    ├── prd.md                 # @pm — requirements + acceptance criteria
    ├── architecture.md        # @architect — technical design + file:line refs
    └── stories/               # @sm — self-contained build units
        ├── 01-setup.md
        ├── 02-core-logic.md
        └── 03-tests.md
```

## Flow
1. `@analyst` → `briefing.md`
2. `@pm` → `prd.md`
3. `@architect` → `architecture.md`
4. `@qa` → critique the above (loop until solid)
5. `@sm` → `stories/NN-*.md` (one per buildable unit)
6. `@dev` → implement stories in order
7. `@qa` → review each build

For trivial tasks, skip to `@dev` directly — no spec needed.
