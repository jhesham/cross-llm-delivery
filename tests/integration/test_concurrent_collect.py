"""B1.5 — concurrent isolation + collect-from-worktree (the BUG1 regression test).

Two slices run concurrently in REAL worktrees off one repo. Each creates a DISTINCT
file. The test asserts the two safety properties the original live run violated:

1. **Isolation:** each slice's file lands ONLY in its own `slice-<id>` branch — no
   cross-contamination (slice-A's branch must not contain slice-B's file).
2. **Collect:** each accepted slice's code SURVIVES — i.e. branch `slice-<id>` has a
   commit containing that slice's file (the worktree is committed before removal,
   not discarded by `git worktree remove --force`).

This is the regression test that would have caught the original "code landed on one
branch / code lost" failure. Uses real git + a file-creating executor + real pytest
test_runner (trivial always-pass test) so the slice is accepted.
"""

from pathlib import Path

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.orchestrator import run_plan_parallel
from tests.integration.harness import init_repo, real_git_runner

pytestmark = pytest.mark.integration


class RealFileExecutor:
    """Creates the slice's file in the workdir (no LLM), captures via intent-to-add."""

    def run(self, task, workdir, feedback=None):
        for rel in task.files:
            dest = Path(workdir) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f"# {task.id}\nVALUE = '{task.id}'\n", encoding="utf-8")
        real_git_runner(["git", "add", "--intent-to-add", "-A"], str(workdir))
        _, names = real_git_runner(["git", "diff", "HEAD", "--name-only"], str(workdir))
        files = [ln.strip() for ln in names.splitlines() if ln.strip()]
        return ExecutorResult(ok=True, diff="d", files_changed=files,
                              token_usage={}, raw_log="")


def _judge(files_changed, allowed, run_tests):
    from cld.judge import judge as _j
    return _j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


def _always_pass_runner(workdir):
    return "1 passed in 0.0s"


def _branch_file_list(repo, branch):
    """Files present in a branch's tree (via git ls-tree)."""
    rc, out = real_git_runner(["git", "ls-tree", "-r", "--name-only", branch], repo)
    return set(ln.strip() for ln in out.splitlines() if ln.strip())


def test_concurrent_slices_isolated_and_collected(git_repo):
    repo = git_repo
    slices = [
        SliceTask(id="A", brief="b", files=["pkg/a.py"], acceptance_test_path="t.py"),
        SliceTask(id="B", brief="b", files=["pkg/b.py"], acceptance_test_path="t.py"),
    ]
    ledger = Ledger(str(Path(repo) / ".cld-ledger.json"))

    result = run_plan_parallel(
        slices, ledger,
        executor=RealFileExecutor(), judge_fn=_judge,
        max_workers=2,
        repo_dir=repo, git_runner=real_git_runner,
        test_runner=_always_pass_runner,
    )

    assert sorted(result.completed) == ["A", "B"]

    files_a = _branch_file_list(repo, "slice-A")
    files_b = _branch_file_list(repo, "slice-B")

    # (2) COLLECT: each slice's code survives on its branch
    assert "pkg/a.py" in files_a, "slice-A's code must persist on its branch"
    assert "pkg/b.py" in files_b, "slice-B's code must persist on its branch"

    # (1) ISOLATION: no cross-contamination between branches
    assert "pkg/b.py" not in files_a, "slice-A branch must NOT contain slice-B's file"
    assert "pkg/a.py" not in files_b, "slice-B branch must NOT contain slice-A's file"
