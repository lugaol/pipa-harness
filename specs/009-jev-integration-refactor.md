# 009 — Jev MCP Integration & Pipa Harness Refactor

## Executive Summary

This refactor transforms pipa harness from an LLM-only routing system into a **hybrid intelligence architecture** where Jev handles fast, structured decisions (routing, triage, classification) and LLMs handle complex reasoning, code generation, and explanations. The result: 20-40x faster routing, zero cost for simple decisions, and a more reliable, deterministic system.

---

## Part 1: Current State Analysis

### What Works Well
- **Two-phase workflow** (Plan → Build) is solid
- **Tiered model routing** (lowest → xhigh) is cost-effective
- **Graphify integration** provides excellent code understanding
- **Vault/memory system** enables session continuity
- **Rules/skills architecture** allows progressive disclosure

### Current Pain Points

| Problem | Impact | Current Solution | Cost |
|---------|--------|------------------|------|
| **LLM-based routing** | 1-3s latency, $0.0001-0.001/route | `@jam-supervisor` uses LLM to decide | Tokens + latency |
| **Simple decisions need LLMs** | Overkill for classify/score/route | Full LLM call for trivial tasks | Expensive |
| **No confidence calibration** | LLMs are overconfident or inconsistent | No programmatic confidence | Unreliable |
| **String generation overhead** | LLMs generate text for decisions | Parse+validate structured output | Fragile |
| **Routing mistakes cascade** | Wrong agent = wasted tokens + time | Retry loops | Expensive |

### Current Architecture Flow

```
User Request
    │
    ▼
@jam-supervisor (LLM, 1-3s, $0.0001+)
    │
    ├──→ @jam-explorer (cheapest LLM)
    ├──→ @jam-implementer (strongest LLM)
    ├──→ @jam-verifier (fast LLM)
    └──→ @jam-researcher (deep LLM)
```

**Problem**: The supervisor is an LLM doing what should be a 70ms function call.

---

## Part 2: Target State Architecture

### Core Principle: Jev as Intelligence Layer, LLMs as Generation Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER REQUEST                                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  JEV LAYER (70ms, free)                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ • Task classification (explore/implement/verify/research)│    │
│  │ • Confidence scoring (0.0 - 1.0)                        │    │
│  │ • Simple decisions (yes/no, which one, priority)        │    │
│  │ • Triage (bug/feature/question, severity)               │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐
│ HIGH CONFIDENCE     │       │ LOW CONFIDENCE      │
│ (≥0.90)             │       │ (<0.90)             │
│ → Direct route      │       │ → LLM escalation   │
│ No LLM needed       │       │                     │
└─────────────────────┘       └─────────────────────┘
          │                               │
          ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐
│ SPECIFIC AGENT      │       │ LLM AGENT           │
│ (explore/verify)    │       │ (dev/researcher)    │
└─────────────────────┘       └─────────────────────┘
```

### Jev Layer Responsibilities

| Task | Jev Tool | Confidence Threshold | Action |
|------|----------|---------------------|--------|
| Route to agent | `classify` | ≥0.90 → direct, <0.90 → LLM | Instant routing |
| Bug severity | `classify` | Always | No LLM needed |
| Feature vs bug | `classify` | ≥0.90 → direct | Skip supervisor |
| Build error type | `classify` | ≥0.85 → direct | Route to skill |
| Code quality score | `score` | Always | Pre-check before review |
| Is this ready to merge? | `check` | ≥0.95 → skip review | Save tokens |
| Which file to edit? | `match` | ≥0.80 → direct | Skip exploration |

### LLM Layer Responsibilities

| Task | Why LLM Needed | Which Tier |
|------|----------------|------------|
| Code generation | String output required | `mid` (implementer) |
| Complex reasoning | Chain-of-thought | `high` (researcher) |
| Explanations | String generation | `low` (verifier) |
| Architecture design | Creative + structured | `high` (architect) |
| Conflict resolution | Multi-factor judgment | `xhigh` (supervisor) |

---

## Part 3: Jev MCP Integration

### 3.1 Install Jev MCP Server

Add Jev as a registered MCP server in pipa harness:

```json
// mcp/jev/config.json
{
  "name": "jev",
  "type": "remote",
  "url": "https://api.typesafe.ai/v1/mcp",
  "env": {
    "TYPESAFE_API_KEY": "${TYPESAFE_API_KEY}"
  },
  "tools": [
    "jev_classify",
    "jev_check",
    "jev_ask",
    "jev_match",
    "jev_score"
  ]
}
```

### 3.2 Jev Provider in providers.yaml

```yaml
# models/providers.yaml addition
- slug: typesafe
  label: TypeSafe Jev
  kind: cloud
  requires: [TYPESAFE_API_KEY]
  list_url: https://api.typesafe.ai/v1/models
  keep: jev_only
  litellm:
    model: "openai/jev-1.13-free"
    api_base: https://api.typesafe.ai/v1
    api_key: os.environ/TYPESAFE_API_KEY
    custom_llm_provider: openai
