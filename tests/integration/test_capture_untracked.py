"""B1.2 — test pinning BUG 1 / Defect 1 (capture of untracked created files).

A CLI executor captures changed files via `git diff HEAD --name-only`. When a slice
CREATES a new file it is untracked, and `git diff HEAD` omits it — so `files_changed`
would come back empty for a slice that clearly changed the tree. The shared
`capture_diff` helper fixes this with `git add --intent-to-add -A` before diffing.
This test drives a real executor (CursorExecutor — the gemini provider was removed
2026-06-22) with a real git_runner but a fake LLM dispatch (the dispatch "creates"
the file via a runner shim), and asserts the created file appears in files_changed.
"""

from pathlib import Path

import pytest

from cld.executors.base import SliceTask
from cld_providers.cursor.provider import CursorExecutor
from tests.integration.harness import real_git_runner

pytestmark = pytest.mark.integration

CREATED_FILE = "src/created_by_slice.py"


def _runner_factory(repo: str):
    """A runner that behaves like real git for git commands, but for the executor's
    CLI dispatch it (a) returns a minimal success JSON and (b) actually creates the
    slice file on disk — simulating the agent's effect. Everything else (git
    diff/status) is REAL. The cursor dispatch is identified by its `-p` + `--workspace`
    flags (argv[0] is a node/cursor-agent path, not a fixed name).
    """
    def runner(args, cwd):
        if "-p" in args and "--workspace" in args:
            # simulate the executor's effect: a new file appears in the worktree
            dest = Path(cwd) / CREATED_FILE
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("x = 1\n", encoding="utf-8")
            return (0, '{"type":"result","subtype":"success","is_error":false,"usage":{}}')
        # real git for everything else (diff, name-only, add, status, ...)
        return real_git_runner(args, cwd)

    return runner


def test_created_file_appears_in_files_changed(git_repo):
    ex = CursorExecutor(runner=_runner_factory(git_repo))
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
