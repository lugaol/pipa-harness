---
as_of: 2026-10-03
valid_until: 2026-11-03
status: active
---
<meta awareness="low">
# Research — Tools that generate project-specific AI agent context (rules / AGENTS.md / skills)

- **Question:** What open-source tools exist that analyse a codebase and emit
  project-specific agent context? Do any emit *skills* (progressive-disclosure
  `SKILL.md` folders)? Do any derive conventions from **static analysis** rather
  than prompting an LLM? Is there evidence they help?

## Headline findings

1. **AGENTS.md has no spec.** It is "just standard Markdown… the agent simply
   parses the text you provide" — no required fields, no schema
   (https://agents.md/). It is stewarded by the **Agentic AI Foundation** under
   the Linux Foundation since 2025-12-09 (https://openai.com/index/agentic-ai-foundation/).
2. **A *separate* open standard does exist for skills:** **Agent Skills** at
   https://agentskills.io — Anthropic-originated, now open, with a real spec
   (6 frontmatter fields, progressive-disclosure token budgets). 40+ clients
   listed. This is the one format with a normative spec.
3. **Almost nothing auto-generates these files.** Cursor and Copilot hand-write
   them or generate them *by asking the agent in chat*. The only
   vendor-shipped generator is Claude Code's bundled `/run-skill-generator`,
   and its method is **empirical capture** (run the build, record what worked),
   not static analysis.
4. **The static-analysis niche exists but is unvalidated.** `patchwork`
   (0★, 3 commits) and `codebase-md` (3★) do real tree-sitter work and emit
   `CONVENTIONS.md`/`AGENTS.md`. Neither has any adoption or independent
   evaluation.
5. **There is now peer-reviewed-style evidence that the popular approach is
   wrong.** arXiv:2602.11988 (ETH Zurich) found context files do **not**
   improve task success and cost **+20%**, and specifically that
   **"repository overviews … are not helpful"** — which is precisely what
   `/init`-style generators emit.

---

## Q1 — The AGENTS.md standard

**Primary source:** https://github.com/agentsmd/agents.md and https://agents.md/

| Fact | Value | Source |
|---|---|---|
| Stars | 24,742 | https://api.github.com/repos/agentsmd/agents.md |
| Created | 2025-08-19 | same |
| Last push | 2026-09-10 | same |
| Forks / open issues | 1,892 / 180 | same |
| License | MIT | same |
| Adoption | "over 60k open-source projects" | https://agents.md/ |

**Governance.** Donated to the **Agentic AI Foundation (AAIF)** under the Linux
Foundation, announced 2025-12-09 by OpenAI, co-founded with Anthropic and Block
and backed by Google, Microsoft, AWS, Bloomberg, Cloudflare
(https://openai.com/index/agentic-ai-foundation/). AAIF's working groups are
listed at https://aaif.io/ — none is an "AGENTS.md schema" working group.

**Is there a spec? No.** Direct quote from https://agents.md/ FAQ:

> "Are there required fields? **No.** AGENTS.md is just standard Markdown. Use
> any headings you like; the agent simply parses the text you provide."

Documented behaviours only: nearest file in the directory tree wins; nested
`AGENTS.md` supported (the main OpenAI repo reportedly has 88); migration path
is `mv AGENT.md AGENTS.md && ln -s AGENTS.md AGENT.md`.

**"openagents.md"?** No such project found. `agentsmd.org` does not resolve.
The standard is `AGENTS.md` under `agents.md` / `agentsmd/agents.md`.

**Supported readers** (https://agents.md/): Codex, Jules, Factory, Aider, goose,
opencode, Zed, Warp, VS Code, Devin, UiPath Autopilot, Junie, Amp, Cursor,
RooCode, Gemini CLI, Kilo Code, Phoenix, Semgrep, GitHub Copilot coding agent,
Ona, Windsurf, Augment Code.

## Q1b — Agent Skills: the one format WITH a spec

**Primary source:** https://agentskills.io/specification

- Anthropic-originated, released as an open standard, "open to contributions
  from the broader ecosystem"; repo https://github.com/agentskills/agentskills
  (https://agentskills.io/).
- Structure: `SKILL.md` (required) + optional `scripts/`, `references/`,
  `assets/`.
- Frontmatter: `name` (required, ≤64 chars, `a-z0-9-`, must match parent
  directory), `description` (required, ≤1024 chars), plus optional `license`,
  `compatibility` (≤500), `metadata`, `allowed-tools`.
- **Progressive-disclosure budgets:** metadata ~100 tokens at startup; full body
  <5000 tokens recommended; keep `SKILL.md` under 500 lines; keep file
  references one level deep.
- Validator: `skills-ref validate ./my-skill`.
- Claude Code accepts ~20 extra frontmatter fields as vendor extensions, but
  packing/upload for claude.ai or the Skills API accepts **only the 6 spec
  fields** or it hard-errors (https://code.claude.com/docs/en/skills).
- 40+ clients incl. Cursor, GitHub Copilot, VS Code, OpenCode, Codex, Gemini
  CLI, goose, Roo Code, Junie, Factory, Amp, Kiro, Laravel Boost
  (https://agentskills.io/).

**This is a different standard from AGENTS.md.** Two coexisting conventions.

## Q2 — What major tools ship, and do they GENERATE?

| Tool | Files | Generates? | Method |
|---|---|---|---|
| **Cursor** | `.cursor/rules/*.mdc` (frontmatter `description`/`globs`/`alwaysApply`), User/Team rules, `AGENTS.md` | **No** | Hand-written, or `/create-rule` in chat (agent writes the file on request). Plain `.md` in `.cursor/rules` is **ignored** — `.mdc` required. Nested `AGENTS.md` supported, more specific wins. Source: https://cursor.com/docs/context/rules |
| **GitHub Copilot** | `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md` (frontmatter `applyTo:`, optional `excludeAgent`), `AGENTS.md`, or `CLAUDE.md`/`GEMINI.md` | **Yes, officially** | GitHub publishes a **verbatim LLM prompt** to onboard a repo; Copilot cloud agent executes it and opens a draft PR. Source: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions |
| **Claude Code** | `CLAUDE.md`, `@import`, `.claude/skills/*/SKILL.md`, `.claude/agents/*.md` | **Yes — two ways** | `/init` "generate a starter CLAUDE.md file based on your current project structure" (LLM scan). Bundled `/run-skill-generator` writes `.claude/skills/run-<name>/`; `/verify` writes `.claude/skills/verify/SKILL.md`. Sources: https://code.claude.com/docs/en/best-practices , https://code.claude.com/docs/en/skills |
| **Aider** | `CONVENTIONS.md` (hand-written, `--read`) + **repo map** | **No** for conventions | Conventions are user-authored markdown. But Aider's repo map **is** real static analysis (tree-sitter AST + graph ranking over the dependency graph) fed as ephemeral context, never written to an editable file. Sources: https://aider.chat/docs/usage/conventions.html , https://aider.chat/docs/repomap.html |
| **Spec Kit** | `.specify/` artifacts | **No** — process scaffolding | Installs `/speckit-*` **agent skills**; emits specs/plans/tasks, not repo conventions. https://github.com/github/spec-kit |
| **BMAD-METHOD** | BMad briefs/specs/architecture | **No** | Installs skills via `npx skills add` / plugin marketplaces; emits delivery artifacts. https://github.com/bmad-code-org/BMAD-METHOD |

**The key asymmetry:** GitHub's official generation prompt is not "summarise
the repo". Its `<BuildInstructions>` block requires the agent to **empirically
execute** things — verbatim:

> "Each command should be validated by running it to ensure that it works
> correctly… Try cleaning the repo and environment and running commands in
> different orders and document errors and misbehavior observed… **Make a change
> to the codebase.** Document any unexpected build issues as well as the
> workarounds."

And it caps output: "Instructions must be no longer than 2 pages. Instructions
must not be task specific."

Claude Code's `/run-skill-generator` uses the same pattern and goes further:
`/run` and `/verify` first **infer** from project type + `README`/`package.json`/
`Makefile`, and the generator then **captures what actually worked**. Notably
Anthropic deliberately made the recorded file *stable* — "Claude edits the
recorded file only when it steered a run wrong… so you can commit the file
without per-session diffs" (https://code.claude.com/docs/en/skills).

## Q3 — Purpose-built generators

| Project | ★ | Emits | Method | Editable? | Active? |
|---|---|---|---|---|---|
| `github/spec-kit` | 140k | `.specify/` specs/plans/tasks + `/speckit-*` skills | LLM | yes | yes |
| `bmad-code-org/BMAD-METHOD` | 54k | BMad artifacts + skills | LLM | yes | yes |
| `bmad-code-org/bmad-builder` | 206 | skills/workflows/**agents** | LLM | yes | yes |
| `yamadashy/repomix` | 29k | `repomix-output.{xml,md,json,txt}` **+ `.claude/skills/<name>/`** via `--skill-generate` | **static** (gitignore-aware packing; tree-sitter for `--compress`) | yes | yes |
| `cyclotruc/gitingest` | 16k | repo→text digest | static | n/a | yes |
| `originalankur/GenerateAgents.md` | 257 | `AGENTS.md`, 17 fixed sections, `--style strict\|comprehensive` | **LLM** (DSPy RLM / Recursive Language Model) + `git log --grep=revert` | yes | last push 2026-03-03 |
| `FerroxLabs/agents-md` | 717 | one hand-written drop-in `AGENTS.md` | **hand-written** | yes | push 2026-05-31 |
| `savedpixel/ai-agent-rules-generator` | 7 | multi-tool rules/instructions/skills "from a single prompt" | LLM | yes | push 2026-04-11 |

**The repomix distinction you asked about is real but incomplete.** repomix's
primary output is a **context dump** — one merged file of the whole repo, meant
to be pasted/uploaded once. That is categorically different from an editable,
version-controlled rules file. But repomix *also* has `--skill-generate`,
which emits `.claude/skills/<name>/SKILL.md` containing "Skills metadata,
file/line/token counts, overview, and usage instructions"
(https://raw.githubusercontent.com/yamadashy/repomix/main/README.md). So repomix
straddles both. Note that its skill is a **codebase reference map**, not
conventions — it does not claim to tell the agent your style.

**Aider is a third category:** static analysis → **ephemeral context, no file at
all**. Worth separating from the other two.

**GenerateAgents.md is the most interesting LLM generator** because it has a
`--style strict` mode whose stated rationale is the research: "Research suggests
that broad, descriptive codebase summaries can sometimes distract LLMs and
drive up token costs. The strict style combats this by giving the agent *only*
what it can't easily `grep` for itself." It also mines `git log --grep=revert`
for "Lessons Learned / Anti-Patterns". That git-archaeology angle is the most
underrated idea here and is *not* LLM-hallucination-dependent.

## Q4 — Do skill-generating tools exist?

**Yes, but only three real ones, and none derives *conventions* from code.**

1. **Claude Code's bundled `/run-skill-generator`** — the closest thing to the
   ask. Emits a per-project `.claude/skills/run-<name>/`. Scope is **build /
   launch / verify recipes**, not coding conventions. Hybrid method: infer from
   `package.json`/`Makefile`/README → empirically capture → commit. Editable
   but deliberately stabilised. Needs Claude Code v2.1.200+.
   https://code.claude.com/docs/en/skills
2. **repomix `--skill-generate`** — emits `.claude/skills/<name>/`. Content is
   a **codebase reference map** (counts, overview, usage). Static. Editable.
3. **`patchwork`** — ships its own `SKILL.md` plus an **MCP server with 8
   tools** (`patchwork_naming`, `patchwork_testing`, `patchwork_check` …) so the
   agent can query conventions on demand instead of loading them all. This is
   arguably the *right* architecture for progressive disclosure. **But 0★.**

**What does not exist:** a maintained tool that statically analyses a codebase
and emits a **folder of `SKILL.md` files, one per concern** (naming / testing /
error-handling / API patterns), conforming to https://agentskills.io. The
`SKILL.md`-generator repos that exist (`Betswish/meta-skill-generator` 1★,
`bakrsabeeh/skill-generator` 1★, `lirazgershon148/conversation-to-skill-generator`
7★, `weareoxd/design-skill-generator` 1★) all generate skills from an **idea,
a conversation, or a Figma file** — not from source code. GitHub search for
`SKILL.md generator claude` returns only **17 repositories total**, max 7★.

## Q5 — Static-analysis-driven approaches

| Tool | ★ | Static signal used | Emits |
|---|---|---|---|
| `SaiNarayana-B/patchwork` | **0** | tree-sitter AST (py/ts/js/go/rust/java), reads `package.json`/`pyproject.toml`/`go.mod`/`Cargo.toml`; 7 miners (Naming, Import, Structure, ErrorHandling, Testing, APIPattern, GitPattern); per-category **confidence scores** + real examples + counter-examples; git commit/branch/co-change mining | `CONVENTIONS.md`, `AGENTS.md` (`--agents-md`), append `CLAUDE.md`, JSON. 100% local, zero LLM |
| `sauravanand542/codebase-md` | **3** | tree-sitter `convention_inferrer`; dependency parsing + live PyPI/npm health; TF-IDF context routing; git hooks | 6 formats: `CLAUDE.md`, `.cursorrules`, `AGENTS.md`, `codex.md`, `.windsurfrules`, `PROJECT_CONTEXT.md` |
| `SaiNarayana-B/patchwork` (via MCP) | 0 | same | on-demand tools instead of a file |
| Claude Code `/run`+`/verify` | vendor | project type + `README`/`package.json`/`Makefile` | recipe in a SKILL.md |
| Aider repo map | vendor | tree-sitter AST + PageRank-style graph ranking on dependency graph | ephemeral context |
| `laravel/boost` | unverified | framework-version-derived guidelines | vendor guidelines + agent skills (https://laravel.com/docs/12.x/boost#agent-skills) |

patchwork's design is the most interesting *on paper*: it emits exactly the
content class the research says matters (test framework, coverage tool, package
manager, exception naming, commit style) with **confidence percentages** and
**counter-examples**, and `patchwork update` "preserving manual edits".

**But calibrate hard.** patchwork: created 2026-06-24, last push 2026-06-25,
**3 commits, 0★, 0 forks, 70 KB**. Its README contains a competitive matrix
against "argus" and "sourcebook" — **neither is findable in GitHub search**, and
its contributing section still says `git clone https://github.com/yourusername/patchwork`.
Treat as a design sketch, not a product. codebase-md self-declares **v0.1.0
alpha**, tree-sitter limited to py/js/ts (Go and Rust by heuristics), no
incremental mode.

## Q6 — Anti-patterns and failure modes (all citations checked)

**The load-bearing primary source** is **arXiv:2602.11988**, Thibaud Gloaguen,
Niels Mündler-Sasahara, Mark Niklas Müller, Veselin Raychev, Martin Vechev
(ETH Zurich SRI Lab). Submitted 2026-02-12, last revised 2026-09-29 (v3).
https://arxiv.org/abs/2602.11988

Verbatim from the abstract:

> "we find that providing context files **does not generally improve task
> success rates**, while **increasing inference cost by over 20% on average**.
> This observation holds across different LLMs, coding agents, and for both
> LLM-generated and developer-committed context files. Specifically, we find
> that while instructions in the context files are **well followed** by coding
> agents, **repository overviews, although popular and recommended by model
> providers, are not helpful**. We conclude that while context files are useful
> for **specifying non-standard coding practices**, any attempts to improve
> performance should be **rigorously evaluated before deployment**."

Supporting evidence:

- **arXiv:2601.20404** — Lulla, Mohsenimofidi, Galster, Zhang, Baltes, Treude.
  10 repos / 124 PRs, with vs without `AGENTS.md`. "lower median runtime
  (Δ 28.64%) and reduced output token consumption (Δ 16.58%), while maintaining
  a **comparable task completion behavior**." So: faster and cheaper, **not more
  successful**. https://arxiv.org/abs/2601.20404
- **arXiv:2606.20512** — Shepard & Albrecht, "Probe-and-Refine Tuning of
  Repository Guidance for Coding Agents". This is the constructive result:
  33.0% mean resolve rate vs 28.3% static KB vs 25.5% unguided on SWE-bench
  Verified (p<0.001). Critically: "The improvement comes from **coverage rather
  than precision**: refined guidance produces evaluable patches for 14.5 pp more
  instances while per-patch precision remains statistically constant (~59%).
  … improved guidance helps agents **reach the correct file** rather than
  improving the quality of the changes they make." Their procedure uses
  **synthetic bug-fix probes** with **single-shot LLM calls, no agent loop and
  no tool use** — i.e. guidance is *tuned against measured failure*, not
  generated from a description. https://arxiv.org/abs/2606.20512

**Named failure modes:**

1. **Redundancy / context rot.** Overviews restate what the agent can derive from
   `package.json`, a file listing, or reading source. +20% cost, no accuracy gain
   (arXiv:2602.11988).
2. **Compliance ceiling.** Human-written verbose files help ~4% but cost ~+19%;
   agents follow *everything* — more tests, more file reads, more searching —
   with no proportional accuracy gain (reported in
   https://agentpatterns.ai/instructions/evaluating-agents-md-context-files/ —
   secondary source, not independently verified against the paper PDF).
3. **Silent truncation.** Codex CLI caps `AGENTS.md` at 32 KiB
   (`project_doc_max_bytes`, ~8k tokens); beyond that it is **silently
   truncated** (reported at
   https://codex.danielvaughan.com/2026/07/26/do-auto-generated-agents-md-files-actually-help-codex-cli-init-research-evidence-context-engineering/
   — secondary; the 32 KiB figure itself was not verified against
   developers.openai.com).
4. **Staleness / anchoring.** Mentioning a deprecated technology even in a "do
   not use" context biases generation toward it (Addy Osmani,
   https://addyosmani.com/blog/agents-md/ — cited by secondary sources; **not
   independently fetched**).
5. **Structure does not matter.** Reported null: moving instructions to the top,
   splitting into hierarchical files, or shortening files produced no
   detectable effect (McMillan, arXiv:2605.10039, per secondary source —
   **arXiv ID not independently verified**).
6. **Wrong information beats no information is false — but wrong is worse than
   redundant.** Removing existing repo docs made the *same* auto-generated file
   worth +2.7% (agentpatterns, secondary).
7. **Vendor docs themselves warn about this.** Claude Code's best-practices page
   lists "The over-specified CLAUDE.md… If your CLAUDE.md is too long, Claude
   ignores half of it" as a named failure pattern, and prescribes a
   line-by-line test: "Would removing this cause Claude to make mistakes?" with
   an explicit ✅Include / ❌Exclude table
   (https://code.claude.com/docs/en/best-practices).

## Q7 — Eval / benchmark work

This area is genuinely well-populated for 2026 — five papers, all reachable:

| ID | Title | What it measures |
|---|---|---|
| **arXiv:2602.11988** | Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents? | success rate + cost, LLM-generated vs developer-committed |
| **arXiv:2601.20404** | On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents | runtime + token efficiency, 10 repos / 124 PRs |
| **arXiv:2606.20512** | Probe-and-Refine Tuning of Repository Guidance for Coding Agents | resolve rate; coverage vs precision decomposition |
| arXiv:2605.10039 | Instruction Adherence in Coding Agent Configuration Files: A Factorial Study of Four File-Structure Variables | **null** result on file structure (ID unverified) |
| arXiv:2606.13449 | AIDev — agentic-PR merge rates vs context files | ~26.35% of projects degraded vs ~27.7% improved ≥20% (ID unverified) |

**Tooling that operationalises this** — `lukasmetzler/agenteval` (7★,
MIT): a linter + benchmarker + CI gate for instruction files. Supports
`CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`,
`.github/instructions/*.instructions.md`, `.claude/skills/*/SKILL.md`,
`.cursorrules`, `.cursor/rules/*.mdc`, `.windsurfrules`. Catches dead
references, filler phrases, contradictions, token-budget overruns, vague
instructions, stale instructions, and **invalid skill metadata per the Anthropic
spec**. `agenteval harvest` builds eval tasks from your own git history;
`agenteval ci --min-score` gates regressions. Its tagline is the right
posture: **"Your CLAUDE.md is untested."**
https://github.com/lukasmetzler/agenteval

Related: `gudo7208/awesome-coding-agent-eval` — a knowledge base of coding-agent
eval methods, itself shipped with an `AGENTS.md` + `llms-full.txt` for agent
consumption.

## What does NOT exist (verified gaps)

1. **No AGENTS.md schema.** No required fields, no validation, no formal spec,
   and no AAIF working group on it. Contrast with Agent Skills, which has one.
   → The "just Markdown" design is the reason nothing can validate it.
2. **No widely-adopted codebase → SKILL.md-folder generator.** The
   `SKILL.md generator` search returns **17 repos total, ≤7★**, and none derives
   skills from source code — they take an idea, a conversation, or a Figma file.
3. **No validated static-analysis conventions generator.** The two real ones
   have 0★ and 3★. `patchwork`'s README compares itself to "argus" and
   "sourcebook"; **neither is findable on GitHub**, so the competitive landscape
   it claims does not exist.
4. **No mainstream vendor ships static-analysis rule generation.** Cursor,
   Copilot, and Claude Code all produce *descriptions of the repo*, never
   *measured conventions with confidence scores*. This is the single largest
   opportunity.
5. **No agent that measures its own guidance file against task outcomes.** The
   loop in arXiv:2606.20512 (probes → measure → patch guidance) has been
   demonstrated in a paper and **not productised**. `agenteval` is the closest
   shipping approximation.
6. **No cross-tool context-file consistency checker.** Multiple competing
   formats (AGENTS.md, CLAUDE.md, .cursorrules, .windsurfrules, codex.md,
   copilot-instructions.md) and no tool verifies they agree. `codebase-md`
   generates 6 formats from one scan but does not validate consistency.
7. **No progressive-disclosure generator.** Everything emits a flat file loaded
   every session. `codebase-md`'s TF-IDF "smart context routing" is the only
   retrieval-shaped attempt I found, and it is 3★ alpha.

## Recommendation

For the stated goal (onboard an agent to a repo, project-specific, skills-shaped):

- **Steal probe-and-refine, not `/init`.** arXiv:2606.20512 is the only result
  showing a *positive* effect, and it works by measuring failures, not by
  describing the repo. "Coverage not precision" means the win is helping the
  agent *find the right file* — so emit **pointers and gotchas**, not
  architecture.
- **Ship static analysis, not LLM prose.** Every LLM-based generator (including
  `/init`) produces exactly the "repository overview" that arXiv:2602.11988
  shows is inert. `patchwork`'s confidence-scored, counter-example-bearing,
  zero-LLM output is the right *shape*, and its `update`-preserves-manual-edits
  plus `diff` CI gate is the right *lifecycle*.
- **Emit skills, not one file.** `SKILL.md` per concern (naming / testing /
  errors / API), each `name` matching its directory, each under ~500 lines and
  ~5k tokens per https://agentskills.io/specification. This gets you
  progressive disclosure instead of a 32 KiB every-session tax.
- **Validate with `agenteval` in CI** before believing any of it, and validate
  the `SKILL.md` frontmatter with `skills-ref validate`.
- **Kill anything the agent can grep.** Directory trees, tech stack, module
  purposes — delete on sight.

## Sources

- https://agents.md/ · https://github.com/agentsmd/agents.md
- https://openai.com/index/agentic-ai-foundation/ · https://aaif.io/
- https://agentskills.io/ · https://agentskills.io/specification
- https://code.claude.com/docs/en/skills · https://code.claude.com/docs/en/best-practices
- https://cursor.com/docs/context/rules
- https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- https://aider.chat/docs/repomap.html · https://aider.chat/docs/usage/conventions.html
- https://github.com/github/spec-kit · https://github.com/bmad-code-org/BMAD-METHOD
- https://github.com/yamadashy/repomix · https://github.com/cyclotruc/gitingest
- https://github.com/originalankur/GenerateAgents.md · https://github.com/FerroxLabs/agents-md
- https://github.com/SaiNarayana-B/patchwork · https://github.com/sauravanand542/codebase-md
- https://github.com/lukasmetzler/agenteval
- https://arxiv.org/abs/2602.11988 · https://arxiv.org/abs/2601.20404 · https://arxiv.org/abs/2606.20512
- https://agentpatterns.ai/instructions/evaluating-agents-md-context-files/
- https://codex.danielvaughan.com/2026/07/26/do-auto-generated-agents-md-files-actually-help-codex-cli-init-research-evidence-context-engineering/

### Not verified in this pass
Zed, Continue.dev, Cline, Roo Code, and Windsurf rule-file docs were **not**
individually fetched. They are confirmed only insofar as (a) https://agents.md/
lists them as AGENTS.md readers and (b) https://agentskills.io/ lists them as
Agent Skills clients, and (c) `agenteval` claims support for `.windsurfrules`
and `.cursor/rules`. Treat their specifics as unconfirmed. Also unverified:
GitNexus (48★) — star count confirmed, function **not** checked; it appears to
be a code-intelligence/knowledge-graph tool rather than a context-file emitter.
`laravel/boost` — repo exists, README is a stub pointing at laravel.com/docs;
its guidelines+skills role is sourced only from the agentskills.io blurb.
arXiv:2605.10039 and arXiv:2606.13449 were cited by secondary sources and their
abstracts were **not** fetched. The 32 KiB Codex truncation limit and Addy
Osmani's anchoring-effect claim are likewise secondary-sourced only.