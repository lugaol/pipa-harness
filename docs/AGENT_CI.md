# Agent CI

Merge gate for agent definitions. Every PR touching `agents/**` or
`.pipa/agents-local/**` runs `tools/evals/run.py`. Regressions fail
the check before merge.

## Why

Agent markdown *is* code. A casual edit to `@qa` can drop the PASS/FAIL rule or
delete an approval gate — nothing else in CI catches that. Evals do.

## Usage

Zero config. The workflow (`.github/workflows/agent-evals.yml`) already calls
the local action:

```yaml
- uses: ./
```

Or use it in any workflow:

```yaml
- uses: lugaol/pipa-harness@main
  with:
    evals-path: tools/evals/run.py   # default
    python-version: "3.12"                 # default
    fail-on-error: "true"                  # default; "false" = warn only
```

Results land in the job summary:

| file | check | pass |
|------|-------|------|
| `agents/explorer.md` | has_transparency_rule | :white_check_mark: |
| `agents/qa.md` | qa_no_looks_good | :white_check_mark: |
| `agents/dev.md` | dev_golden_rules | :white_check_mark: |

Badge:

```markdown
[![Agent Evals](https://github.com/lugaol/pipa-harness/actions/workflows/agent-evals.yml/badge.svg)](https://github.com/lugaol/pipa-harness/actions/workflows/agent-evals.yml)
```

## Add a golden check

1. Write a predicate over the agent file content.
2. Attach it in `run_evals()` keyed by filename.
3. It runs in CI automatically. Exit code follows failures.

```python
def check_sm_no_prose(content):
    """@sm stories must be self-contained."""
    return "self-contained" in content.lower()

# inside run_evals(), after the existing checks:
if "sm" in f.name:
    result["sm_self_contained"] = {"pass": check_sm_no_prose(content), "msg": "stories self-contained"}
```

## Roadmap

Task-level evals: run real agent sessions end-to-end through the LiteLLM free
tier and grade transcripts, not just file contents. Same gate, deeper signal.
