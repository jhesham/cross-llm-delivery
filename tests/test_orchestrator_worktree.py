"""T5.4: worktree isolation for the parallel path (multi-agent safety).

When run_plan_parallel is given repo_dir + git_runner, each slice runs inside its
own git worktree, and the executor receives that worktree's path as its workdir —
so concurrent agents never share a directory. Without repo_dir, behavior is
unchanged (workdir falls back to task.id).
"""

import threading

from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.orchestrator import run_plan_parallel


def _slice(i, deps=None):
    return SliceTask(id=i, brief="b", files=[f"src/{i}.py"],
                     acceptance_test_path="t.py", deps=deps or [])


class WorkdirRecordingExecutor:
    """Records the workdir each slice was run with."""

    def __init__(self):
        self.workdirs = {}
        self._lock = threading.Lock()

    def run(self, task, workdir):
        with self._lock:
            self.workdirs[task.id] = workdir
        return ExecutorResult(ok=True, diff="", files_changed=[f"src/{task.id}.py"],
                              raw_log="1 passed in 0.1s")


def _judge(files_changed, allowed, run_tests):
    from cld.judge import judge as _j
    return _j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


class FakeGitRunner:
    """Records git worktree commands; always succeeds."""

    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()

    def __call__(self, args, cwd):
        with self._lock:
            self.calls.append(args)
        return (0, "")


def test_each_slice_runs_in_distinct_worktree(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    ex = WorkdirRecordingExecutor()
    git = FakeGitRunner()
    slices = [_slice("A"), _slice("B"), _slice("C")]

    run_plan_parallel(
        slices, led, executor=ex, judge_fn=_judge, max_workers=3,
        repo_dir="/repo", git_runner=git,
    )

    # Each slice got a DISTINCT workdir (not "/repo" and not each other's).
    paths = set(ex.workdirs.values())
    assert len(paths) == 3
    assert "/repo" not in paths
    # The worktree path should be derived per-slice (contain the slice id or its branch).
    for sid, wd in ex.workdirs.items():
        assert sid in wd or f"slice-{sid}" in wd


def test_worktree_add_and_remove_issued_per_slice(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    ex = WorkdirRecordingExecutor()
    git = FakeGitRunner()

    run_plan_parallel(
        [_slice("A")], led, executor=ex, judge_fn=_judge,
        repo_dir="/repo", git_runner=git,
    )

    flat = [" ".join(c) for c in git.calls]
    assert any("worktree add" in c for c in flat)
    assert any("worktree remove" in c for c in flat)


def test_fallback_without_repo_dir_uses_task_id(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    ex = WorkdirRecordingExecutor()
    # no repo_dir / git_runner -> old behavior: workdir == task.id
    run_plan_parallel([_slice("A")], led, executor=ex, judge_fn=_judge)
    assert ex.workdirs["A"] == "A"


def test_completed_still_correct_with_worktrees(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    ex = WorkdirRecordingExecutor()
    git = FakeGitRunner()
    res = run_plan_parallel(
        [_slice("A"), _slice("B")], led, executor=ex, judge_fn=_judge,
        repo_dir="/repo", git_runner=git,
    )
    assert sorted(res.completed) == ["A", "B"]