```

### 3.3 New Tier: `jev`

Add a dedicated tier for Jev decisions:

```yaml
# models/tiers.yaml addition
tiers:
  jev:
    label: Jev
    description: Fast structured decisions — routing, triage, classification. Zero cost.
    cost_ceiling_usd_per_1m: 0.0
    latency_target_ms: 100
    min_context: 4096
    max_steps: 1
```

---

## Part 4: Refactored Routing System

### 4.1 New Agent: `@router`

Replace the LLM-based supervisor routing with a Jev-powered router:

```yaml
# agents/router.md
---
model: jev/jev-1.13-free
description: Fast task router using Jev. Classifies requests and routes to correct agent.
mode: subagent
permission:
  edit: deny
  bash:
    "*": deny
  task:
    "*": allow
---
You are a task router. You classify incoming requests and route them to the correct agent.

## Classification Schema

Classify each request into:
1. **Task type**: explore | implement | verify | research | orchestrate
2. **Complexity**: simple | moderate | complex
3. **Confidence**: 0.0 - 1.0

## Routing Rules

| Classification | Confidence | Route To |
|----------------|------------|----------|
| explore + simple | ≥0.90 | @jam-explorer |
| explore + moderate | ≥0.85 | @jam-explorer |
| implement + simple | ≥0.90 | @jam-implementer |
| implement + moderate | ≥0.85 | @jam-implementer |
| verify + any | ≥0.90 | @jam-verifier |
| research + any | ≥0.85 | @jam-researcher |
| orchestrate + any | <0.90 | @jam-supervisor |
| any + complex | <0.80 | @jam-supervisor |

## Output Format

Return a JSON object:
```json
{
  "task_type": "explore|implement|verify|research|orchestrate",
  "complexity": "simple|moderate|complex",
  "confidence": 0.95,
  "route_to": "@jam-explorer",
  "reasoning": "Simple file lookup, high confidence"
}
```

## Escalation

If confidence < 0.80 for any classification, escalate to @jam-supervisor.
```

### 4.2 Refactored Supervisor Flow

```yaml
# Updated jam-supervisor.md (excerpt)
## Coordination modes
1. **First**: Run @router to classify the task
2. **If confidence ≥ 0.90**: Route directly to classified agent
3. **If confidence < 0.90**: Use your own judgment (LLM reasoning)
4. **Always**: Log routing decision for learning
```

### 4.3 Jev Decision Patterns

#### Pattern 1: Task Classification (Replace Supervisor Routing)

```python
# Before (LLM-based routing):
response = llm_call(
    prompt=f"Classify this task and route to the correct agent: {task_description}",
    tier="mid"  # Expensive!
)
# Result: 1-3 seconds, $0.0001+

# After (Jev routing):
response = jev_classify(
    state=task_description,
    labels={
        "explore": "Read-only code search, file lookup, explanation",
        "implement": "Code changes, bug fixes, new features",
        "verify": "Build verification, test running, review",
        "research": "Deep research, API docs, architecture analysis",
        "orchestrate": "Complex multi-agent coordination"
    },
    question="What type of task is this?"
)
# Result: 70ms, free, with confidence score
```

#### Pattern 2: Confidence Gate (Skip LLM if Confident)

```python
# Before:
if task_type == "explore":
    route_to_explorer(task)  # Always use LLM

# After:
classification = jev_classify(task)
if classification.confidence >= 0.90:
    route_to_classified_agent(classification)  # No LLM needed
else:
    supervisor_judgment(task)  # LLM for complex cases
```

#### Pattern 3: Triage (Real-time Bug Classification)

```python
# Before:
# Bug report comes in → supervisor reads it → decides severity → routes
# Cost: 2-5 seconds, tokens

# After:
severity = jev_classify(
    state=bug_report,
    labels={
        "critical": "System down, data loss, security vulnerability",
        "high": "Major feature broken, no workaround",
        "medium": "Feature degraded, workaround exists",
        "low": "Cosmetic, minor inconvenience"
    },
    question="What is the severity of this bug?"
)
# Result: 70ms, free, immediate routing
```

#### Pattern 4: Build Error Triage (Jam Instrument Specific)

```python
# Before:
# Build fails → supervisor reads logs → decides which skill to load → routes

