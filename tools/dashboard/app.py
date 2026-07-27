#!/usr/bin/env python3
"""pipa_harness dashboard — FastAPI server on :8080."""
import json, os, re, subprocess, sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
STATE = ROOT / "state"
EXTENSIONS_DIR = Path.home() / ".harness_extensions_registry"
EXTENSIONS_DIR.mkdir(exist_ok=True)
AGENT_CONFIG = STATE / "agent_llm_overrides.json"
LITELLM_CONFIG = ROOT / "config" / "litellm.yaml"

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("Missing fastapi/uvicorn — install: pip install fastapi uvicorn")
    sys.exit(1)

app = FastAPI(title="pipa_harness dashboard", version="0.2.0")

# ── agent config store ───────────────────────────────────────────────────────

def load_overrides() -> dict:
    if AGENT_CONFIG.exists():
        return json.loads(AGENT_CONFIG.read_text())
    return {}

def save_overrides(data: dict) -> None:
    STATE.mkdir(exist_ok=True)
    AGENT_CONFIG.write_text(json.dumps(data, indent=2))

# ── agent discovery ─────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, m.group(2)

def discover_agents() -> list[dict]:
    agents = []
    seen = set()
    bases = [ROOT / "agents", ROOT / "templates" / "extension" / "agents"]
    for d in sorted((ROOT.parent).iterdir()):
        he = d / ".harness_extension" / "agents"
        if he.exists():
            bases.append(he)
    for base in bases:
        if not base.exists():
            continue
        for f in sorted(base.glob("*.md")):
            try:
                rel = str(f.relative_to(ROOT))
            except ValueError:
                rel = str(f)
            if rel in seen:
                continue
            seen.add(rel)
            try:
                text = f.read_text()
                fm, body = parse_frontmatter(text)
                agents.append({
                    "path": rel,
                    "name": fm.get("name", f.stem),
                    "description": fm.get("description", ""),
                    "mode": fm.get("mode", ""),
                    "model": fm.get("model", ""),
                    "permission": fm.get("permission", ""),
                })
            except Exception:
                pass
    return agents

def discover_extensions() -> list[dict]:
    exts = []
    scan_root = ROOT.parent
    if not scan_root.exists():
        scan_root = Path("/Users/noname/Development")
    for d in sorted(scan_root.iterdir()):
        if not d.is_dir():
            continue
        he = d / ".harness_extension"
        if not he.exists():
            continue
        rules = list(he.glob("rules/*.md")) if (he / "rules").exists() else []
        skills = list((he / "skills").glob("*/SKILL.md")) if (he / "skills").exists() else []
        ext_agents = list((he / "agents").glob("*.md")) if (he / "agents").exists() else []
        exts.append({
            "project": d.name,
            "path": str(he),
            "rules": len(rules),
            "skills": len(skills),
            "agents": len(ext_agents),
            "has_state": (he / "state").exists(),
            "has_vault": (he / "vault").exists(),
            "rule_names": [r.name for r in rules[:5]],
            "skill_names": [s.parent.name for s in skills[:5]],
            "agent_names": [a.name for a in ext_agents[:5]],
        })
    return exts

def cmd_ok(cmd: list[str], timeout: int = 3) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return False, str(e)

def discover_project_root() -> Optional[Path]:
    """Find the active project root from CWD or from siblings of the harness root."""
    # 1. Current working directory's git root, if it has a harness extension
    try:
        cwd = Path.cwd()
        git_root = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True, timeout=3
        ).stdout.strip()
        root = Path(git_root)
        if (root / ".harness_extension").is_dir():
            return root
    except Exception:
        pass

    # 2. Sibling directories of the harness root that contain .harness_extension
    try:
        for candidate in ROOT.parent.iterdir():
            if candidate.is_dir() and candidate != ROOT and (candidate / ".harness_extension").is_dir():
                return candidate
    except Exception:
        pass

    return None

