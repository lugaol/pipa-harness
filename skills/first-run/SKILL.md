---
name: first-run
description: "Set up pipa in a new project and get the agent reading it. Triggers: new project, first time, getting started, onboarding, setup, init, from scratch, dummy user, how do I start, nothing works, agent ignores my rules."
---

# First run

The shortest path from an empty directory to an agent that reads your
project. Every step here was verified by walking it as a new user.

## 1. Get the CLI on PATH

`pipa` should resolve to the same checkout your agent config reads.

```sh
pipa doctor          # prints cli-on-path and agent-instructions
```

If `cli-on-path` says **SPLIT-BRAIN**, the CLI on PATH and the agent's
`AGENTS.md` are two different copies, so your edits appear to do nothing.
Fix by pointing the symlink at the checkout you actually edit:

```sh
ln -sfn /path/to/your/checkout ~/.pipa-harness
hash -r
```

Rule of thumb: **`pipa` on PATH and the agent's `instructions` must be the
same tree.** Everything else is downstream of that.

## 2. Init a project

```sh
cd myproject
git init            # required — memory and rules anchor to the repo
pipa init
```

`pipa init` creates a thin overlay in `.pipa/` and never overwrites global
wiring. It picks `opencode` unless you pass `--runtime`.

## 3. Make the agent actually read it

This is the step people miss. `pipa init` writes `AGENTS.md` in the project,
but that file is only visible to the agent if it is in the `instructions`
array of `~/.config/opencode/opencode.jsonc`:

```jsonc
"instructions": [
  "/abs/path/to/pipa/AGENTS.md",  // global map
  "AGENTS.md",                    // project context (relative to cwd)
  ".pipa/rules/*.md"              // project rules, loaded on trigger
]
```

If `AGENTS.md` is missing, everything `pipa init` generated is invisible —
the agent works, it just knows nothing about your project. `pipa doctor`
checks this and reports it as `agent-instructions`.

## 4. Fill the placeholders

`init` cannot infer your build system in a bare directory, so it writes:

```
- Build: `none detected — add your build command`
- Tests: `none detected — add your test command`
```

Edit `.pipa/AGENTS.md` and put the real commands in. Until then the agent
has no verified way to run your tests, and will guess.

## 5. Verify the whole loop

```sh
pipa status         # services + project wiring
pipa doctor         # split-brain, callability, credentials
pipa check          # mechanical checks: config | models | tiers | secrets
```

Then ask the agent something only your project can answer:

```sh
opencode run "what build and test commands does this project declare?"
```

If it answers with your real commands, the loop is closed. If it says
`none detected`, step 3 or 4 is incomplete.

## 6. Keep it honest

`pipa check` is the difference between a harness you trust and one you hope
works. It sends real requests, so it catches what reading config cannot:

| Command | Catches |
|---|---|
| `pipa check config` | default models missing from the gateway |
| `pipa check models` | picker models that are listed but not callable |
| `pipa check tiers` | a tier pointing at a model that 400s |
| `pipa check secrets` | credentials in tracked files |

Run `pipa check models` and `pipa check tiers` after changing any model
assignment. Listing a model in a catalog proves nothing — only a live call
does. If the gateway is down these degrade to a warning rather than
reporting every model as broken.

## First-hour checklist

- [ ] `pipa doctor` shows no SPLIT-BRAIN
- [ ] `pipa doctor` shows `agent-instructions` OK
- [ ] `pipa init` completed, `.pipa/runtime` is the runtime you use
- [ ] Build and test commands filled into `.pipa/AGENTS.md`
- [ ] Agent answers correctly about your project
- [ ] `pipa check` exits 0
