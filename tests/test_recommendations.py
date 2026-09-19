"""pipa.recommendations — derived recommended tiers/models per agent."""
from pipa.model_registry import TIER_ALIASES, normalize_tier
from pipa.recommendations import recommended_model, recommended_tier, recommended_tiers
from pipa.runtime import AGENT_MODEL_MAP


def test_recommended_tier_matches_agent_defaults():
    for agent, tier in AGENT_MODEL_MAP.items():
        assert recommended_tier(agent) == normalize_tier(tier)


def test_unknown_agent_has_no_recommendation():
    assert recommended_tier("no-such-agent") == ""
    assert recommended_model("no-such-agent") == ""


def test_recommended_tiers_all_valid():
    tiers = recommended_tiers()
    assert tiers, "every mapped agent should have a recommendation"
    for agent, tier in tiers.items():
        assert tier in TIER_ALIASES, f"{agent} -> {tier!r}"


def test_recommended_model_empty_when_tier_unassigned(monkeypatch):
    import pipa.model_registry as reg

    monkeypatch.setattr(reg, "tier_resolution", lambda: {})
    assert recommended_model("dev") == ""


def test_recommended_model_resolves_display(monkeypatch):
    import pipa.model_registry as reg

    class Entry:
        display = "DeepSeek V4 Flash"
        active = True

    monkeypatch.setattr(reg, "tier_resolution", lambda: {"mid": Entry()})
    assert recommended_model("dev") == "DeepSeek V4 Flash"