def harness_status() -> dict:
    checks = {}

    ok, out = cmd_ok(["curl", "-sf", "http://localhost:4000/v1/models", "-H", "Authorization: Bearer sk-pipa-local"])
    checks["litellm"] = {"up": ok, "detail": f"{len(json.loads(out).get('data', []))} models" if ok else "gateway down"}

    ok, _ = cmd_ok(["curl", "-sf", "-o", "/dev/null", "http://localhost:11434"])
    checks["ollama"] = {"up": ok, "detail": "running" if ok else "not running"}

    ok, out = cmd_ok(["opencode", "--version"])
    checks["opencode"] = {"up": ok, "detail": out[:40] if ok else "not installed"}

    # Use project root for graphify (discovered from CWD or harness siblings)
    project_root = discover_project_root()
    gpath = (project_root / "graphify-out" / "graph.json") if project_root else Path.cwd() / "graphify-out" / "graph.json"
    checks["graphify"] = {"up": gpath.exists(), "detail": "graph.json present" if gpath.exists() else "no graph yet"}

    ok, _ = cmd_ok(["ls", "-d", "/Applications/Emdash.app"]) if sys.platform == "darwin" else cmd_ok(["emdash", "--version"])
    checks["emdash"] = {"up": ok, "detail": "installed" if ok else "not installed"}

    return checks

def tools_status() -> dict:
    tools = []
    for f in sorted((ROOT / "bin").glob("*")):
        if f.is_file() and f.suffix not in (".pyc",):
            tools.append({"name": f.name, "path": str(f.relative_to(ROOT)), "exec": os.access(f, os.X_OK)})
    dash = ROOT / "tools" / "dashboard" / "app.py"
    if dash.exists():
        tools.append({"name": "dashboard", "path": str(dash.relative_to(ROOT)), "exec": True})
    return {"pipa_tools": tools}

# ── kilo free models parser ──────────────────────────────────────────────────

KILO_API_URL = "https://api.kilo.ai/api/gateway/models"

