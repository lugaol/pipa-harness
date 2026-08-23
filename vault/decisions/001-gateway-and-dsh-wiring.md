# Decision: LiteLLM stays the LLM plane; dsh wired via cordis.patch.yml

**as_of:** 2026-08-22
**scope:** decisions

## Context
The `@deepseek-ai/harness` npm package never existed; the real package is
`@deepseek-ai/dsh`. The first cordis.yml template used a fictional schema.

## Decision
1. Gateway: keep LiteLLM (:4000) — de-facto self-hosted OSS standard;
   Portkey only wins on guardrails, Helicone is maintenance-mode.
2. Free-tier aliases: kilo (`kilo-auto/free`, stepfun flash), Kimi trial
   credits, OpenRouter `:free` routes (or-* aliases) gated on
   OPENROUTER_API_KEY.
3. dsh wiring: write `~/.dsh/cordis.patch.yml` patching the dormant
   `llm-pi-ai` adapter (`api: openai-completions`,
   `compat.supportsDeveloperRole: false`, `maxTokensField: max_tokens`)
   plus `~/.dsh/.credentials.yaml` ref — no key ever in YAML.
4. Conformance tests (tests/test_conformance_*.py) pin these contracts so
   a fictional schema cannot ship again.

**valid_until:** 2027-08-22 (revisit when dsh leaves developer preview)
