"""pipa recall — one query over vault + memory.db + code graph."""
from __future__ import annotations

from pipa import config


def _say(msg: str = "") -> None:
    print(msg)


def _digest_cap() -> int:
    """Per-model digest budget, mirroring ia's memory-context caps."""
    import os

    if os.environ.get("MEMORY_CONTEXT_DISABLED") == "1":
        return 0
    if os.environ.get("MEMORY_CONTEXT_SMALL") == "1":
        return 1200
    try:
        explicit = int(os.environ.get("MEMORY_CONTEXT_MAX_CHARS") or "")
        if explicit > 0:
            return min(explicit, 8000)
    except ValueError:
        pass
    return 4000


def cmd_recall(args) -> int:
    if getattr(args, "stale", False):
        from pipa.recall import stale_report
        report = stale_report(project=config.find_project())
        if not report:
            _say("memory clean — no stale notes.")
            return 0
        _say(f"stale notes: {len(report)} (report-only — delete, rewrite, or SUPERSEDE)")
        for entry in report:
            _say(f"  - {entry['title']} @ {entry['path']}")
            for reason in entry["reasons"]:
                _say(f"      {reason}")
        return 0
    from pipa.recall import recall as do_recall
    if not args.query:
        _say("usage: pipa recall <query> | pipa recall --stale")
        return 2
    out = do_recall(args.query, project=config.find_project(), limit=args.limit)
    if getattr(args, "digest", False):
        return _print_digest(args.query, out)
    if not out["results"]:
        _say(f'nothing recalled for "{args.query}" '
             f"(sources: {', '.join(out['sources_queried']) or 'none'})")
        return 1
    _say(f'recall "{args.query}" — sources: {", ".join(out["sources_queried"])}')
    cur = None
    for hit in out["results"]:
        if hit["source"] != cur:
            cur = hit["source"]
            _say(f"\n  [{cur}]")
        flag = " EXPIRED" if hit["expired"] else ""
        loc = f" @ {hit['path']}" if hit.get("path") else ""
        _say(f"   - {hit['title']}{flag}{loc}")
        if hit.get("detail"):
            _say(f"       {hit['detail'][:100]}")
    return 0


def _print_digest(query: str, out: dict) -> int:
    """Compact machine-readable digest for the memory-context plugin.

    Bounded (see _digest_cap), best-effort, never fails loudly: prints
    "(memory context unavailable)" and exits 0 when there is nothing.
    """
    cap = _digest_cap()
    if cap <= 0:
        return 0
    lines = [f"memory digest for: {query[:200]}"]
    for hit in out["results"][:12]:
        flag = " [expired]" if hit["expired"] else ""
        loc = f" ({hit['path']})" if hit.get("path") else ""
        lines.append(f"- [{hit['source']}] {hit['title']}{flag}{loc}")
        if hit.get("detail"):
            lines.append(f"  {hit['detail'][:200]}")
    text = "\n".join(lines)
    if len(text) > cap:
        text = text[:cap] + "\n…(truncated; use pipa recall for details)"
    if not out["results"]:
        text = "(memory context unavailable)"
    print(text)
    return 0
