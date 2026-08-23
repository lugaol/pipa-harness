"""LiteLLM proxy callback: appends per-completion spend rows to an NDJSON ledger.

Wiring (for whoever owns models/ fragments — this module wires nothing):

1.  This file must live under the config file's directory, at
    models/tools/litellm_hooks/spend_callback.py — LiteLLM resolves custom
    callbacks relative to the loaded config, not PYTHONPATH. The composer
    writes the effective config to models/.effective.yaml, so the relative
    path `tools.litellm_hooks.spend_callback.proxy_handler_instance`
    resolves here.

2.  Register the exported instance in the composed config:

        litellm_settings:
          callbacks:
          - tools.litellm_hooks.spend_callback.proxy_handler_instance

    The ledger destination comes from PIPA_SPEND_LOG (pipa sets it to
    <install>/state/spend.ndjson when launching the proxy); default shown:

        export PIPA_SPEND_LOG="$HOME/.pipa/spend.ndjson"

Every successful completion then appends exactly one JSON line of metadata
only: timestamp, model, alias/model_group, prompt/completion tokens, cost,
latency, status. Message content, prompts and API keys are NEVER logged.
All handlers swallow every exception so a ledger failure can never break
the serving path.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

_DEFAULT_LOG = Path.home() / ".pipa" / "spend.ndjson"


def _ledger_path() -> Path:
    return Path(os.environ.get("PIPA_SPEND_LOG") or _DEFAULT_LOG)


def _row(kwargs: dict, response_obj, start_time, end_time, status: str = "success"):
    usage = getattr(response_obj, "usage", None)
    model = getattr(response_obj, "model", None) or (kwargs or {}).get("model")
    alias = None
    try:
        alias = kwargs["litellm_params"]["model_group"]
    except (KeyError, TypeError):
        pass
    cost = None
    try:
        import litellm

        cost = litellm.completion_cost(response_obj=response_obj, model=model)
    except Exception:
        cost = None
    latency_ms = None
    if start_time and end_time:
        latency_ms = round((end_time - start_time).total_seconds() * 1000, 1)
    return {
        "event": "spend",
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "status": status,
        "model": model,
        "alias": alias,
        "tokens_in": getattr(usage, "prompt_tokens", None),
        "tokens_out": getattr(usage, "completion_tokens", None),
        "cost_usd": cost,
        "latency_ms": latency_ms,
    }


class SpendCallback(CustomLogger):
    def _append(self, row: dict) -> None:
        path = _ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ── async seam ──────────────────────────────────────────────────────────
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            self._append(_row(kwargs, response_obj, start_time, end_time))
        except Exception:
            pass

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            exc = (kwargs or {}).get("exception")
            row = {
                "event": "spend_error",
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "status": "failure",
                "model": (kwargs or {}).get("model"),
                "error_type": type(exc).__name__ if exc else None,
            }
            self._append(row)
        except Exception:
            pass

    # ── sync seam ───────────────────────────────────────────────────────────
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            self._append(_row(kwargs, response_obj, start_time, end_time))
        except Exception:
            pass

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self.async_log_failure_event(kwargs, response_obj, start_time, end_time)


proxy_handler_instance = SpendCallback()