def _get_kilo_api_key() -> str:
    locations = [
        ROOT / ".env",
        Path.home() / ".harness_extensions_registry" / ".env",
    ]
    for env_file in locations:
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("KILO_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "sk-pipa-local"

def fetch_kilo_free_models() -> list[dict]:
    """Query the Kilo Code API for all available models and return those
    that are free (contain ':free' in id, or are known free-tier providers)."""
    free = []
    api_key = _get_kilo_api_key()
    try:
        r = subprocess.run(
            ["curl", "-sf", KILO_API_URL,
             "-H", f"Authorization: Bearer {api_key}"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0 or not r.stdout.strip():
            return free
        data = json.loads(r.stdout)
        for m in data.get("data", []):
            mid = m.get("id", "")
            # Free models: explicit :free suffix, or known free providers
            is_free = (
                ":free" in mid or
                mid in ("openrouter/free",) or
                mid.startswith("kilo-auto/")
            )
            if is_free:
                provider = _infer_provider(mid)
                free.append({
                    "id": mid,
                    "provider": provider,
                    "model": mid,  # Use model id directly, no prefix
                    "api_base": "https://api.kilo.ai/api/gateway",
                    "api_key": "os.environ/KILO_API_KEY",
                    "description": f"{provider} — free via Kilo Code",
                })
    except Exception:
        pass
    return free

def _infer_provider(model_id: str) -> str:
    mid = model_id.lower()
    if mid.startswith("stepfun") or "step" in mid: return "StepFun"
    if mid.startswith("inclusionai") or "ling" in mid: return "InclusionAI"
    if mid.startswith("poolside") or "laguna" in mid: return "Poolside"
    if mid.startswith("nvidia") or "nemotron" in mid: return "NVIDIA"
    if mid.startswith("kwaipilot") or "kat-coder" in mid: return "Kwaipilot"
    if mid.startswith("cohere"): return "Cohere"
    if mid.startswith("openrouter"): return "OpenRouter"
    if mid.startswith("kilo-auto"): return "Kilo Code (free)"
    if mid.startswith("kimi") or mid.startswith("moonshot"): return "Kimi (Moonshot)"
    if ":free" in mid: return "Kilo Code (free)"
    return "Kilo Gateway"

def fetch_ollama_models() -> list[dict]:
    """Query the local Ollama daemon (:11434) for installed models."""
    models = []
    try:
        r = subprocess.run(
            ["curl", "-sf", "-m", "3", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode != 0 or not r.stdout.strip():
            return models
        data = json.loads(r.stdout)
        for m in data.get("models", []):
            name = m.get("name", "")
            if not name:
                continue
            models.append({
                "id": name,
                "provider": "Ollama (local)",
                "model": f"openai/{name}",
                "api_base": "http://localhost:11434/v1",
                "api_key": "ollama",
                "description": f"Local Ollama model — {name}",
            })
    except Exception:
        pass
    return models

# ── litellm config ─────────────────────────────────────────────────────────

PRESET_MODELS = [
    # Kilo Code free gateway models (openrouter + Kilo Auto)
    {"id": "kilo-auto/free", "provider": "Kilo Code (free)", "model": "kilo-auto/free", "api_base": "https://api.kilo.ai/api/gateway", "api_key": "os.environ/KILO_API_KEY", "custom_llm_provider": "openai", "description": "Kilo Auto-router — picks the best free model"},
    {"id": "openrouter/free", "provider": "Kilo Code (free)", "model": "openrouter/free", "api_base": "https://api.kilo.ai/api/gateway", "api_key": "os.environ/KILO_API_KEY", "custom_llm_provider": "openai", "description": "OpenRouter free-tier pool"},
    {"id": "step-3.7-flash:free", "provider": "Kilo Code (free)", "model": "stepfun/step-3.7-flash:free", "api_base": "https://api.kilo.ai/api/gateway", "api_key": "os.environ/KILO_API_KEY", "custom_llm_provider": "openai", "description": "Step 3.7 Flash — free via Kilo Code"},
    {"id": "ling-3.0-flash:free", "provider": "Kilo Code (free)", "model": "inclusionai/ling-3.0-flash:free", "api_base": "https://api.kilo.ai/api/gateway", "api_key": "os.environ/KILO_API_KEY", "custom_llm_provider": "openai", "description": "InclusionAI Ling 3.0 Flash — free via Kilo Code"},

    # Kimi (Moonshot) cloud models — current as of 2026-07
    {"id": "kimi-k3", "provider": "Kimi (Moonshot)", "model": "openai/kimi-k3", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Kimi K3 — flagship, 1M context, multimodal"},
    {"id": "kimi-k2.7-code", "provider": "Kimi (Moonshot)", "model": "openai/kimi-k2.7-code", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Kimi K2.7 Code — coding specialist, 256k context"},
    {"id": "kimi-k2.7-code-highspeed", "provider": "Kimi (Moonshot)", "model": "openai/kimi-k2.7-code-highspeed", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Kimi K2.7 Code High-Speed — fast coding, 256k"},
    {"id": "kimi-k2.6", "provider": "Kimi (Moonshot)", "model": "openai/kimi-k2.6", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Kimi K2.6 — vision + text, thinking mode, 256k"},
    {"id": "kimi-k2.5", "provider": "Kimi (Moonshot)", "model": "openai/kimi-k2.5", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Kimi K2.5 — general agent/code/vision, 256k"},
    {"id": "moonshot-v1-8k", "provider": "Kimi (Moonshot)", "model": "openai/moonshot-v1-8k", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Moonshot V1 — 8k context"},
    {"id": "moonshot-v1-32k", "provider": "Kimi (Moonshot)", "model": "openai/moonshot-v1-32k", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Moonshot V1 — 32k context"},
    {"id": "moonshot-v1-128k", "provider": "Kimi (Moonshot)", "model": "openai/moonshot-v1-128k", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Moonshot V1 — 128k context"},
    {"id": "moonshot-v1-8k-vision-preview", "provider": "Kimi (Moonshot)", "model": "openai/moonshot-v1-8k-vision-preview", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Moonshot V1 Vision — 8k"},
    {"id": "moonshot-v1-32k-vision-preview", "provider": "Kimi (Moonshot)", "model": "openai/moonshot-v1-32k-vision-preview", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Moonshot V1 Vision — 32k"},
    {"id": "moonshot-v1-128k-vision-preview", "provider": "Kimi (Moonshot)", "model": "openai/moonshot-v1-128k-vision-preview", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "custom_llm_provider": "openai", "description": "Moonshot V1 Vision — 128k"},

    # Ollama local models — only Qwen2.5 Coder (light + heavy) are pre-pulled
    {"id": "qwen2.5-coder:7b", "provider": "Ollama (local)", "model": "openai/qwen2.5-coder:7b", "api_base": "http://localhost:11434/v1", "api_key": "ollama", "description": "Local 7B — fast, coding"},
    {"id": "qwen2.5-coder:14b", "provider": "Ollama (local)", "model": "openai/qwen2.5-coder:14b", "api_base": "http://localhost:11434/v1", "api_key": "ollama", "description": "Local 14B — heavy, coding"},

    # Other cloud providers
    {"id": "claude-sonnet-4-5", "provider": "Anthropic (cloud)", "model": "anthropic/claude-sonnet-4-5", "api_base": "", "api_key": "os.environ/ANTHROPIC_API_KEY", "description": "Claude Sonnet 4.5 — strong reasoning"},
    {"id": "claude-haiku", "provider": "Anthropic (cloud)", "model": "anthropic/claude-3-5-haiku-20241022", "api_base": "", "api_key": "os.environ/ANTHROPIC_API_KEY", "description": "Claude Haiku — fast, cheap"},
    {"id": "gemini-2.5-flash", "provider": "Google (cloud)", "model": "gemini/gemini-2.5-flash-preview-05-20", "api_base": "", "api_key": "os.environ/GEMINI_API_KEY", "description": "Gemini 2.5 Flash — free tier available"},
    {"id": "gpt-4o-mini", "provider": "OpenAI (cloud)", "model": "openai/gpt-4o-mini", "api_base": "", "api_key": "os.environ/OPENAI_API_KEY", "description": "GPT-4o Mini — cheap, fast"},
]

def parse_litellm_config() -> dict:
    if not LITELLM_CONFIG.exists():
        return {"model_list": [], "router_settings": {}}
    text = LITELLM_CONFIG.read_text()
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except Exception:
        return {"model_list": [], "router_settings": {}}

def write_litellm_config(data: dict) -> None:
    try:
        import yaml
        LITELLM_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        LITELLM_CONFIG.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    except Exception as e:
        raise HTTPException(500, f"Failed to write config: {e}")

def update_opencode_config(alias: str, model: str) -> None:
    """Update the active project's .opencode/opencode.jsonc with model info
    for visualization. The project is discovered from CWD or from siblings of
    the harness root."""
    try:
        project_root = discover_project_root()
        if project_root is None:
            return
        opencode_path = project_root / ".opencode" / "opencode.jsonc"
        if not opencode_path.exists():
            return
        import json
        content = opencode_path.read_text()
        data = json.loads(content)

        provider = data.setdefault("provider", {}).setdefault("litellm", {})
        models = provider.setdefault("models", {})

        short = model.split("/")[-1] if "/" in model else model
        descriptive = f"{alias} - {short}"

        models[alias] = {"model": model, "description": descriptive}

        opencode_path.write_text(json.dumps(data, indent=2) + "\n")
    except Exception as e:
        print(f"update_opencode_config failed: {e}")

def reload_litellm() -> tuple[bool, str]:
    pidfile = STATE / "litellm.pid"
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            r = subprocess.run(["kill", "-HUP", str(pid)], capture_output=True, timeout=2)
            if r.returncode == 0:
                return True, "sent SIGHUP to litellm"
            return False, f"SIGHUP failed (rc={r.returncode}): {r.stderr.decode().strip()}"
        except Exception as e:
            return False, f"SIGHUP error: {e}"
    return False, "no pid file — restart gateway manually"

# ── merged presets (static + live ollama + live kilo free) ──────────────────

def _preset_group(p: dict) -> str:
    b = (p.get("api_base") or "").lower()
    if "kilo.ai" in b: return "kilo"
    if "11434" in b or "localhost" in b: return "ollama"
    if "moonshot" in b: return "kimi"
    return "other"

def all_presets() -> list[dict]:
    """Static presets + installed Ollama models + live Kilo free models,
    deduped by id, each tagged with a 'group' for the UI picker."""
    ollama_up = _ollama_is_up()
    merged, seen = [], set()
    for p in PRESET_MODELS + fetch_ollama_models() + fetch_kilo_free_models():
        if p.get("id") in seen:
            continue
        seen.add(p.get("id"))
        q = dict(p)
        q["group"] = _preset_group(q)
        if q["group"] == "ollama" and not ollama_up:
            q["disabled"] = True
            q["description"] = (q.get("description") or q.get("id", "")) + " — Ollama not running"
        merged.append(q)
    return merged

def _ollama_is_up() -> bool:
    ok, _ = cmd_ok(["curl", "-sf", "-o", "/dev/null", "http://localhost:11434"])
    return ok

# ── .env API-key store ───────────────────────────────────────────────────────

ENV_FILE = ROOT / ".env"
ENV_KEYS = ("KILO_API_KEY", "KIMI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY")

def read_env_file() -> dict:
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values

def _mask(v: str) -> str:
    return f"{v[:4]}…{v[-4:]}" if len(v) > 8 else "•••"

@app.get("/api/env-keys")
def api_get_env_keys():
    values = read_env_file()
    return JSONResponse({
        k: {"set": bool(values.get(k)), "masked": _mask(values[k]) if values.get(k) else ""}
        for k in ENV_KEYS
    })

@app.post("/api/env-keys")
def api_set_env_key(payload: dict):
    key = payload.get("key", "")
    value = (payload.get("value") or "").strip()
    if key not in ENV_KEYS:
        raise HTTPException(400, f"unknown key — allowed: {', '.join(ENV_KEYS)}")
    if not value or any(c in value for c in " \t\r\n"):
        raise HTTPException(400, "value must be non-empty and contain no whitespace")
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    out, done = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(out) + "\n")
    return JSONResponse({"ok": True, "key": key, "masked": _mask(value)})

@app.post("/api/gateway/restart")
def api_restart_gateway():
    """Kill the gateway and start a fresh one with the current .env loaded,
    so newly saved API keys take effect without leaving the dashboard."""
    import shutil, time
    pidfile = STATE / "litellm.pid"
    if pidfile.exists():
        try:
            subprocess.run(["kill", str(int(pidfile.read_text().strip()))], capture_output=True, timeout=2)
            time.sleep(1.5)
        except Exception:
            pass
    binary = shutil.which("litellm")
    if not binary:
        return JSONResponse({"ok": False, "detail": "litellm binary not found on PATH"})
    env = dict(os.environ)
    env.update({k: v for k, v in read_env_file().items() if v})
    STATE.mkdir(exist_ok=True)
    log = open(STATE / "litellm.log", "a")
    log.write("\n[restart from dashboard]\n")
    log.flush()
    proc = subprocess.Popen(
        [binary, "--config", str(LITELLM_CONFIG), "--port", "4000"],
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        env=env, cwd=str(ROOT),
    )
    pidfile.write_text(str(proc.pid))
    for _ in range(20):
        ok, _ = cmd_ok(["curl", "-sf", "-m", "2", "http://localhost:4000/v1/models",
                        "-H", "Authorization: Bearer sk-pipa-local"])
        if ok:
            return JSONResponse({"ok": True, "detail": f"gateway restarted (pid {proc.pid})"})
        time.sleep(2)
    return JSONResponse({"ok": False, "detail": "gateway did not come up — see state/litellm.log"})

@app.post("/api/ollama/start")
def api_start_ollama():
    """Best-effort attempt to start Ollama if it is installed and not running."""
    import shutil, time
    binary = shutil.which("ollama")
    if not binary:
        return JSONResponse({"ok": False, "detail": "ollama binary not found on PATH"})
    if _ollama_is_up():
        return JSONResponse({"ok": True, "detail": "ollama already running"})
    try:
        proc = subprocess.Popen([binary, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(20):
            if _ollama_is_up():
                return JSONResponse({"ok": True, "detail": f"ollama started (pid {proc.pid})"})
            time.sleep(1)
        return JSONResponse({"ok": False, "detail": "ollama did not become ready in time"})
    except Exception as e:
        return JSONResponse({"ok": False, "detail": str(e)})

@app.get("/api/models")
def api_list_models():
    cfg = parse_litellm_config()
    aliases = {}
    for entry in cfg.get("model_list", []):
        name = entry.get("model_name", "")
        params = entry.get("litellm_params", {})
        aliases[name] = {
            "model": params.get("model", ""),
            "api_base": params.get("api_base", ""),
            "api_key": params.get("api_key", ""),
        }
    for name, info in aliases.items():
        update_opencode_config(name, info.get("model", ""))
    # Merge static presets with installed Ollama models and live Kilo free models
    return JSONResponse({"aliases": aliases, "presets": all_presets()})

@app.post("/api/models/{alias}")
def api_set_model(alias: str, payload: dict):
    preset_id = payload.get("preset_id", "")
    custom_model = payload.get("model", "")
    custom_api_base = payload.get("api_base", "")
    custom_api_key = payload.get("api_key", "")

    cfg = parse_litellm_config()
    model_list = cfg.get("model_list", [])

    preset = next((p for p in all_presets() if p["id"] == preset_id), None)
    custom_llm_provider = None
    if preset:
        model = preset["model"]
        api_base = preset["api_base"]
        api_key = preset["api_key"]
        custom_llm_provider = preset.get("custom_llm_provider")
    elif custom_model:
        model = custom_model
        api_base = custom_api_base
        api_key = custom_api_key
    else:
        raise HTTPException(400, "preset_id or model required")

    updated = False
    for entry in model_list:
        if entry.get("model_name") == alias:
            if model:
                entry["litellm_params"]["model"] = model
            if api_base:
                entry["litellm_params"]["api_base"] = api_base
            if api_key:
                entry["litellm_params"]["api_key"] = api_key
            if custom_llm_provider:
                entry["litellm_params"]["custom_llm_provider"] = custom_llm_provider
            updated = True
            break

    if not updated:
        model_list.append({
            "model_name": alias,
            "litellm_params": {
                "model": model,
                "api_base": api_base or "http://localhost:11434/v1",
                "api_key": api_key or "ollama",
                **({"custom_llm_provider": custom_llm_provider} if custom_llm_provider else {}),
            }
        })

    cfg["model_list"] = model_list
    write_litellm_config(cfg)

    update_opencode_config(alias, model)

    ok, out = reload_litellm()
    return JSONResponse({"ok": True, "alias": alias, "model": model, "reload": ok, "detail": out[:200]})

@app.post("/api/models/{alias}/reset")
def api_reset_model(alias: str):
    defaults = {
        "primary": {"model": "kwaipilot/kat-coder-pro-v2.5:free", "api_base": "https://api.kilo.ai/api/gateway", "api_key": "os.environ/KILO_API_KEY", "custom_llm_provider": "openai"},
        "fast": {"model": "stepfun/step-3.7-flash:free", "api_base": "https://api.kilo.ai/api/gateway", "api_key": "os.environ/KILO_API_KEY", "custom_llm_provider": "openai"},
        "deep": {"model": "openai/kimi-k2.7-code", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY"},
        "explore": {"model": "openai/qwen2.5-coder:7b", "api_base": "http://localhost:11434/v1", "api_key": "ollama", "custom_llm_provider": "openai"},
    }
    if alias not in defaults:
        raise HTTPException(404, "unknown alias")

    cfg = parse_litellm_config()
    for entry in cfg.get("model_list", []):
        if entry.get("model_name") == alias:
            entry["litellm_params"].update(defaults[alias])
            break

    write_litellm_config(cfg)
    update_opencode_config(alias, defaults[alias]["model"])
    ok, out = reload_litellm()
    return JSONResponse({"ok": True, "alias": alias, "reload": ok, "detail": out[:200]})

# ── routes ───────────────────────────────────────────────────────────────────

@app.get("/api/status")
def api_status():
    return JSONResponse(harness_status())

@app.get("/api/agents")
def api_agents():
    return JSONResponse(discover_agents())

@app.get("/api/extensions")
def api_extensions():
    return JSONResponse(discover_extensions())

@app.get("/api/tools")
def api_tools():
    return JSONResponse(tools_status())

@app.get("/api/agent-config")
def api_agent_config():
    return JSONResponse(load_overrides())

@app.post("/api/agent-config/{agent_path:path}")
def api_set_agent(agent_path: str, payload: dict):
    overrides = load_overrides()
    model = payload.get("model", "")
    if model:
        overrides[agent_path] = {"model": model}
    else:
        overrides.pop(agent_path, None)
    save_overrides(overrides)
    return JSONResponse({"ok": True, "model": model})

@app.put("/api/agent-file/{agent_path:path}")
def api_edit_agent_file(agent_path: str, payload: dict):
    candidate = ROOT / agent_path
    if not candidate.exists():
        candidate = Path(agent_path)
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(404, "agent file not found")
    model = payload.get("model", "")
    text = candidate.read_text()
    if model:
        new_text = re.sub(r"^(model:\s*).*$", r"\1" + model, text, count=1, flags=re.MULTILINE)
        if new_text == text:
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    new_text = parts[0] + "---\nmodel: " + model + "\n" + parts[1].lstrip("\n") + "---" + parts[2]
                else:
                    new_text = "---\nmodel: " + model + "\n---\n" + text
            else:
                new_text = "---\nmodel: " + model + "\n---\n" + text
    else:
        new_text = re.sub(r"^model:\s*.*\n?", "", text, count=1, flags=re.MULTILINE)
        new_text = re.sub(r"---\s*\n\s*---\s*\n", "\n", new_text)
    candidate.write_text(new_text)
    return JSONResponse({"ok": True, "model": model, "file": str(candidate)})

# ── new harness features ─────────────────────────────────────────────────────

@app.get("/api/traces")
def api_traces():
    import sqlite3
    db = STATE / "traces.db"
    if not db.exists():
        return JSONResponse({"traces": []})
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT agent, task_type, status, tokens, latency_ms, created_at FROM traces ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return JSONResponse({"traces": [dict(zip(["agent","task_type","status","tokens","latency_ms","created_at"], r)) for r in rows]})

@app.get("/api/evals")
def api_evals():
    import subprocess, json
    try:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "agent_evals" / "run.py")], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return JSONResponse({"ok": True, "detail": "All evals passed"})
        return JSONResponse({"ok": False, "detail": r.stdout[:500]})
    except Exception as e:
        return JSONResponse({"ok": False, "detail": str(e)})

@app.get("/api/checkpoints")
def api_checkpoints():
    plan = STATE / "PLAN.md"
    if not plan.exists():
        return JSONResponse({"checkpoints": []})
    text = plan.read_text()
    cp_section = re.search(r"## Checkpoints\n(.*?)(?:\n## |\Z)", text, re.DOTALL)
    if not cp_section:
        return JSONResponse({"checkpoints": []})
    lines = [l.strip() for l in cp_section.group(1).strip().splitlines() if l.strip() and not l.startswith("#")]
    return JSONResponse({"checkpoints": lines})

@app.get("/api/summaries")
def api_summaries():
    summaries_dir = STATE / "summaries"
    if not summaries_dir.exists():
        return JSONResponse({"summaries": []})
    files = sorted(summaries_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[:20]
    return JSONResponse({"summaries": [{"name": f.name, "path": str(f.relative_to(ROOT)), "mtime": f.stat().st_mtime} for f in files]})

@app.get("/api/memory")
def api_memory():
    import sqlite3
    db = STATE / "memory.db"
    if not db.exists():
        return JSONResponse({"status": "not indexed", "count": 0})
    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    scopes = conn.execute("SELECT scope, COUNT(*) FROM memories GROUP BY scope").fetchall()
    conn.close()
    return JSONResponse({"status": "indexed", "count": count, "scopes": dict(scopes)})

@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "tools" / "dashboard" / "static" / "index.html").read_text()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
