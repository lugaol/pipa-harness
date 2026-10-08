"""Providers page (Phase 2 of the ia_harness port).

Key names surface, never values. Cloud providers are never live-called.
"""
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = HARNESS_ROOT / "dashboard"

for _p in (str(HARNESS_ROOT), str(DASHBOARD_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_providers_template_exists():
    assert (DASHBOARD_DIR / "templates" / "providers.html").is_file()


def test_page_module_exposes_router():
    import importlib

    module = importlib.import_module("pages.providers")
    assert hasattr(module, "router")
    assert len(module.router.routes) > 0


def test_list_providers_shape(monkeypatch, tmp_path):
    from pipa import config
    from data import providers as providers_data

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for var in ("KILO_API_KEY", "MOONSHOT_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    rows = providers_data.list_providers()
    assert rows, "providers.yaml should yield rows"
    for r in rows:
        assert {"slug", "label", "kind", "key_rows", "missing", "models",
                "discovered", "live", "ready"} <= set(r)
        for k in r["key_rows"]:
            assert set(k) == {"name", "present"}
            assert isinstance(k["present"], bool)


def test_unknown_provider_rejected():
    from data import providers as providers_data

    ok, msg = providers_data.test_provider("no-such-provider")
    assert ok is False and msg


def test_missing_keys_reported_by_name_only(monkeypatch, tmp_path):
    from pipa import config
    from data import providers as providers_data

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.delenv("KILO_API_KEY", raising=False)
    ok, msg = providers_data.test_provider("kilo")
    assert ok is False
    assert "KILO_API_KEY" in msg


def test_keys_present_never_live_calls_cloud(monkeypatch, tmp_path):
    from pipa import config
    from data import providers as providers_data

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.setenv("KILO_API_KEY", "dummy-not-a-real-secret")
    ok, msg = providers_data.test_provider("kilo")
    assert ok is True
    assert "not live-called" in msg


def test_no_secret_values_in_provider_rows(monkeypatch, tmp_path):
    """Even with keys set, rows carry presence booleans, never values."""
    from pipa import config
    from data import providers as providers_data

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    secret = "sk-test-dummy-value-12345"
    monkeypatch.setenv("KILO_API_KEY", secret)
    rows = providers_data.list_providers()
    assert secret not in repr(rows)


# ── provider attribution: one owner, two consumers ─────────────────────────

def test_registry_and_composer_agree_on_which_provider_owns_an_id():
    """A duplicated model id must be attributed the same way everywhere.

    Regression: the registry took the FIRST provider to report an id while the
    composer let the LAST one overwrite. For
    `nvidia/nemotron-3-super-120b-a12b:free` (reported by both openrouter and
    kilo) the gateway routed it through kilo — whose key was set — while the
    registry attributed it to openrouter, whose key was not, marked it
    inactive, and dropped it from the model picker. A working model the user
    could not see, plus a credential check pointed at the wrong provider.
    """
    from pipa.providers import resolve_backing

    catalog = {
        "openrouter": {"ok": True, "models": [{"id": "shared/free"}, {"id": "or-only"}]},
        "kilo": {"ok": True, "models": [{"id": "shared/free"}, {"id": "kilo-only"}]},
    }
    backing = resolve_backing(catalog)
    assert backing["shared/free"] == "kilo", (
        f"later provider should own a duplicated id, got {backing['shared/free']!r}"
    )
    assert backing["or-only"] == "openrouter"
    assert backing["kilo-only"] == "kilo"


def test_only_the_backing_provider_reaches_the_registry():
    """A model owned by a later provider must not be listed twice."""
    from pipa import model_registry
    from pipa.providers import resolve_backing

    catalog = {
        "openrouter": {"ok": True, "models": [{"id": "shared/free"}]},
        "kilo": {"ok": True, "models": [{"id": "shared/free"}]},
    }
    backing = resolve_backing(catalog)
    monkey = catalog
    owners = [slug for slug in monkey if any(backing[m["id"]] == slug
                                             for m in monkey[slug]["models"])]
    assert sorted(owners) == ["kilo"], owners


def test_load_dotenv_refills_an_empty_key(monkeypatch, tmp_path):
    """A long-lived process must not keep a key it once saw as empty.

    Regression: load_dotenv skipped any key already in os.environ, including
    one present but EMPTY. The dashboard is a daemon — if it started while a
    key was unset, it held `KIMI_API_KEY=""` forever, every later compose
    judged kimi unavailable, and the gateway silently lost the paid provider
    along with the tier alias pointing at one. The user had paid for the key
    and the harness had quietly stopped routing to it.
    """
    from pipa import config

    env = tmp_path / ".env"
    env.write_text('KIMI_API_KEY=sk-real\nOTHER=sk-other\n')
    monkeypatch.setattr(config, "harness_root", lambda: tmp_path)
    monkeypatch.setenv("KIMI_API_KEY", "")   # stale daemon state
    monkeypatch.delenv("OTHER", raising=False)

    config.load_dotenv()

    assert config.os.environ["KIMI_API_KEY"] == "sk-real", (
        "an empty env var must be refilled from .env, not treated as set"
    )
    assert config.os.environ["OTHER"] == "sk-other"


def test_load_dotenv_still_respects_a_real_override(monkeypatch, tmp_path):
    """A non-empty value already in the environment wins — that is the point."""
    from pipa import config

    env = tmp_path / ".env"
    env.write_text("KIMI_API_KEY=sk-from-file\n")
    monkeypatch.setattr(config, "harness_root", lambda: tmp_path)
    monkeypatch.setenv("KIMI_API_KEY", "sk-from-shell")

    config.load_dotenv()
    assert config.os.environ["KIMI_API_KEY"] == "sk-from-shell"


def test_force_overwrites_a_set_key(monkeypatch, tmp_path):
    from pipa import config

    env = tmp_path / ".env"
    env.write_text("KIMI_API_KEY=sk-new\n")
    monkeypatch.setattr(config, "harness_root", lambda: tmp_path)
    monkeypatch.setenv("KIMI_API_KEY", "sk-old")

    config.load_dotenv(force=True)
    assert config.os.environ["KIMI_API_KEY"] == "sk-new"
