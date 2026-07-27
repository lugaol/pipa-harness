#!/usr/bin/env python3
# pipa-pull-ollama-models.py — extract unique Ollama model tags from a LiteLLM config.
#
# Usage: pipa-pull-ollama-models.py <litellm-config.yaml>
# Prints one model tag per line, e.g.:
#   qwen2.5-coder:7b
#   qwen2.5-coder:14b
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config/litellm.yaml")
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} not found", file=sys.stderr)
        return 1

    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    models = set()
    for entry in cfg.get("model_list", []):
        params = entry.get("litellm_params", {})
        api_base = params.get("api_base", "")
        model = params.get("model", "")
        if "localhost:11434" in api_base and model.startswith("openai/"):
            models.add(model.replace("openai/", ""))

    for m in sorted(models):
        print(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
