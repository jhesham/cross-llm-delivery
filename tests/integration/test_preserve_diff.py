"""BUG B-3 (non-destructive worktree preservation) — found during the first real
Windows build (HANDOFF-clean-install.md, 2026-06-22).

When a slice is NOT accepted (e.g. the judge can't import the test, or the test
genuinely fails), the orchestrator's worktree context manager force-removes the
worktree — which discarded the executor's uncommitted (often CORRECT) code. The
engine must preserve that diff to `.cld/<id>/<id>.patch` before removal so a judge
mis-resolution can never silently delete work.
"""
import os
from pathlib import Path

import pytest

from cld.orchestrator import run_plan_parallel
from cld.executors.base import SliceTask
from cld.ledger import Ledger
from cld.judge import judge
from tests.integration.harness import real_git_runner, FileCreatingExecutor

pytestmark = pytest.mark.integration


def test_failed_slice_preserves_executor_diff(git_repo):
    task = SliceTask(id="T9", brief="make src/new.py", files=["src/new.py"],
                     acceptance_test_path="tests/test_new.py")
    ledger = Ledger(os.path.join(git_repo, ".cld-ledger.json"))

    # judge always rejects (test_runner reports no pass) -> slice NOT accepted ->
    # the worktree is force-removed. The executor's diff must be preserved first.
    run_plan_parallel(
        [task], ledger,
        executor=FileCreatingExecutor(contents={"src/new.py": "x = 42\n"}),
        judge_fn=judge,
        test_runner=lambda wd, p=None: "no tests ran",  # 0 passed -> not accepted
        repo_dir=git_repo, git_runner=real_git_runner, max_workers=1,
    )

    patch = Path(git_repo) / ".cld" / "T9" / "T9.patch"
    assert patch.is_file(), "executor diff was NOT preserved on non-accept (data loss)"
    body = patch.read_text(encoding="utf-8", errors="replace")
    assert "src/new.py" in body and "x = 42" in body, body

    # the raw judge output must be persisted for diagnosis (concurrency false-negative report)
    judge_out = Path(git_repo) / ".cld" / "T9" / "judge-output.txt"
    assert judge_out.is_file(), "raw judge output was not persisted (undiagnosable)"
    jo = judge_out.read_text(encoding="utf-8", errors="replace")
    assert "no tests ran" in jo and "attempt 1" in jo, jo
