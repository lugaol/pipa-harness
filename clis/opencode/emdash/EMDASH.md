# emdash + OpenCode integration

emdash is the parallel-agent orchestrator. It creates isolated git worktrees,
each running its own agent CLI (OpenCode, Claude Code, Codex, etc.).

## Setup

1. Install emdash: `brew install --cask emdash` (macOS) or see
   https://github.com/generalaction/emdash/releases
2. Add your project in emdash (point it at the repo root).
3. Copy the worktree scripts so emdash bootstraps each worktree:
   ```bash
   mkdir -p .opencode
   cp clis/opencode/emdash/setup-script.sh <project>/.opencode/
   cp clis/opencode/emdash/run-script.sh   <project>/.opencode/
   chmod +x .opencode/*.sh
   ```
   emdash runs `setup-script.sh` on worktree creation and `run-script.sh` when
   you press Run.

## Provider

When creating a task in emdash, select **OpenCode** as the provider. OpenCode
reads `.opencode/opencode.jsonc` which points at the LiteLLM gateway
(`http://localhost:4000`). All models flow through the aliases defined in
`models/.effective.yaml` (composed).

## Workflow

- **Single agent**: run `opencode` directly in the repo (uses the project config).
- **Parallel agents**: Add Task in emdash → each gets a worktree + branch.
  Review diffs side-by-side, merge what works, discard the rest.
- **Long research**: use emdash to run the `@researcher` subagent in its own
  worktree so it doesn't block implementation.

## Model routing per task

emdash tasks using OpenCode inherit the model from `opencode.jsonc` (`litellm/primary`).
To use a different model alias for a specific task, set the env var before creating it,
or override in the task's OpenCode session with `/model litellm/deep`.
