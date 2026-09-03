"""Service management: installers, ollama/litellm/dashboard lifecycle.

Python port of bin/pipa-up.sh. Idempotent: safe to re-run anytime.
Platforms: macOS (brew for GUI apps) and Linux (best effort).
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import config

OS = platform.system()  # Darwin | Linux
ARCH = platform.machine()  # arm64 | x86_64


class Reporter:
    def ok(self, msg: str) -> None:
        print(f"  [ok] {msg}")

    def add(self, msg: str) -> None:
        print(f"  [++] {msg}")

    def warn(self, msg: str) -> None:
        print(f"  [!!] {msg}", file=sys.stderr)


def have(binary: str) -> bool:
    return shutil.which(binary) is not None


def _run(cmd: list[str] | str, shell: bool = False, timeout: int | None = None) -> int:
    try:
        return subprocess.run(cmd, shell=shell, timeout=timeout).returncode
    except Exception:
        return 1


def _http_up(url: str, timeout: float = 2.0, headers: dict | None = None) -> bool:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False


def _wait_http(url: str, seconds: int, headers: dict | None = None) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _http_up(url, headers=headers):
            return True
        time.sleep(2)
    return False


def _pid_alive(pid_file: Path) -> bool:
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _start_daemon(cmd: list[str], log: Path, pid_file: Path,
                  extra_env: dict | None = None) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    env = None
    if extra_env:
        env = dict(os.environ)
        env.update(extra_env)
    with log.open("ab") as lf:
        proc = subprocess.Popen(
            cmd, stdout=lf, stderr=subprocess.STDOUT,
            start_new_session=True, env=env,
        )
    pid_file.write_text(str(proc.pid))
    return proc.pid


# ── installers ──────────────────────────────────────────────────────────────

def ensure_uv(rep: Reporter) -> bool:
    if have("uv"):
        rep.ok("uv")
        return True
    rep.add("installing uv...")
    _run("curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True)
    os.environ["PATH"] = f"{Path.home() / '.local' / 'bin'}:{os.environ['PATH']}"
    if have("uv"):
        rep.ok("uv installed")
        return True
    rep.warn("uv install failed")
    return False


def ensure_ollama(rep: Reporter) -> bool:
    if have("ollama"):
        rep.ok("ollama")
        return True
    rep.add("installing ollama...")
    if OS == "Darwin" and have("brew"):
        if _run(["brew", "install", "ollama"]) != 0:
            _run(["brew", "install", "--cask", "ollama"])
    elif OS == "Linux":
        _run("curl -fsSL https://ollama.com/install.sh | sh", shell=True)
    else:
        rep.warn("install ollama manually: https://ollama.com/download")
        return False
    if have("ollama"):
        rep.ok("ollama installed")
        return True
    rep.warn("ollama install failed")
    return False


def ensure_python_deps(rep: Reporter) -> bool:
    """Ensure interpreter deps the CLI gateway/dashboard need (pyyaml, fastapi,
    uvicorn, jinja2). Tolerates Debian/Ubuntu PEP 668 externally-managed envs
    by retrying with --break-system-packages; never raises into callers.
    """
    wanted = {
        "yaml": "pyyaml",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "jinja2": "jinja2",
    }
    missing = [pkg for mod, pkg in wanted.items() if _run(
        [sys.executable, "-c", f"import {mod}"], timeout=15
    ) != 0]
    if not missing:
        rep.ok("python deps (yaml fastapi uvicorn jinja2)")
        return True
    rep.add(f"installing python deps: {', '.join(missing)}...")
    ok_all = True
    for pkg in missing:
        base = [sys.executable, "-m", "pip", "install", "--user", "--no-cache-dir", pkg]
        if _run(base, timeout=180) != 0:
            # PEP 668 externally-managed (Debian/Ubuntu 12.04+, Fedora 38+)
            if _run(base[:-1] + ["--break-system-packages"] + base[-1:], timeout=180) != 0:
                rep.warn(f"{pkg}: install failed — install manually or use a venv")
                ok_all = False
    # re-probe
    still = [mod for mod in wanted if _run(
        [sys.executable, "-c", f"import {mod}"], timeout=15
    ) != 0]
    if still:
        rep.warn(f"python deps still missing after install: {', '.join(still)}")
        return False
    rep.ok("python deps installed")
    return True


def ensure_litellm(rep: Reporter) -> bool:
    if have("litellm"):
        rep.ok("litellm")
        return True
    rep.add("installing litellm[proxy]...")
    if _run(["uv", "tool", "install", "litellm[proxy]"]) != 0:
        _run(["uv", "tool", "install", "--force", "litellm[proxy]"])
    if have("litellm"):
        rep.ok("litellm installed")
        return True
    rep.warn("litellm install failed")
    return False


def ensure_graphify(rep: Reporter) -> bool:
    if have("graphify") and have("graphify-mcp"):
        out = subprocess.run(
            ["uv", "tool", "dir"], capture_output=True, text=True
        )
        venv_py = Path(out.stdout.strip()) / "graphifyy" / "bin" / "python"
        probe = subprocess.run(
            [str(venv_py), "-c", "import mcp"], capture_output=True
        ) if venv_py.is_file() else None
        if probe is None or probe.returncode == 0:
            rep.ok("graphify (+mcp)")
            return True
        rep.add("adding mcp to graphify tool env...")
        _run(["uv", "tool", "install", "graphifyy", "--with", "mcp", "--reinstall"])
        rep.ok("graphify (+mcp)")
        return True
    rep.add("installing graphifyy (+mcp)...")
    _run(["uv", "tool", "install", "graphifyy", "--with", "mcp"])
    if have("graphify"):
        rep.ok("graphify installed")
        return True
    rep.warn("graphify install failed")
    return False


def ensure_obsidian(rep: Reporter, gui: bool = True) -> bool:
    if not gui:
        return True
    if OS == "Darwin" and Path("/Applications/Obsidian.app").is_dir():
        rep.ok("obsidian")
        return True
    if OS == "Linux" and (
        have("obsidian")
        or _run(["flatpak", "info", "md.obsidian.Obsidian"]) == 0
    ):
        rep.ok("obsidian")
        return True
    rep.add("installing obsidian...")
    if OS == "Darwin" and have("brew"):
        _run(["brew", "install", "--cask", "obsidian"])
    elif OS == "Linux":
        if have("flatpak"):
            _run(["flatpak", "install", "-y", "flathub", "md.obsidian.Obsidian"])
        elif have("snap"):
            _run(["sudo", "snap", "install", "obsidian", "--classic"])
        else:
            rep.warn("install obsidian manually: https://obsidian.md/download")
            return False
    else:
        rep.warn("install obsidian manually: https://obsidian.md/download")
        return False
    rep.ok("obsidian installed")
    return True


def ensure_emdash(rep: Reporter, gui: bool = True) -> bool:
    if not gui:
        return True
    if OS == "Darwin":
        import glob
        if glob.glob("/Applications/[Ee]mdash.app"):
            rep.ok("emdash")
            return True
    if OS == "Linux" and have("emdash"):
        rep.ok("emdash")
        return True
    rep.add("installing emdash from GitHub releases...")
    api = "https://api.github.com/repos/generalaction/emdash/releases/latest"
    try:
        with urllib.request.urlopen(api, timeout=15) as r:
            assets = json.load(r).get("assets", [])
        urls = [a["browser_download_url"] for a in assets]
    except Exception:
        urls = []
    if OS == "Darwin":
        pat = "arm64.dmg" if ARCH == "arm64" else "x64.dmg"
        url = next((u for u in urls if u.lower().endswith(pat)), None)
        if url:
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                dmg = Path(tmp) / "emdash.dmg"
                urllib.request.urlretrieve(url, dmg)
                _run(["hdiutil", "attach", "-nobrowse", "-quiet", str(dmg)])
                import glob
                apps = glob.glob("/Volumes/*/*.app")
                if apps:
                    _run(["cp", "-R", apps[0], "/Applications/"])
                    _run(["hdiutil", "detach", "-quiet", str(Path(apps[0]).parent)])
                rep.ok("emdash installed")
                return True
        rep.warn("could not resolve emdash dmg — https://github.com/generalaction/emdash/releases")
        return False
    url = next((u for u in urls if u.lower().endswith("x86_64.appimage")), None)
    if url:
        dest = Path.home() / ".local" / "bin" / "emdash"
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, dest)
        dest.chmod(0o755)
        rep.ok("emdash installed (~/.local/bin/emdash)")
        return True
    rep.warn("could not resolve emdash AppImage — https://github.com/generalaction/emdash/releases")
    return False


def ensure_dashboard(rep: Reporter, root: Path) -> bool:
    state = config.state_dir()
    pid_file = state / "dashboard.pid"
    if _pid_alive(pid_file):
        rep.ok(f"dashboard already running (:{config.DASHBOARD_PORT})")
        return True
    rep.add(f"starting dashboard (:{config.DASHBOARD_PORT})...")
    _start_daemon(
        ["python3", str(root / "dashboard" / "server.py")],
        state / "dashboard.log",
        pid_file,
    )
    time.sleep(1)
    if _pid_alive(pid_file):
        rep.ok(f"dashboard up (http://localhost:{config.DASHBOARD_PORT})")
        return True
    rep.warn(f"dashboard failed to start — see {state / 'dashboard.log'}")
    return False


# ── services ────────────────────────────────────────────────────────────────

def start_ollama(rep: Reporter) -> bool:
    state = config.state_dir()
    if _http_up(config.OLLAMA_URL):
        rep.ok("ollama serve already running")
        return True
    rep.add("starting ollama serve...")
    _start_daemon(["ollama", "serve"], state / "ollama.log", state / "ollama.pid")
    if _wait_http(config.OLLAMA_URL, 20):
        rep.ok(f"ollama serve up (:{config.OLLAMA_PORT})")
        return True
    rep.warn(f"ollama serve did not come up — see {state / 'ollama.log'}")
    return False


def pull_models(rep: Reporter, litellm_config: Path, root: Path) -> None:
    if not have("ollama") or not _http_up(config.OLLAMA_URL):
        return
    script = root / "tools" / "ollama" / "pull_models.py"
    out = subprocess.run(
        ["python3", str(script), str(litellm_config)], capture_output=True, text=True
    )
    models = sorted(set(out.stdout.split()))
    listed = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout
    present = {line.split()[0] for line in listed.splitlines()[1:] if line.split()}
    for m in models:
        if m in present:
            rep.ok(f"model present: {m}")
        else:
            rep.add(f"pulling model: {m} (large download)...")
            if _run(["ollama", "pull", m]) == 0:
                rep.ok(f"pulled {m}")
            else:
                rep.warn(f"pull failed: {m}")


def start_litellm(rep: Reporter, litellm_config: Path) -> bool:
    state = config.state_dir()
    url = f"{config.LITELLM_URL}/v1/models"
    headers = {"Authorization": f"Bearer {config.LITELLM_KEY}"}
    if _http_up(url, headers=headers):
        rep.ok(f"litellm gateway already running (:{config.LITELLM_PORT})")
        return True
    rep.add(f"starting litellm gateway (:{config.LITELLM_PORT})...")
    spend_log = config.state_dir() / "spend.ndjson"
    _start_daemon(
        ["litellm", "--config", str(litellm_config), "--port", str(config.LITELLM_PORT)],
        state / "litellm.log",
        state / "litellm.pid",
        extra_env={"PIPA_SPEND_LOG": str(spend_log)},
    )
    if _wait_http(url, 30, headers=headers):
        rep.ok(f"litellm gateway up (:{config.LITELLM_PORT})")
        return True
    rep.warn(f"gateway did not come up — see {state / 'litellm.log'}")
    return False


def stop_services() -> list[str]:
    """Stop services started by pipa (pid files under the harness state dir)."""
    state = config.state_dir()
    stopped = []
    for name in ("litellm", "ollama", "dashboard"):
        pid_file = state / f"{name}.pid"
        if _pid_alive(pid_file):
            try:
                os.kill(int(pid_file.read_text().strip()), 15)
                stopped.append(name)
            except Exception:
                pass
        pid_file.unlink(missing_ok=True)
    return stopped


def persist_path(rep: Reporter, root: Path) -> None:
    line = f'export PATH="{root}/bin:$HOME/.opencode/bin:$HOME/.local/bin:$PATH"'
    shell = os.path.basename(os.environ.get("SHELL", ""))
    for rc in (Path.home() / ".zshrc", Path.home() / ".bashrc"):
        if rc.suffix == ".zshrc" and not (rc.exists() or shell == "zsh"):
            continue
        if rc.suffix == ".bashrc" and not (rc.exists() or shell == "bash"):
            continue
        if rc.exists() and f"{root}/bin" in rc.read_text():
            rep.ok(f"PATH already in {rc.name}")
            continue
        with rc.open("a") as f:
            f.write(f"\n# pipa_harness (pipa CLI + runtimes + uv tools)\n{line}\n")
        rep.add(f"PATH added to {rc.name} (open a new terminal to pick it up)")
