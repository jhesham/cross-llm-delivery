"""B1.4 — the judge must run REAL tests, not trust the executor's stdout.

BUG1/Defect2: deliver_slice passed run_tests=lambda: result.raw_log, so the judge
re-parsed the EXECUTOR's self-reported output. A lying/incorrect executor log
therefore drove the verdict (this is why the ledger mislabeled slices on the live
run). The fix: deliver_slice accepts an injected `test_runner(workdir) -> str` that
runs the real acceptance tests in the workdir; the judge uses THAT, not raw_log.
"""

from cld.executors.base import ExecutorResult, SliceTask
from cld.orchestrator import deliver_slice


def _real_judge(files_changed, allowed, run_tests):
    from cld.judge import judge as _j
    return _j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


class LyingExecutor:
    """Returns a raw_log claiming success, regardless of reality."""

    def run(self, task, workdir, feedback=None):
        return ExecutorResult(ok=True, diff="x", files_changed=["src/a.py"],
                              raw_log="999 passed in 0.1s")  # the lie


def _slice():
    return SliceTask(id="A", brief="b", files=["src/a.py"], acceptance_test_path="t.py")


def test_judge_uses_real_test_runner_not_executor_log():
    # The executor LIES (claims 999 passed); the real test_runner reports a FAILURE.
    # The verdict must follow the real runner, not the executor's stdout.
    seen = {}

    def real_test_runner(workdir):
        seen["workdir"] = workdir
        return "FAILED t.py::test_x\n1 failed in 0.1s"  # ground truth: it failed

    res = deliver_slice(_slice(), executor=LyingExecutor(), judge_fn=_real_judge,
                        max_retries=0, workdir="/wt/slice-A",
                        test_runner=real_test_runner)
    assert res.accepted is False  # NOT fooled by the executor's "999 passed"
    assert seen["workdir"] == "/wt/slice-A"  # ran in the worktree


def test_judge_passes_when_real_runner_passes():
    def real_test_runner(workdir):
        return "3 passed in 0.1s"

    res = deliver_slice(_slice(), executor=LyingExecutor(), judge_fn=_real_judge,
                        max_retries=0, workdir="/wt/slice-A",
                        test_runner=real_test_runner)
    assert res.accepted is True


def test_backward_compatible_without_test_runner():
    # No test_runner -> falls back to the executor's raw_log (prior behavior).
    res = deliver_slice(_slice(), executor=LyingExecutor(), judge_fn=_real_judge,
                        max_retries=0)
    # with the lie "999 passed" and no real runner, it accepts (legacy behavior)
    assert res.accepted is True
