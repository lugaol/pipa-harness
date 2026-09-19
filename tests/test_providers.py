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
