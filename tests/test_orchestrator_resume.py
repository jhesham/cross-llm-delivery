"""T4.2: resumable orchestrator layer (run_plan).

Verifies run_plan skips ledger-done slices, persists after each, and that a
simulated stop + fresh start resumes from the right slice. All effects faked.
"""

from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import DONE, FAILED, Ledger
from cld.orchestrator import PlanResult, run_plan


class FakeExecutor:
    """Records which slice ids it was asked to run; returns preset result."""

    def __init__(self, files_by_id, log_by_id):
        self._files = files_by_id
        self._log = log_by_id
        self.dispatched = []

    def run(self, task, workdir):
        self.dispatched.append(task.id)
        return ExecutorResult(
            ok=True,
            diff="",
            files_changed=self._files.get(task.id, []),
            raw_log=self._log.get(task.id, ""),
        )


def _real_judge(files_changed, allowed, run_tests):
    from cld.judge import judge as _judge
    return _judge(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


def _slice(i):
    return SliceTask(id=i, brief="b", files=[f"src/{i}.py"], acceptance_test_path="t.py")


def _passing_setup(ids):
    files = {i: [f"src/{i}.py"] for i in ids}
    logs = {i: "2 passed in 0.1s" for i in ids}
    return FakeExecutor(files, logs)


def test_run_plan_runs_all_when_ledger_empty(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    slices = [_slice("A"), _slice("B")]
    ex = _passing_setup(["A", "B"])
    res = run_plan(slices, led, executor=ex, judge_fn=_real_judge)
    assert isinstance(res, PlanResult)
    assert res.completed == ["A", "B"]
    assert res.skipped == []
    assert ex.dispatched == ["A", "B"]
    assert led.is_done("A") and led.is_done("B")


def test_run_plan_skips_done_slices(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    led.set("A", status=DONE)  # pre-marked done
    slices = [_slice("A"), _slice("B")]
    ex = _passing_setup(["A", "B"])
    res = run_plan(slices, led, executor=ex, judge_fn=_real_judge)
    assert res.skipped == ["A"]
    assert res.completed == ["B"]
    assert ex.dispatched == ["B"]  # A never dispatched


def test_run_plan_records_failures(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    # B "passes", C produces a failing test log
    ex = FakeExecutor(
        files_by_id={"B": ["src/B.py"], "C": ["src/C.py"]},
        log_by_id={"B": "1 passed in 0.1s", "C": "FAILED t.py::x\n1 failed in 0.1s"},
    )
    res = run_plan([_slice("B"), _slice("C")], led, executor=ex, judge_fn=_real_judge)
    assert res.completed == ["B"]
    assert res.failed == ["C"]
    assert led.is_done("B")
    assert led.get("C").status == FAILED


def test_run_plan_persists_after_each(tmp_path):
    # After run, the ledger file on disk must already reflect DONE (saved per slice).
    p = str(tmp_path / "l.json")
    led = Ledger(p)
    ex = _passing_setup(["A"])
    run_plan([_slice("A")], led, executor=ex, judge_fn=_real_judge)
    # fresh load from disk sees the persisted state
    reloaded = Ledger.load(p)
    assert reloaded.is_done("A")


def test_resume_from_simulated_stop(tmp_path):
    # Run 1: only A in the plan, completes -> persisted.
    p = str(tmp_path / "l.json")
    led1 = Ledger(p)
    ex1 = _passing_setup(["A"])
    run_plan([_slice("A")], led1, executor=ex1, judge_fn=_real_judge)

    # Run 2: fresh ledger loaded from disk, full plan [A, B]. A must be skipped.
    led2 = Ledger.load(p)
    ex2 = _passing_setup(["A", "B"])
    res = run_plan([_slice("A"), _slice("B")], led2, executor=ex2, judge_fn=_real_judge)
    assert res.skipped == ["A"]
    assert res.completed == ["B"]
    assert ex2.dispatched == ["B"]  # A not re-run after resume


def test_run_plan_persists_usage_to_ledger(tmp_path):
    from cld.orchestrator import run_plan
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    class _Exec:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="+x", files_changed=["x"],
                                  token_usage={"total": 7}, raw_log="")

    p = str(tmp_path / "l.json")
    led = Ledger(p)
    run_plan([SliceTask(id="A", brief="b", files=["x"], acceptance_test_path="t.py")],
             led, executor=_Exec(),
             judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})())
    e = Ledger.load(p).get("A")
    assert e.status == "done"
    assert e.token_usage == {"total": 7}
    assert e.model
