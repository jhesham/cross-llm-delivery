"""T5.2: parallel fan-out — run DAG-independent slices concurrently per layer.

run_plan_parallel layers slices via the DAG (parallel_batches), runs each layer's
independent slices concurrently (separate worktrees in production; fake executor
here), respects deps across layers, persists to the ledger per slice, and is
quota-aware (an injected quota_check can throttle/skip near the cap).

All effects faked — no real threads-on-subprocess, no live LLM.
"""

import threading
import time

from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import DONE, Ledger
from cld.orchestrator import PlanResult, run_plan_parallel


def _slice(i, deps=None):
    return SliceTask(
        id=i, brief="b", files=[f"src/{i}.py"],
        acceptance_test_path="t.py", deps=deps or [],
    )


class FakeExecutor:
    """Records dispatch order + concurrency; all slices 'pass'."""

    def __init__(self):
        self.dispatched = []
        self._lock = threading.Lock()
        self.max_concurrent = 0
        self._active = 0

    def run(self, task, workdir):
        with self._lock:
            self._active += 1
            self.max_concurrent = max(self.max_concurrent, self._active)
            self.dispatched.append(task.id)
        time.sleep(0.02)  # hold the slot so concurrency is observable
        with self._lock:
            self._active -= 1
        return ExecutorResult(ok=True, diff="", files_changed=[f"src/{task.id}.py"],
                              raw_log="1 passed in 0.1s")


def _judge(files_changed, allowed, run_tests):
    from cld.judge import judge as _j
    return _j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


def test_parallel_runs_independent_slices_concurrently(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    # A, B, C all independent -> one layer, should run concurrently
    slices = [_slice("A"), _slice("B"), _slice("C")]
    ex = FakeExecutor()
    res = run_plan_parallel(slices, led, executor=ex, judge_fn=_judge, max_workers=3)
    assert isinstance(res, PlanResult)
    assert sorted(res.completed) == ["A", "B", "C"]
    assert ex.max_concurrent >= 2  # genuinely ran in parallel


def test_parallel_respects_dependency_layers(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    # B depends on A: A must be dispatched (and complete) before B
    slices = [_slice("A"), _slice("B", deps=["A"])]
    ex = FakeExecutor()
    res = run_plan_parallel(slices, led, executor=ex, judge_fn=_judge, max_workers=4)
    assert sorted(res.completed) == ["A", "B"]
    assert ex.dispatched.index("A") < ex.dispatched.index("B")


def test_parallel_skips_ledger_done(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    led.set("A", status=DONE)
    slices = [_slice("A"), _slice("B")]
    ex = FakeExecutor()
    res = run_plan_parallel(slices, led, executor=ex, judge_fn=_judge, max_workers=2)
    assert res.skipped == ["A"]
    assert res.completed == ["B"]
    assert "A" not in ex.dispatched


def test_parallel_persists_to_ledger(tmp_path):
    p = str(tmp_path / "l.json")
    led = Ledger(p)
    ex = FakeExecutor()
    run_plan_parallel([_slice("A"), _slice("B")], led, executor=ex, judge_fn=_judge,
                      max_workers=2)
    reloaded = Ledger.load(p)
    assert reloaded.is_done("A") and reloaded.is_done("B")


def test_quota_check_throttles_dispatch(tmp_path):
    """When quota_check reports over-cap, slices are deferred (not dispatched) and
    recorded as skipped-for-quota rather than run."""
    led = Ledger(str(tmp_path / "l.json"))
    ex = FakeExecutor()

    # quota_check returns a percentage; threshold default behaviour: >= 95 -> defer
    def over_quota():
        return 99

    res = run_plan_parallel(
        [_slice("A"), _slice("B")], led, executor=ex, judge_fn=_judge,
        max_workers=2, quota_check=over_quota, quota_threshold=95,
    )
    # nothing dispatched while over quota
    assert ex.dispatched == []
    assert sorted(res.deferred) == ["A", "B"]
    assert res.completed == []


def test_quota_under_threshold_runs_normally(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))
    ex = FakeExecutor()
    res = run_plan_parallel(
        [_slice("A")], led, executor=ex, judge_fn=_judge,
        max_workers=1, quota_check=lambda: 10, quota_threshold=95,
    )
    assert res.completed == ["A"]
    assert res.deferred == []


def test_run_plan_parallel_accepts_executor_factory(tmp_path):
    # Additive, backward-compatible: run_plan_parallel accepts executor_factory + default_spec.
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    class _Exec:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")

    slices = [SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py")]
    ledger = Ledger(str(tmp_path / "l.json"))
    res = run_plan_parallel(
        slices, ledger,
        executor=_Exec(),
        executor_factory=None,
        default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    assert "T1" in res.completed


def test_each_slice_uses_its_own_tagged_executor(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    ran = {}  # slice_id -> spec the executor was built from

    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, task, workdir, feedback=None):
            ran[task.id] = self.spec
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")

    slices = [
        SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py"),
        SliceTask(id="T2", brief="b", files=["y"], acceptance_test_path="t.py",
                  executor="opencode:opencode/claude-sonnet-4-6"),
    ]
    ledger = Ledger(str(tmp_path / "l.json"))
    run_plan_parallel(
        slices, ledger,
        executor_factory=lambda spec: _Rec(spec),
        default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    assert ran["T1"] == "gemini"
    assert ran["T2"] == "opencode:opencode/claude-sonnet-4-6"


def test_unknown_per_slice_executor_fails_only_that_slice(tmp_path):
    # An unknown executor spec must FAIL that slice, not crash the build; siblings still run.
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    class _Ok:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")

    def factory(spec):
        if spec.startswith("bogus"):
            raise ValueError(f"Unknown executor: {spec!r}")
        return _Ok()

    slices = [
        SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py"),  # ok
        SliceTask(id="T2", brief="b", files=["y"], acceptance_test_path="t.py",
                  executor="bogus:whatever"),                                       # bad
    ]
    ledger = Ledger(str(tmp_path / "l.json"))
    res = run_plan_parallel(
        slices, ledger,
        executor_factory=factory, default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    assert "T1" in res.completed          # the good slice still ran
    assert "T2" in res.failed             # the bad slice failed
    assert "T2" not in res.completed