# After:
error_type = jev_classify(
    state=build_log_tail,
    labels={
        "ndk": "C++/NDK compilation error",
        "gradle": "Gradle build system error",
        "kotlin": "Kotlin compilation error",
        "resource": "Android resource error",
        "dependency": "Dependency resolution error"
    },
    question="What type of build error is this?"
)
# Route to correct skill instantly
```

---

## Part 5: Configuration Simplification

### 5.1 Unified Configuration File

Replace multiple config files with a single `pipa.yaml`:

```yaml
# pipa.yaml (single source of truth)
harness:
  name: "my-project"
  version: "1.0.0"

# LLM Configuration
models:
  providers:
    - name: opencode-zen
      type: cloud
      api_key: ${OPENCODE_ZEN_API_KEY}
      models: ["mimo-v2.5-free", "deepseek-v4-flash-free"]
    
    - name: kilo
      type: cloud
      api_key: ${KILO_API_KEY}
      models: ["kilo-auto/free", "stepfun/step-3.7-flash:free"]
    
    - name: typesafe
      type: cloud
      api_key: ${TYPESAFE_API_KEY}
      models: ["jev-1.13-free"]
  
  tiers:
    lowest: opencode-zen/mimo-v2.5-free
    low: opencode-zen/deepseek-v4-flash-free
    mid: opencode-zen/deepseek-v4-flash-free
    high: kilo/kilo-auto/free
    xhigh: kilo/stepfun/step-3.7-flash:free
    jev: typesafe/jev-1.13-free

# Agent Configuration
agents:
  router:
    model: jev/jev-1.13-free
    role: "Task classification and routing"
  
  supervisor:
    model: ${tier:mid}
    role: "Orchestration, conflict resolution"
  
  explorer:
    model: ${tier:lowest}
    role: "Read-only code exploration"
  
  implementer:
    model: ${tier:mid}
    role: "Code implementation"
  
  verifier:
    model: ${tier:low}
    role: "Build verification, review"
  
  researcher:
    model: ${tier:high}
    role: "Deep research"

# Rules (path-scoped)
rules:
  - path: "app/src/main/cpp/**"
    rules: ["audio-ndk.md"]
  - path: "app/src/main/res/**"
    rules: ["ui-xml.md"]
  - path: "**"
    rules: ["security.md", "testing.md", "git-workflow.md"]

# Skills (trigger-loaded)
skills:
  - name: graphify
    triggers: ["architecture", "how does X work"]
  - name: debugging
    triggers: ["bug", "error", "crash"]
  - name: code-review
    triggers: ["review", "PR", "diff"]
  - name: performance
    triggers: ["latency", "performance"]
  - name: release
    triggers: ["release", "version", "tag"]

# Memory
memory:
  vault: "vault/"
  db: "state/memory.db"
  graph: "graphify-out/graph.json"
  session: "state/SESSION.md"
  plan: "state/PLAN.md"

# Jev Integration
jev:
  enabled: true
  confidence_threshold: 0.90
  tools: ["classify", "check", "ask", "match", "score"]
  routing:
    enabled: true
    fallback_to_llm: true
```

### 5.2 Config Migration Script

```python
# tools/config/migrate.py
"""Migrate old config format to new pipa.yaml"""
import yaml
import json
from pathlib import Path

