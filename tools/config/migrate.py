#!/usr/bin/env python3
"""Config Migration - Convert old config files to unified pipa.yaml"""
import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any


def parse_agent_frontmatter(filepath: Path) -> Dict[str, Any]:
    """Parse YAML frontmatter from agent markdown file"""
    content = filepath.read_text()
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 2:
            try:
                return yaml.safe_load(parts[1])
            except yaml.YAMLError:
                pass
    return {"name": filepath.stem}


def migrate_providers(config: Dict) -> Dict:
    """Read providers.yaml and add to config"""
    providers_file = Path("models/providers.yaml")
    if providers_file.exists():
        with open(providers_file) as f:
            data = yaml.safe_load(f)
            config["models"]["providers"] = data.get("providers", [])
    return config


def migrate_tiers(config: Dict) -> Dict:
    """Read tiers.yaml and add to config"""
    tiers_file = Path("models/tiers.yaml")
    if tiers_file.exists():
        with open(tiers_file) as f:
            data = yaml.safe_load(f)
            config["models"]["tier_meta"] = data.get("tiers", {})
            config["agents"]["_tiers"] = data.get("agent_tiers", {})
    return config


def migrate_agents(config: Dict) -> Dict:
    """Read agent files and add to config"""
    agents_dir = Path("agents")
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*.md"):
            agent_config = parse_agent_frontmatter(agent_file)
            name = agent_config.pop("name", agent_file.stem)
            config["agents"][name] = agent_config
    return config


def migrate_skills(config: Dict) -> Dict:
    """Read skill files and add to config"""
    skills_dir = Path("skills")
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    content = skill_file.read_text()
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 2:
                            try:
                                skill_meta = yaml.safe_load(parts[1])
                                config["skills"].append({
                                    "name": skill_meta.get("name", skill_dir.name),
                                    "triggers": skill_meta.get("triggers", []),
                                    "path": str(skill_file),
                                })
                            except yaml.YAMLError:
                                pass
    return config


def migrate_rules(config: Dict) -> Dict:
    """Read rule files and add to config"""
    rules_dir = Path("rules")
    if rules_dir.exists():
        for rule_file in rules_dir.glob("*.md"):
            config["rules"]["global"].append(rule_file.name)
    return config


def migrate() -> Dict[str, Any]:
    """Main migration function"""
    config = {
        "harness": {
            "name": "pipa-harness",
            "version": "2.0.0",
            "description": "Project-agnostic agent harness with Jev + LLM hybrid routing",
        },
        "models": {"providers": [], "tiers": {}, "tier_meta": {}},
        "agents": {},
        "rules": {"global": [], "path_scoped": []},
        "skills": [],
        "memory": {
            "vault": "vault/",
            "db": "state/memory.db",
            "graph": "graphify-out/graph.json",
            "session": "state/SESSION.md",
            "plan": "state/PLAN.md",
            "jev_cache": "state/jev_cache.db",
        },
        "jev": {
            "enabled": True,
            "confidence_threshold": 0.90,
            "routing": {"enabled": True, "fallback_to_llm": True},
        },
    }

    print("Migrating config files to pipa.yaml...")
    config = migrate_providers(config)
    print(f"  - Migrated {len(config['models']['providers'])} providers")

    config = migrate_tiers(config)
    print(f"  - Migrated {len(config['models']['tier_meta'])} tiers")

    config = migrate_agents(config)
    print(f"  - Migrated {len(config['agents'])} agents")

    config = migrate_skills(config)
    print(f"  - Migrated {len(config['skills'])} skills")

    config = migrate_rules(config)
    print(f"  - Migrated {len(config['rules']['global'])} rules")

    # Write output
    output_file = Path("pipa.yaml")
    with open(output_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"\nMigration complete: {output_file}")
    return config


if __name__ == "__main__":
    migrate()
