"""pipa.memory_gc — retention GC (summaries rollup, scratch prune, report-only vault)."""
import os
import time
from pathlib import Path

from pipa import memory_gc as gc


def _touch(path: Path, days_old: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n")
    old = time.time() - days_old * 86400
    os.utime(path, (old, old))


def test_collect_old_summary_for_rollup(tmp_path):
    (tmp_path / "summaries").mkdir()
    (tmp_path / "summaries" / "2020-01-01-001.md").write_text("# old\n")
    (tmp_path / "summaries" / "2999-01-01-001.md").write_text("# new\n")
    cands = gc.collect_candidates(tmp_path, tmp_path / "vault")
    assert cands["summaries/2020-01-01-001.md"][0] == "rollup"
    assert "summaries/2999-01-01-001.md" not in cands


def test_collect_old_scratch_for_prune(tmp_path):
    _touch(tmp_path / "scratch" / "shots" / "old.png", days_old=60)
    _touch(tmp_path / "scratch" / "new.png", days_old=1)
    cands = gc.collect_candidates(tmp_path, tmp_path / "vault", scratch_days=30)
    assert cands["scratch/shots/old.png"][0] == "prune"
    assert "scratch/new.png" not in cands


def test_over_budget_vault_note_is_report_only(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "big.md").write_text("# t\n" + "line\n" * 150)
    (vault / "small.md").write_text("# t\nsmall\n")
    cands = gc.collect_candidates(tmp_path, vault)
    assert cands["vault/big.md"][0] == "report"
    assert "vault/small.md" not in cands


def test_apply_rolls_up_and_prunes(tmp_path):
    (tmp_path / "summaries").mkdir()
    (tmp_path / "summaries" / "2020-05-01-001.md").write_text("# may summary\n")
    _touch(tmp_path / "scratch" / "old.png", days_old=60)
    (tmp_path / "spend.ndjson").write_text('{"rows": 1}\n')
    cands = gc.collect_candidates(tmp_path, tmp_path / "vault")
    result = gc.apply_gc(tmp_path, cands)
    assert result["rollups_written"] == 1
    assert result["summaries_pruned"] == 1
    assert result["scratch_deleted"] == 1
    rollup = tmp_path / "summaries" / "rollups" / "2020-05.md"
    assert rollup.exists() and "may summary" in rollup.read_text()
    assert not (tmp_path / "summaries" / "2020-05-01-001.md").exists()
    assert not (tmp_path / "scratch" / "old.png").exists()
    assert (tmp_path / "spend.ndjson").exists(), "ledger untouched"


def test_cli_dry_run_and_manifest(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    from pipa import config
    from pipa.commands.memory_gc import cmd_memory_gc

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "harness_root", lambda: tmp_path)
    (tmp_path / "summaries").mkdir()
    (tmp_path / "summaries" / "2020-01-01-001.md").write_text("# old\n")
    assert cmd_memory_gc(SimpleNamespace(apply=False, manifest=False,
                                         summaries_days=180, scratch_days=30)) == 0
    out = capsys.readouterr().out
    assert "Dry run" in out and "2020-01-01-001.md" in out
    assert (tmp_path / "summaries" / "2020-01-01-001.md").exists()
    assert cmd_memory_gc(SimpleNamespace(apply=False, manifest=True,
                                         summaries_days=180, scratch_days=30)) == 0
    assert '"eligible": 1' in capsys.readouterr().out
