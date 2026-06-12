"""B1.1 — Real-git integration test harness.

All other cld tests use FAKE git_runners and FAKE executors, so they can never
observe the behaviors that only emerge against real git (e.g. `git diff HEAD`
silently omitting untracked new files — BUG 1, Defect 1). This harness supplies
the missing realism:

- `real_git_runner`: the actual subprocess git runner (same shape as
  run_delivery.py's git_runner).
- `init_repo(path)`: create a real git repo with one initial commit (so HEAD exists).
- `FileCreatingExecutor`: a fake Executor that, on .run(task, workdir), ACTUALLY
  writes the slice's files into `workdir` (simulating what Gemini does — creating
  new files) and then captures the diff via the SAME real-git logic GeminiExecutor
  uses. This lets tests observe the real capture path deterministically, offline.

These run real `git` subprocesses on tiny temp repos — fast (sub-second), but
marked `integration` so they can be deselected where git is unavailable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from cld.executors.base import ExecutorResult, SliceTask


def real_git_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Run a real git (or other) command; return (returncode, combined output).

    Mirrors run_delivery.py::git_runner so integration tests exercise exactly the
    runner the live pipeline uses.
    """
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return (proc.returncode, (proc.stdout or "") + (proc.stderr or ""))


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

    Simulates Gemini's observable effect (new files appear in the worktree) without
    any network/LLM. It then captures the diff with the SAME real-git logic as
    GeminiExecutor (`git diff HEAD` + `--name-only`), so a test can assert what the
    real capture path actually reports — including the untracked-file blind spot.

    `contents` maps a file path (relative to workdir) -> file text. Defaults to a
    trivial body for each of task.files.
    """

    def __init__(self, *, runner=real_git_runner, contents: dict[str, str] | None = None):
        self._runner = runner
        self._contents = contents

    def run(self, task: SliceTask, workdir, feedback: str | None = None) -> ExecutorResult:
        cwd = str(workdir)
        # 1) actually create the slice's files (this is what Gemini does)
        for rel in task.files:
            body = (self._contents or {}).get(rel, f"# {rel} created by FileCreatingExecutor\n")
            dest = Path(cwd) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")

        # 2) capture exactly as GeminiExecutor does (the path under test)
        _, diff = self._runner(["git", "diff", "HEAD"], cwd)
        _, names = self._runner(["git", "diff", "HEAD", "--name-only"], cwd)
        files_changed = [ln.strip() for ln in names.splitlines() if ln.strip()]

        return ExecutorResult(
            ok=True,
            diff=diff,
            files_changed=files_changed,
            token_usage={"total": 0},
            raw_log="1 passed in 0.01s",
        )
