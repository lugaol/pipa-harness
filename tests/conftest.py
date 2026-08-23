"""Test bootstrap: make `import pipa` work regardless of cwd, with a
deterministic environment (gateway constants must not depend on the
developer's shell exports).
"""
import os
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]

# Clear env overrides before `pipa.config` is imported anywhere, so
# LITELLM_KEY / LITELLM_URL / harness_root() resolve to repo defaults.
for _var in ("PIPA_ROOT", "LITELLM_KEY", "LITELLM_URL", "OLLAMA_URL"):
    os.environ.pop(_var, None)

if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))
