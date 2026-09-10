"""Offline integration helpers: real Git, test-owned repos, simulated file writers.

FileCreatingExecutor uses the production capture helper. Assertions should inspect
Git trees and actual files independently, rather than duplicating capture logic.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from cld.executors.base import ExecutorResult, SliceTask
from cld.executors._capture import capture_diff


def real_git_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Run a real git (or other) command; return (returncode, combined output).

    Mirrors run_delivery.py::git_runner so integration tests exercise exactly the
    runner the live pipeline uses.
    """
    proc = subprocess.run(args, cwd=cwd, capture_output=True)
    return (proc.returncode, (proc.stdout + proc.stderr).decode("utf-8"))


def init_repo(path: str | Path) -> str:
    """Initialize a real git repo at `path` with one committed file (HEAD exists).

    Returns the repo path as a string. Configures a local identity so commits work
    in CI without global git config.
    """
    path = str(path)
    Path(path).mkdir(parents=True, exist_ok=True)
    runs = [
        ["git", "init", "-q"],
        ["git", "config", "user.email", "harness@cld.test"],
        ["git", "config", "user.name", "cld-harness"],
        ["git", "config", "commit.gpgsign", "false"],
    ]
    for args in runs:
        rc, out = real_git_runner(args, path)
        if rc != 0:
            raise RuntimeError(f"git init step failed: {args} -> {out}")
    # one initial commit so HEAD exists (worktree/diff need it)
    (Path(path) / "README.md").write_text("base\n", encoding="utf-8")
    for args in (["git", "add", "-A"], ["git", "commit", "-qm", "init"]):
        rc, out = real_git_runner(args, path)
        if rc != 0:
            raise RuntimeError(f"git initial commit failed: {args} -> {out}")
    return path


class FileCreatingExecutor:
    """Fake Executor that REALLY creates the slice's files in the workdir.

    Writes files without any network/LLM and delegates capture to the shared
    production helper used by the providers.

    `contents` maps a file path (relative to workdir) -> file text. Defaults to a
    trivial body for each of task.files.
    """

    def __init__(self, *, runner=real_git_runner, contents: dict[str, str] | None = None):
        self._runner = runner
        self._contents = contents

    def run(self, task: SliceTask, workdir, feedback: str | None = None) -> ExecutorResult:
        cwd = str(workdir)
        # Simulate the implementation process's filesystem effects.
        for rel in task.files:
            body = (self._contents or {}).get(rel, f"# {rel} created by FileCreatingExecutor\n")
            dest = Path(cwd) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")

        diff, files_changed = capture_diff(self._runner, cwd)

        return ExecutorResult(
            ok=True,
            diff=diff,
            files_changed=files_changed,
            token_usage={"total": 0},
            raw_log="1 passed in 0.01s",
        )
