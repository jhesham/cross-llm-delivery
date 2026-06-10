"""B1.2 — failing test pinning BUG 1 / Defect 1.

The REAL GeminiExecutor captures changed files via `git diff HEAD --name-only`.
When a slice CREATES a new file, that file is untracked, and `git diff HEAD`
omits it — so `files_changed` comes back empty for a slice that clearly changed
the tree. This test drives the real GeminiExecutor with a real git_runner but a
fake LLM dispatch (the dispatch "creates" the file via a runner shim), and asserts
the FIXED behavior: the created file appears in files_changed.

RED until B1.3 (executor `git add` before diff). Green after.
"""

from pathlib import Path

import pytest

from cld.executors.base import SliceTask
from cld.executors.gemini import GeminiExecutor
from tests.integration.harness import real_git_runner

pytestmark = pytest.mark.integration

CREATED_FILE = "src/created_by_slice.py"


def _runner_factory(repo: str):
    """A runner that behaves like real git for git commands, but for the gemini
    dispatch it (a) returns a minimal JSON and (b) actually creates the slice file
    on disk — simulating Gemini's effect. Everything else (git diff/status) is REAL.
    """
    def runner(args, cwd):
        if args and args[0] in ("gemini", "gemini.cmd"):
            # simulate the executor's effect: a new file appears in the worktree
            dest = Path(cwd) / CREATED_FILE
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("x = 1\n", encoding="utf-8")
            return (0, '{"stats": {"models": {}}}')
        # real git for everything else (diff, name-only, add, status, ...)
        return real_git_runner(args, cwd)

    return runner


def test_created_file_appears_in_files_changed(git_repo):
    ex = GeminiExecutor(runner=_runner_factory(git_repo))
    task = SliceTask(id="S1", brief="create the module",
                     files=[CREATED_FILE], acceptance_test_path="t.py")
    result = ex.run(task, git_repo)

    # ground truth: the file really exists and real git sees it.
    # (-uall expands untracked dirs to individual files; plain porcelain collapses
    # them to 'src/'.)
    assert (Path(git_repo) / CREATED_FILE).is_file()
    rc, status = real_git_runner(["git", "status", "--porcelain", "-uall"], git_repo)
    assert CREATED_FILE in status  # real git knows the tree changed

    # THE FIX (B1.3): the executor's capture must report the created file.
    assert result.ok is True
    assert CREATED_FILE in result.files_changed, (
        "Defect 1: git diff HEAD omits untracked new files; executor must "
        "`git add` (or --intent-to-add) before diffing so created files are captured."
    )
    # and the diff must be non-empty (it currently is empty for untracked files)
    assert result.diff.strip(), "diff should include the created file's content"
