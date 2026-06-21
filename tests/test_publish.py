import subprocess, sys, os
from pathlib import Path
from generator.publish import load_publish_targets, publish_one, publish_umbrella
import pytest


def _write(tmp, body):
    p = tmp / "targets.toml"; p.write_text(body, encoding="utf-8"); return p


def test_loads_provider_and_umbrella_targets(tmp_path):
    p = _write(tmp_path,
        'gemini = "git@example.com:me/cross-llm-gemini.git"\n'
        'cursor = "git@example.com:me/cross-llm-cursor.git"\n'
        'all = "git@example.com:me/cross-llm-all.git"\n')
    t = load_publish_targets(p)
    assert t["gemini"].endswith("cross-llm-gemini.git")
    assert t["all"].endswith("cross-llm-all.git")


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_publish_targets(tmp_path / "nope.toml")


def test_example_config_exists_and_is_documented():
    ex = Path("generator/publish-targets.example.toml").read_text(encoding="utf-8")
    assert "all" in ex and "#" in ex   # has the umbrella key + explanatory comments


# ---- Task 2: publish_one ----

def _git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (p.returncode, (p.stdout or "") + (p.stderr or ""))


def test_dry_run_touches_nothing_and_returns_plan(tmp_path):
    targets = {"cursor": "git@example.com:me/cross-llm-cursor.git"}
    plan = publish_one("cursor", targets=targets, version="9.9.9",
                       dist_root=tmp_path, execute=False)
    assert plan["provider"] == "cursor"
    assert plan["repo"].endswith("cross-llm-cursor.git")
    assert plan["version"] == "9.9.9"
    assert plan["files"] > 0
    # dry-run must NOT have pushed anything (no network); the plan lists intended actions
    assert any("push" in a.lower() for a in plan["actions"])


def test_execute_pushes_to_local_bare_repo(tmp_path):
    # a LOCAL bare repo stands in for the remote -> real git, zero network
    remote = tmp_path / "remote.git"
    _git(["git", "init", "--bare", str(remote)], str(tmp_path))
    targets = {"cursor": str(remote)}
    publish_one("cursor", targets=targets, version="9.9.9",
                dist_root=tmp_path / "dist", execute=True, runner=_git)
    # clone the bare repo and verify the skill landed at the repo ROOT + the tag exists
    work = tmp_path / "verify"
    _git(["git", "clone", str(remote), str(work)], str(tmp_path))
    assert (work / "SKILL.md").is_file()                 # repo root IS the skill
    assert (work / "scripts" / "cld_providers" / "cursor").is_dir()
    rc, tags = _git(["git", "tag"], str(work))
    assert "v9.9.9" in tags
    # trimmed: no __pycache__ committed
    rc, ls = _git(["git", "ls-files"], str(work))
    assert "__pycache__" not in ls and ".pyc" not in ls


# ---- Task 3: publish_umbrella ----

def test_umbrella_dry_run_lists_all_providers(tmp_path):
    targets = {"all": "git@example.com:me/cross-llm-all.git"}
    plan = publish_umbrella(targets=targets, version="9.9.9",
                            dist_root=tmp_path / "dist", execute=False)
    # the umbrella bundles every known provider
    from generator.build_skill import _known_providers
    for p in _known_providers():
        assert f"cross-llm-{p}" in plan["bundled"]


def test_umbrella_execute_to_local_bare_repo(tmp_path):
    remote = tmp_path / "all.git"
    _git(["git", "init", "--bare", str(remote)], str(tmp_path))
    publish_umbrella(targets={"all": str(remote)}, version="9.9.9",
                     dist_root=tmp_path / "dist", execute=True, runner=_git)
    work = tmp_path / "verify-all"
    _git(["git", "clone", str(remote), str(work)], str(tmp_path))
    from generator.build_skill import _known_providers
    for p in _known_providers():
        assert (work / f"cross-llm-{p}" / "SKILL.md").is_file()
    assert (work / "README.md").is_file()


# ---- Task 4: README documents per-provider install ----

def test_readme_documents_per_provider_install():
    r = Path("README.md").read_text(encoding="utf-8")
    assert "cross-llm-" in r                       # references the per-provider skills
    assert "generator/build_skill.py" in r or "build_skill" in r   # how to generate
