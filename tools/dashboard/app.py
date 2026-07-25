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
        })
    return exts

def cmd_ok(cmd: list[str], timeout: int = 3) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return False, str(e)

def harness_status() -> dict:
    checks = {}

    ok, out = cmd_ok(["curl", "-sf", "http://localhost:4000/v1/models", "-H", "Authorization: Bearer sk-pipa-local"])
    checks["litellm"] = {"up": ok, "detail": out[:120] if ok else "gateway down"}

    ok, _ = cmd_ok(["curl", "-sf", "-o", "/dev/null", "http://localhost:11434"])
    checks["ollama"] = {"up": ok, "detail": "running" if ok else "not running"}

    ok, _ = cmd_ok(["opencode", "--version"])
    checks["opencode"] = {"up": ok, "detail": out[:40] if ok else "not installed"}

    gpath = ROOT.parent / "graphify-out" / "graph.json"
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

# ── litellm config ─────────────────────────────────────────────────────────

PRESET_MODELS = [
    {"id": "step-3.7-flash:free", "provider": "StepFun (cloud)", "model": "openai/stepfun/step-3.7-flash:free", "api_base": "https://api.stepfun.com/v1", "api_key": "os.environ/STEPFUN_API_KEY", "description": "Step 3.7 Flash — free tier"},
    {"id": "gpt-oss:20b", "provider": "Ollama (local)", "model": "openai/gpt-oss:20b", "api_base": "http://localhost:11434/v1", "api_key": "ollama", "description": "Local 20B — primary coding"},
    {"id": "qwen3:8b", "provider": "Ollama (local)", "model": "openai/qwen3:8b", "api_base": "http://localhost:11434/v1", "api_key": "ollama", "description": "Local 8B — fast, tool-calling"},
    {"id": "kimi-k2:free", "provider": "Kimi (cloud)", "model": "openai/kimi-k2", "api_base": "https://api.moonshot.cn/v1", "api_key": "os.environ/KIMI_API_KEY", "description": "Kimi free tier"},
    {"id": "claude-sonnet-4-5", "provider": "Anthropic (cloud)", "model": "anthropic/claude-sonnet-4-5", "api_base": "", "api_key": "os.environ/ANTHROPIC_API_KEY", "description": "Claude Sonnet — strong reasoning"},
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

def reload_litellm() -> tuple[bool, str]:
    pidfile = STATE / "litellm.pid"
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            subprocess.run(["kill", "-HUP", str(pid)], capture_output=True, timeout=2)
            return True, "sent SIGHUP to litellm"
        except Exception:
            pass
    return False, "no pid file — restart gateway manually"

@app.post("/api/gateway/restart")
def api_restart_gateway():
    pidfile = STATE / "litellm.pid"
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            subprocess.run(["kill", str(pid)], capture_output=True, timeout=2)
        except Exception:
            pass
    import time
    time.sleep(1)
    cfg = parse_litellm_config()
    model_list = cfg.get("model_list", [])
    if not model_list:
        return JSONResponse({"ok": False, "detail": "no models in config"})
    log = STATE / "litellm.log"
    with open(log, "a") as lf:
        lf.write("\n[manual restart from dashboard]\n")
    return JSONResponse({"ok": True, "detail": "stopped — run pipa-up.sh to restart"})

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
    return JSONResponse({"aliases": aliases, "presets": PRESET_MODELS})

@app.post("/api/models/{alias}")
def api_set_model(alias: str, payload: dict):
    preset_id = payload.get("preset_id", "")
    custom_model = payload.get("model", "")
    custom_api_base = payload.get("api_base", "")
    custom_api_key = payload.get("api_key", "")

    cfg = parse_litellm_config()
    model_list = cfg.get("model_list", [])

    preset = next((p for p in PRESET_MODELS if p["id"] == preset_id), None)
    if preset:
        model = preset["model"]
        api_base = preset["api_base"]
        api_key = preset["api_key"]
    elif custom_model:
        model = custom_model
        api_base = custom_api_base
        api_key = custom_api_key
    else:
        raise HTTPException(400, "preset_id or model required")

    updated = False
    for entry in model_list:
        if entry.get("model_name") == alias:
            entry["litellm_params"]["model"] = model
            entry["litellm_params"]["api_base"] = api_base
            entry["litellm_params"]["api_key"] = api_key
            updated = True
            break

    if not updated:
        model_list.append({
            "model_name": alias,
            "litellm_params": {
                "model": model,
                "api_base": api_base,
                "api_key": api_key,
            }
        })

    cfg["model_list"] = model_list
    write_litellm_config(cfg)

    ok, out = reload_litellm()
    return JSONResponse({"ok": True, "alias": alias, "model": model, "reload": ok, "detail": out[:200]})

@app.post("/api/models/{alias}/reset")
def api_reset_model(alias: str):
    defaults = {
        "primary": {"model": "openai/stepfun/step-3.7-flash:free", "api_base": "https://api.stepfun.com/v1", "api_key": "os.environ/STEPFUN_API_KEY"},
        "fast": {"model": "openai/qwen3:8b", "api_base": "http://localhost:11434/v1", "api_key": "ollama"},
        "deep": {"model": "openai/gpt-oss:20b", "api_base": "http://localhost:11434/v1", "api_key": "ollama"},
        "explore": {"model": "openai/qwen3:8b", "api_base": "http://localhost:11434/v1", "api_key": "ollama"},
    }
    if alias not in defaults:
        raise HTTPException(404, "unknown alias")

    cfg = parse_litellm_config()
    for entry in cfg.get("model_list", []):
        if entry.get("model_name") == alias:
            entry["litellm_params"].update(defaults[alias])
            break

    write_litellm_config(cfg)
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
        if new_text == text and "model:" not in text:
            new_text = "---\nmodel: " + model + "\n---\n" + text
    else:
        new_text = re.sub(r"^(model:\s*).*$", r"\1", text, count=1, flags=re.MULTILINE)
    candidate.write_text(new_text)
    return JSONResponse({"ok": True, "model": model, "file": str(candidate)})

@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "tools" / "dashboard" / "static" / "index.html").read_text()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
