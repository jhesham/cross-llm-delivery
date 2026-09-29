"""Opt-in local Codex sandbox regressions: no model or network calls.

Run with CLD_RUN_CODEX_SANDBOX_TESTS=1 on Windows with Codex installed.
Only newly reserved directories beneath this checkout's .cld are modified.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest

from cld.executors.base import ExecutorResult
from cld.validate import validate_model
from cld.worktree import worktree
from cld._windows_workspace import prepare_windows_workspace
from tests.integration.harness import init_repo, real_git_runner


pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.name != "nt" or os.environ.get("CLD_RUN_CODEX_SANDBOX_TESTS") != "1",
    reason="opt-in Windows Codex sandbox check; never dispatches a model",
)]


@pytest.fixture
def sandbox_root():
    assert shutil.which("codex"), "Codex must be installed for the opt-in check"
    parent = Path(__file__).resolve().parents[2] / ".cld" / "sandbox-regressions"
    parent.mkdir(parents=True, exist_ok=True)
    root = parent / uuid4().hex
    root.mkdir()
    # Retain validation evidence for inspection. No user directories are reused.
    return root


def sandbox_edit(repo, filename, content, protected_paths):
    code = (
        "from pathlib import Path\n"
        f"p=Path({filename!r}); assert p.is_file(); p.read_text(); p.write_text({content!r})\n"
        f"assert p.read_text()=={content!r}\n"
        "n=Path('new-smoke.txt'); n.write_text('new'); assert n.read_text()=='new'; n.unlink()\n"
        f"for name in {protected_paths!r}:\n"
        " try:\n"
        "  Path(name).write_text('unexpected sandbox write')\n"
        " except PermissionError:\n"
        "  pass\n"
        " else:\n"
        "  raise AssertionError('protected write succeeded: '+name)\n"
        "print('EXISTING_FILE_EDIT_AND_BOUNDARIES_OK')\n"
    )
    return subprocess.run(
        ["codex", "sandbox", "-P", ":workspace", "-C", str(repo),
         "--", sys.executable, "-c", code],
        cwd=repo, capture_output=True, text=True, timeout=30,
    )


def test_codex_sandbox_edits_private_validation_repo_and_preserves_evidence(sandbox_root):
    class LocalSandboxExecutor:
        def run(self, task, cwd):
            repo = Path(cwd)
            ledger = next((repo.parent / "artifacts").glob("*/outcome.json"))
            before = ledger.read_bytes()
            config = (repo / ".git" / "config").read_bytes()
            result = sandbox_edit(repo, "calc.py", "def add(a,b): return a+b\n",
                                  ["../" + ledger.relative_to(repo.parent).as_posix(), ".git/config"])
            assert ledger.read_bytes() == before
            assert (repo / ".git" / "config").read_bytes() == config
            return ExecutorResult(result.returncode == 0, "", raw_log=result.stdout + result.stderr)

    result = validate_model("local-sandbox-fixture", executor=LocalSandboxExecutor(),
                            git_runner=real_git_runner, base_dir=str(sandbox_root))
    assert result.passed, result.note + "; " + Path(result.artifact_path).as_posix()
    assert result.attempts == 1
    assert result.usage == {}


def test_codex_sandbox_edits_managed_worktree_without_changing_source(sandbox_root):
    repo = init_repo(sandbox_root / "source")
    root = sandbox_root / "worktrees"
    root.mkdir()
    path = root / "candidate"
    sentinel = root / "evidence.txt"
    sentinel.write_text("protected")
    with worktree(repo, "sandbox-check", runner=real_git_runner,
                  path=str(path), root=str(root)) as cwd:
        git_pointer = (Path(cwd) / ".git").read_bytes()
        result = sandbox_edit(cwd, "README.md", "candidate\n", ["../evidence.txt", ".git"])
        assert result.returncode == 0, result.stdout + result.stderr
        assert (Path(cwd) / ".git").read_bytes() == git_pointer
        assert sentinel.read_text() == "protected"
        assert Path(repo, "README.md").read_text() == "base\n"


def test_workspace_acl_grant_does_not_follow_child_junction(sandbox_root):
    repo = sandbox_root / "workspace"
    repo.mkdir()
    outside = sandbox_root / "outside"
    outside.mkdir()
    (outside / "marker.txt").write_text("protected")
    link = repo / "junction"
    subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
                   capture_output=True, check=True)
    def acl(path):
        return subprocess.run(["icacls", str(path)], capture_output=True, check=True).stdout
    before = [acl(outside), acl(outside / "marker.txt")]
    prepare_windows_workspace(repo, parent=sandbox_root)
    assert [acl(outside), acl(outside / "marker.txt")] == before
    assert (outside / "marker.txt").read_text() == "protected"
