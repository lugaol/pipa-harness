"""bin/pipa-check skills — the skill discovery contract."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "pipa-check"
GOOD_DESC = 'description: "Use when testing. Triggers: test, check."'


def _run(base):
    return subprocess.run(
        [str(SCRIPT), "skills", str(base)],
        capture_output=True, text=True, timeout=60)


def _skill(base, dirname, frontmatter):
    d = base / "skills" / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n# {dirname}\n")
    return d


def test_valid_skill_passes(tmp_path):
    _skill(tmp_path, "good-skill", f"name: good-skill\n{GOOD_DESC}")
    assert _run(tmp_path).returncode == 0


def test_name_must_match_directory(tmp_path):
    _skill(tmp_path, "actual", f"name: different\n{GOOD_DESC}")
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "!= directory" in r.stdout


def test_name_charset_enforced(tmp_path):
    _skill(tmp_path, "Bad_Name", f"name: Bad_Name\n{GOOD_DESC}")
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "[a-z0-9-]" in r.stdout


def test_trigger_words_required(tmp_path):
    _skill(tmp_path, "no-trigger", 'name: no-trigger\ndescription: "A helpful guide."')
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "no trigger words" in r.stdout


def test_description_length_capped(tmp_path):
    long = "y" * 1100
    _skill(tmp_path, "long-desc", f'name: long-desc\ndescription: "Use when x. Triggers: {long}"')
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "max 1024" in r.stdout


def test_missing_description_fails(tmp_path):
    _skill(tmp_path, "no-desc", "name: no-desc")
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "missing `description`" in r.stdout


def test_missing_skill_md_fails(tmp_path):
    (tmp_path / "skills" / "empty").mkdir(parents=True)
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "has no SKILL.md" in r.stdout


def test_no_skills_dir_is_skipped(tmp_path):
    assert _run(tmp_path).returncode == 0


def test_repo_skills_conform():
    """The harness's own skills are the regression fixture."""
    assert _run(ROOT).returncode == 0
