---
name: using-pipa-in-an-existing-project
description: "Adopt pipa in a project that already has code, tests, and maybe its own AGENTS.md. Triggers: existing project, add pipa to my repo, adopt, integrate, on my codebase, project already started, brownfield, legacy repo, my repo already has code, wire up this repository."
---

# Using pipa in an already-started project

Every command here was run against a real repository with committed code and
tests. Where something does not work, it says so.

## 1. Preflight (30 seconds, from anywhere)

```sh
pipa doctor
```

Read the two checks that predict everything else:

- **`cli-on-path`** — the CLI and the agent must run the same checkout. A
  `SPLIT-BRAIN` here means your edits appear to do nothing.
- **`agent-instructions`** — confirms the agent actually loads project
  context. If this is not `OK`, nothing you put in a project file is read.

Then, in the project:

```sh
pipa next      # the single next action, derived from real state
```

## 2. Adopt it

```sh
cd /path/to/your/project
git init          # only if it is not already a repo
pipa init
```

`init` is **additive**. Verified: it only ever adds files. It never edits
your code, and if you already have an `AGENTS.md` it leaves it completely
alone and tells you so.

What you get:

```
.pipa/
  runtime          the agent runtime ("opencode")
  AGENTS.md        project facts: name, build command, test command
  rules/           your project rules, loaded on trigger
  memory/          decision / research notes
  state/           harness state (gitignored)
AGENTS.md -> .pipa/AGENTS.md    (symlink, unless you already had one)
```

## 3. Check the build/test detection

`init` guesses from filenames — `package.json` → `npm test`, `gradlew` →
`./gradlew test`, `pyproject.toml` → `pytest`, `Makefile` with a `test:`
target → `make test`, `Cargo.toml` → `cargo test`.

```sh
grep -E "Build|Tests" .pipa/AGENTS.md
```

**It will say `none detected` for anything it does not recognise** — Go,
Rust workspaces, Bazel, monorepos, and the harness itself. That is a normal
outcome, not a bug. Edit the two lines in `.pipa/AGENTS.md` and move on.

Confirm it took:

```sh
pipa next
```

If it still says "unfilled placeholders", the edit did not land where the
agent looks.

## 4. If your project already has an AGENTS.md

Verified behaviour: `init` leaves your file untouched and skips the symlink.
The harness then writes its own `.pipa/AGENTS.md` separately, and **both** are
in the agent's `instructions` — your house rules and the build/test facts are
loaded together.

If your build/test facts belong in *your* file instead, just put them there.
Nothing requires the symlink.

## 5. Prove the loop is closed

The single test that matters — ask the agent something only your project can
answer:

```sh
opencode run "what build and test commands does this project use?"
```

If it answers with your real commands, the harness is wired. If it says
`none detected`, step 2 or 3 is incomplete.

Then confirm it can actually run them:

```sh
opencode run "run this project's tests and report the exact command"
```

## 6. Turn on the checks (recommended)

Enforcement is opt-in per project, so the harness does not touch your git
config until you ask:

```sh
pipa check --install-hooks
```

This wires three hooks: secrets on commit, commit-message shape, and a
branch gate. Bypass once with `git commit --no-verify`.

Verify models are genuinely callable, not merely listed:

```sh
pipa check config    # do the default models exist in the gateway?
pipa check models    # is every model in the picker actually callable?
```

`pipa check models` sends a real request per model. This is worth running
once after adopting pipa, because it is the check that catches a model that
appears in the catalog and 400s on contact.

## 7. Work with more than one agent

Delegation is `task()`. For anything wider, agents share a board:

```sh
pipa agents                     # what can be delegated to, and what each is for
pipa agents --json              # same, for an orchestrating agent

pipa bus post --from explorer --to dev --kind finding \
  --body "Token validation: src/auth/session.py:42"
pipa bus read --to dev --since 12
pipa contract                   # what every subagent claimed, and what is unverified
```

**Read the bus before broad exploration.** A sibling may already have
answered, and the board is cheaper than the search it replaces.

## Day-to-day

```sh
pipa next        # what to do now
pipa status      # is anything actually wrong
pipa doctor      # full diagnostics
pipa check       # mechanical checks
pipa recall "x"  # project memory, vault, and code graph in one query
```

## What is optional

- **The code graph.** `pipa status` reports it as `WARN`, not `FAIL`, because
  a project without one is a choice. Enable with `graphify extract .` when
  you want "search before you grep" to be true. It is the single biggest
  quality upgrade available and the easiest to skip.
- **The bus.** Useless with one agent. Worth it the moment you fan out.
- **Project memory.** Accumulates from use; nothing to do up front.

## Known limits

- **Build/test detection is filename-based.** It will not read your Makefile
  targets, infer a monorepo layout, or detect Bazel/Go. Manual fill is
  expected.
- **The bus is pull-based.** An agent must run `pipa bus read` to see
  messages; nothing pushes. A long-running agent will not be interrupted by a
  sibling's finding — it has to look.
- **`pipa init` does not touch your global config.** If `pipa doctor` reports
  a wiring problem, fix it deliberately; it will not be papered over.
