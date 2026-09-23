"""T13A red acceptance for a disposable Codex standalone installer."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


INSTALLER = Path(__file__).resolve().parents[1] / "generator" / "install_codex.py"


def bundle(root: Path, name: str = "cross-llm-opencode", script: str = "print('ok')\n") -> Path:
    source = root / "source" / name
    (source / "scripts" / "cld").mkdir(parents=True)
    (source / "SKILL.md").write_text(f"---\nname: {name}\ndescription: delivery\n---\n\nRun scripts/run_delivery.py\n", encoding="utf-8")
    (source / "scripts" / "run_delivery.py").write_text(script, encoding="utf-8")
    (source / "scripts" / "cld" / "__init__.py").write_text("", encoding="utf-8")
    return source


def invoke(scope: Path, action: str, *, source: Path | None = None, name: str | None = None):
    assert INSTALLER.is_file(), "T13A installer has not been implemented"
    cmd = [sys.executable, str(INSTALLER), action, "--scope-root", str(scope)]
    if source is not None:
        cmd += ["--bundle", str(source)]
    if name is not None:
        cmd += ["--name", name]
    completed = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"installer did not print JSON: {completed.stdout!r} {completed.stderr!r}")
    return completed.returncode, payload


def test_preview_is_read_only_and_reports_exact_target(tmp_path):
    source = bundle(tmp_path)
    scope = tmp_path / "project with spaces"
    code, result = invoke(scope, "--preview", source=source)
    assert code == 0, result
    assert Path(result["target"]) == scope / ".agents" / "skills" / source.name
    assert not scope.exists()


def test_fresh_install_runs_vendored_script_from_nested_cwd(tmp_path):
    source = bundle(tmp_path)
    scope = tmp_path / "repo with spaces"
    nested = scope / "src" / "nested"
    nested.mkdir(parents=True)
    (scope / ".agents" / "skills" / "unrelated").mkdir(parents=True)
    code, result = invoke(scope, "--install", source=source)
    assert code == 0, result
    installed = scope / ".agents" / "skills" / source.name
    assert (installed / "SKILL.md").is_file()
    assert (installed / "scripts" / "cld" / "__init__.py").is_file()
    assert (installed / ".cld-install.json").is_file()
    run = subprocess.run([sys.executable, str(installed / "scripts" / "run_delivery.py")], cwd=nested, text=True, capture_output=True, timeout=10)
    assert run.returncode == 0 and run.stdout.strip() == "ok"
    assert (scope / ".agents" / "skills" / "unrelated").is_dir()


def test_clean_update_then_uninstall_preserves_unrelated(tmp_path):
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    unrelated = scope / ".agents" / "skills" / "other" / "SKILL.md"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("keep", encoding="utf-8")
    assert invoke(scope, "--install", source=source)[0] == 0
    (source / "scripts" / "run_delivery.py").write_text("print('new')\n", encoding="utf-8")
    assert invoke(scope, "--install", source=source)[0] == 0
    target = scope / ".agents" / "skills" / source.name
    assert "new" in (target / "scripts" / "run_delivery.py").read_text(encoding="utf-8")
    assert invoke(scope, "--uninstall", name=source.name)[0] == 0
    assert not target.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_import_cache_does_not_prevent_uninstall(tmp_path):
    source = bundle(tmp_path, script="import cld\nprint('ok')\n")
    scope = tmp_path / "project"
    assert invoke(scope, "--install", source=source)[0] == 0
    target = scope / ".agents" / "skills" / source.name
    run = subprocess.run([sys.executable, str(target / "scripts" / "run_delivery.py")],
                         text=True, capture_output=True, timeout=10)
    assert run.returncode == 0, run.stderr
    assert any(target.rglob("*.pyc"))
    assert invoke(scope, "--uninstall", name=source.name)[0] == 0
    assert not target.exists()


@pytest.mark.parametrize("change", ["edit", "extra", "manifest", "symlink"])
def test_local_edits_block_update_and_uninstall(tmp_path, change):
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    assert invoke(scope, "--install", source=source)[0] == 0
    target = scope / ".agents" / "skills" / source.name
    if change == "edit":
        (target / "SKILL.md").write_text("local", encoding="utf-8")
    elif change == "extra":
        (target / "note.txt").write_text("local", encoding="utf-8")
    elif change == "manifest":
        (target / ".cld-install.json").write_text("invalid", encoding="utf-8")
    else:
        outside = tmp_path / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        try:
            (target / "linked.txt").symlink_to(outside)
        except OSError:
            pytest.skip("symlink creation unavailable")
    snapshot = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert invoke(scope, "--install", source=source)[0] != 0
    assert invoke(scope, "--uninstall", name=source.name)[0] != 0
    assert snapshot == {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_same_name_unowned_collision(tmp_path):
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    target = scope / ".agents" / "skills" / source.name
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("mine", encoding="utf-8")
    assert invoke(scope, "--preview", source=source)[0] != 0
    assert invoke(scope, "--install", source=source)[0] != 0
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "mine"


def test_bad_bundle_and_invalid_name_rejected(tmp_path):
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    (source / "scripts" / "cld" / "__init__.py").unlink()
    assert invoke(scope, "--install", source=source)[0] != 0
    assert invoke(scope, "--uninstall", name="../other")[0] != 0
    assert not scope.exists()


def test_symlink_source_is_rejected(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    source = bundle(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    link = source / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")
    assert invoke(tmp_path / "project", "--install", source=source)[0] != 0


def test_target_parent_symlink_escape_is_rejected(tmp_path):
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    outside = tmp_path / "outside"
    outside.mkdir()
    scope.mkdir()
    try:
        (scope / ".agents").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")
    assert invoke(scope, "--install", source=source)[0] != 0
    assert not (outside / "skills").exists()


def test_read_only_or_permission_denied_target_is_non_destructive(tmp_path):
    source = bundle(tmp_path)
    scope = tmp_path / "project"
    skills = scope / ".agents" / "skills"
    skills.mkdir(parents=True)
    skills.chmod(0o500)
    try:
        if os.access(skills, os.W_OK):
            pytest.skip("runtime can write read-only directories")
        assert invoke(scope, "--install", source=source)[0] != 0
        assert not (skills / source.name).exists()
    finally:
        skills.chmod(0o700)