def migrate():
    """Convert old config files to new pipa.yaml"""
    config = {}
    
    # Read providers.yaml
    with open("models/providers.yaml") as f:
        config["models"] = {"providers": yaml.safe_load(f)["providers"]}
    
    # Read tiers.yaml
    with open("models/tiers.yaml") as f:
        tiers = yaml.safe_load(f)
        config["models"]["tiers"] = tiers["tiers"]
        config["agents"] = {"tiers": tiers["agent_tiers"]}
    
    # Read agent files
    for agent_file in Path("agents").glob("*.md"):
        # Extract frontmatter
        agent_config = parse_agent_frontmatter(agent_file)
        config["agents"][agent_config["name"]] = agent_config
    
    # Write pipa.yaml
    with open("pipa.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print("Migration complete: pipa.yaml created")
```

---

## Part 6: Shared Memory Architecture

### 6.1 Memory Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    SHARED MEMORY SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: Session Memory (per-session, ephemeral)               │
│  ├── state/SESSION.md                                           │
│  ├── state/PLAN.md                                              │
│  └── state/scratch/                                             │
│                                                                 │
│  Layer 2: Project Memory (per-project, persistent)              │
│  ├── .pipa/memory/decisions/                                    │
│  ├── .pipa/memory/research/                                     │
│  └── state/memory.db (SQLite)                                   │
│                                                                 │
│  Layer 3: Global Memory (cross-project, persistent)             │
│  ├── vault/decisions/                                           │
│  ├── vault/research/                                            │
│  └── vault/architecture/                                        │
│                                                                 │
│  Layer 4: Code Knowledge (auto-generated)                       │
│  ├── graphify-out/graph.json                                    │
│  └── graphify-out/GRAPH_REPORT.md                               │
│                                                                 │
│  Layer 5: Jev Decisions (cached, reusable)                      │
│  ├── state/jev_cache.db                                         │
│  └── state/jev_patterns.json                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Jev Decision Cache

Cache Jev decisions for pattern recognition:

```python
# pipa/jev_cache.py
import sqlite3
import json
from typing import Optional

class JevCache:
    """Cache Jev decisions for pattern recognition and learning"""
    
    def __init__(self, db_path: str = "state/jev_cache.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY,
                task_hash TEXT,
                task_description TEXT,
                classification TEXT,
                confidence REAL,
                route_to TEXT,
                success BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def cache_decision(self, task: str, classification: str, 
                       confidence: float, route_to: str, success: bool):
        """Cache a Jev decision for future reference"""
        task_hash = hash(task)
        self.conn.execute("""
            INSERT INTO decisions (task_hash, task_description, classification, 
                                   confidence, route_to, success)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (task_hash, task, classification, confidence, route_to, success))
        self.conn.commit()
    
    def find_similar(self, task: str, threshold: float = 0.8) -> Optional[dict]:
        """Find similar past decisions"""
        task_hash = hash(task)
        cursor = self.conn.execute("""
            SELECT classification, confidence, route_to, success
            FROM decisions
            WHERE task_hash = ? AND confidence >= ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (task_hash, threshold))
        return cursor.fetchone()
```

### 6.3 Graphify + Jev Integration

Use graphify to provide context for Jev decisions:

```python
# pipa/jev_graphify.py
import subprocess
import json

def get_code_context(query: str) -> dict:
    """Get code context from graphify for Jev decisions"""
    result = subprocess.run(
        ["graphify", "query", query],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

def jev_with_context(state: str, questions: dict) -> dict:
    """Run Jev with graphify context enrichment"""
    # Get relevant code context
    context = get_code_context(state)
    
    # Enrich state with code context
    enriched_state = f"""
    Task: {state}
    
    Relevant code context:
    {json.dumps(context, indent=2)}
    """
    
    # Run Jev with enriched context
    return jev_classify(enriched_state, questions)
```

---

## Part 7: Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

| Task | Effort | Impact |
|------|--------|--------|
| Install Jev MCP server | 1 day | Enable Jev tools |
| Add Jev provider to providers.yaml | 1 day | Model routing |
| Create `jev` tier in tiers.yaml | 1 day | Cost isolation |
| Create `@router` agent | 2 days | Core routing |
| Update `@jam-supervisor` to use router | 2 days | Integration |
| Test routing accuracy | 3 days | Validation |

**Deliverable**: Jev-powered routing that matches current LLM routing accuracy

### Phase 2: Decision Patterns (Week 3-4)

| Task | Effort | Impact |
|------|--------|--------|
| Implement confidence gates | 2 days | Skip LLM if confident |
| Add triage classifications | 2 days | Bug/feature routing |
| Build error classification | 2 days | Skill routing |
| Code quality scoring | 3 days | Pre-review checks |
| Jev decision cache | 2 days | Pattern learning |

**Deliverable**: 5+ decision patterns replacing LLM calls

### Phase 3: Configuration Simplification (Week 5-6)

| Task | Effort | Impact |
|------|--------|--------|
| Create unified `pipa.yaml` | 3 days | Single config source |
| Config migration script | 2 days | Backward compatibility |
| Update scaffold.py | 2 days | New project init |
| Update dashboard | 3 days | Config UI |
| Documentation | 2 days | User guide |

**Deliverable**: Single-file configuration, simplified setup

### Phase 4: Shared Memory (Week 7-8)

| Task | Effort | Impact |
|------|--------|--------|
| Jev decision cache | 2 days | Pattern recognition |
| Graphify + Jev integration | 3 days | Context enrichment |
| Cross-project memory | 2 days | Knowledge reuse |
| Memory visualization | 3 days | Dashboard |
| Testing & validation | 2 days | Reliability |

**Deliverable**: Shared memory system with Jev pattern learning

---

## Part 8: Success Metrics

### Performance Metrics

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| Routing latency | 1-3s | 70ms | 20-40x |
| Routing cost | $0.0001-0.001 | Free | 100% |
| Simple decision latency | 1-3s | 70ms | 20-40x |
| Token usage (routing) | 500-1000 | 0 | 100% |
| Routing accuracy | 85-90% | 95%+ | +5-10% |

### Quality Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Routing confidence calibration | None | ±5% accuracy |
| Decision cache hit rate | 0% | 60%+ |
| False positive rate | Unknown | <5% |
| User satisfaction | Subjective | Measured |

### Cost Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Monthly routing cost | $5-20 | $0 |
| Monthly simple decisions | $10-50 | $0 |
| Total model spend | $50-200 | $30-100 |

---

## Part 9: Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Jev accuracy insufficient | Medium | High | Confidence gates + LLM fallback |
| Jev latency spikes | Low | Medium | Timeout + fallback to LLM |
| Jev API downtime | Low | High | Cache + offline mode |
| Configuration complexity | Medium | Medium | Migration scripts + docs |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| User confusion | Medium | Medium | Clear documentation |
| Migration breaking changes | Low | High | Backward compatibility |
| Learning curve | Medium | Low | Training + examples |

---

## Part 10: User Experience

### Before (Current)

```
User: "Fix the build error"
↓
Supervisor (LLM, 2s): "Let me analyze this..."
↓
Routes to verifier (LLM, 3s): "Checking build..."
↓
Returns error type (LLM, 1s): "NDK error in audio.cpp"
↓
Total: 6 seconds, $0.001+
```

### After (With Jev)

```
User: "Fix the build error"
↓
Router (Jev, 70ms): classify → "ndk" (confidence: 0.95)
↓
Routes directly to audio-ndk skill
↓
Total: 70ms, free
```

### User Benefits

1. **Faster responses**: 20-40x improvement for simple tasks
2. **Lower costs**: Zero cost for routing and simple decisions
3. **More reliable**: Calibrated confidence scores
4. **Better UX**: Instant feedback on simple questions
5. **Scalable**: Can handle 100x more requests at same cost

---

## Appendix A: Jev Tool Reference

### classify
```python
jev_classify(
    state="Customer message: 'I'm frustrated'",
    labels={
        "angry": "Expressing frustration or anger",
        "neutral": "Providing information without emotion",
        "happy": "Expressing satisfaction"
    },
    question="What is the emotional tone?"
)
# Returns: {"choice": "angry", "confidence": 0.95, "probabilities": {...}}
```

### check
```python
jev_check(
    state={"temperature": 72, "humidity": 80},
    propositions={
        "is_comfortable": {
            "statement": "The environment is comfortable",
            "true": "Yes, comfortable",
            "false": "No, not comfortable"
        }
    }
)
# Returns: {"probabilities": {"is_comfortable": 0.85}, "flags": ["is_comfortable"]}
```

### match
```python
jev_match(
    query="Find a secure database",
    candidates={
        "sqlite": "File-based, good for dev",
        "postgresql": "Enterprise-grade, ACID compliant",
        "mongodb": "NoSQL, flexible schema"
    },
    question="Which database best matches?"
)
# Returns: {"best_id": "postgresql", "confidence": 1.0, "exists": 0.95}
```

---

## Appendix B: Migration Checklist

- [ ] Install Jev MCP server
- [ ] Add TYPESAFE_API_KEY to .env
- [ ] Add Jev provider to providers.yaml
- [ ] Create `jev` tier in tiers.yaml
- [ ] Create `@router` agent
- [ ] Update `@jam-supervisor` to use router
- [ ] Implement confidence gates
- [ ] Add triage classifications
- [ ] Build error classification
- [ ] Create unified pipa.yaml
- [ ] Write migration script
- [ ] Update documentation
- [ ] Test routing accuracy
- [ ] Validate cost savings
- [ ] Monitor performance

---

## Conclusion

This refactor transforms pipa harness from an LLM-only system into a **hybrid intelligence architecture** where:
- **Jev** handles fast, structured decisions (routing, triage, classification)
- **LLMs** handle complex reasoning, code generation, and explanations
- **Graphify** provides code context for better decisions
- **Shared memory** enables pattern learning and reuse

The result: **20-40x faster routing, zero cost for simple decisions, and a more reliable, deterministic system** that scales to handle 100x more requests at the same cost.

**The right path forward**: Start with Phase 1 (Foundation), validate Jev routing accuracy, then expand to decision patterns and configuration simplification. The key insight is that **Jev is not a replacement for LLMs** — it's a **fast, free pre-filter** that handles 60-80% of routing decisions, leaving LLMs for the 20-40% that need string generation or complex reasoning.
