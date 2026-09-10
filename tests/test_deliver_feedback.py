"""T5.6c: judge feedback feeds the retry.

On a failed attempt, deliver_slice passes the prior judge result's failing-test
feedback to the next executor.run via an optional `feedback` kwarg. Executors that
don't accept it keep working (backward-compatible).
"""

from cld.executors.base import ExecutorResult, SliceTask
from cld.orchestrator import deliver_slice
import pytest


def _judge(files_changed, allowed, run_tests):
    from cld.judge import judge as _j
    return _j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


class FeedbackAwareExecutor:
    """Accepts an optional feedback kwarg; records what it received each attempt.
    Fails the first attempt, passes the second (so a retry happens)."""

    def __init__(self):
        self.feedbacks = []
        self._calls = 0

    def run(self, task, workdir, feedback=None):
        self.feedbacks.append(feedback)
        self._calls += 1
        if self._calls == 1:
            log = "FAILED t.py::test_x\n1 failed in 0.1s"
        else:
            log = "1 passed in 0.1s"
        return ExecutorResult(ok=True, diff="", files_changed=["src/a.py"], raw_log=log)


class LegacyExecutor:
    """Old-style executor: run(task, workdir) only — no feedback kwarg."""

    def run(self, task, workdir):
        return ExecutorResult(ok=True, diff="", files_changed=["src/a.py"],
                              raw_log="1 passed in 0.1s")


def _slice():
    return SliceTask(id="A", brief="b", files=["src/a.py"], acceptance_test_path="t.py")


def test_feedback_passed_to_retry():
    ex = FeedbackAwareExecutor()
    res = deliver_slice(_slice(), executor=ex, judge_fn=_judge, max_retries=2, simulation=True)
    assert res.accepted is True
    assert res.attempts == 2
    # first attempt: no feedback; second attempt: feedback present mentioning the failure
    assert ex.feedbacks[0] is None
    assert ex.feedbacks[1] is not None
    assert "test_x" in ex.feedbacks[1]


def test_legacy_executor_without_feedback_kwarg_still_works():
    # Must not raise even though LegacyExecutor.run has no feedback param.
    ex = LegacyExecutor()
    res = deliver_slice(_slice(), executor=ex, judge_fn=_judge, max_retries=1, simulation=True)
    assert res.accepted is True
    assert res.attempts == 1


def test_executor_body_typeerror_is_not_redispatched():
    class Broken(FeedbackAwareExecutor):
        def run(self, task, workdir, feedback=None):
            if feedback is not None:
                self._calls += 1
                raise TypeError("inside executor")
            return super().run(task, workdir, feedback)
    ex = Broken()
    with pytest.raises(TypeError, match="inside executor"):
        deliver_slice(_slice(), executor=ex, judge_fn=_judge, max_retries=2, simulation=True)
    assert ex._calls == 2


def test_test_runner_body_typeerror_is_not_rerun():
    calls = []
    def broken(wd, path=None):
        calls.append(wd)
        raise TypeError("inside runner")
    with pytest.raises(TypeError, match="inside runner"):
        deliver_slice(_slice(), executor=LegacyExecutor(), judge_fn=_judge, test_runner=broken, simulation=True)
    assert len(calls) == 1
