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


def test_usage_written_to_ledger_on_completion(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    class _Exec:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="+x", files_changed=["x"],
                                  token_usage={"input": 10, "output": 2, "total": 12},
                                  raw_log="")

    slices = [SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py")]
    p = str(tmp_path / "l.json")
    ledger = Ledger(p)
    run_plan_parallel(
        slices, ledger, executor=_Exec(),
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    e = Ledger.load(p).get("T1")
    assert e.status == "done"
    assert e.token_usage == {"input": 10, "output": 2, "total": 12}
    assert e.model  # a model string was recorded (non-empty)


def test_no_slice_pick_fn_is_current_behavior(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult
    seen = []
    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, t, w, feedback=None):
            seen.append(self.spec); return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")
    run_plan_parallel(
        [SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py")],
        Ledger(str(tmp_path / "l.json")),
        executor_factory=lambda s: _Rec(s), default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed")
    assert seen == ["gemini"]   # no pick_fn -> build default (S1b preserved)


def test_resolved_spec_recorded_in_ledger_per_slice(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")

    slices = [
        SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py"),  # untagged -> default
        SliceTask(id="T2", brief="b", files=["y"], acceptance_test_path="t.py",
                  executor="cursor:composer-2.5"),                                 # tagged
    ]
    ledger = Ledger(str(tmp_path / "l.json"))
    run_plan_parallel(
        slices, ledger,
        executor_factory=lambda spec: _Rec(spec), default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    assert ledger.get("T1").model == "gemini"              # untagged -> default spec recorded
    assert ledger.get("T2").model == "cursor:composer-2.5"  # tag spec recorded


def test_effort_recorded_from_spec_suffix(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult
    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")
    slices = [
        SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py",
                  executor="cursor:claude-opus-4-8@medium"),   # tagged w/ effort
        SliceTask(id="T2", brief="b", files=["y"], acceptance_test_path="t.py",
                  executor="gemini"),                          # no effort
    ]
    ledger = Ledger(str(tmp_path / "l.json"))
    run_plan_parallel(
        slices, ledger,
        executor_factory=lambda spec: _Rec(spec), default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    assert ledger.get("T1").effort == "medium"
    assert ledger.get("T2").effort is None
    assert ledger.get("T1").model == "cursor:claude-opus-4-8@medium"  # model unchanged (full spec)


def test_leaf_slice_unchanged_no_subslice_ledger_keys(tmp_path):
    # A normal leaf slice must NOT create any "/"-keyed child entries.
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult
    class _Ok:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")
    p = str(tmp_path / "l.json")
    ledger = Ledger(p)
    run_plan_parallel(
        [SliceTask(id="L", brief="b", files=["x"], acceptance_test_path="t.py")],
        ledger, executor=_Ok(),
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed")
    keys = list(Ledger.load(p).entries.keys())
    assert keys == ["L"]   # no child keys


def test_ladder_climbs_quick_to_workhorse(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    used = []
    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, task, workdir, feedback=None):
            used.append(self.spec)
            ok = self.spec == "wh"           # quick fails, workhorse passes
            return ExecutorResult(ok=ok, diff="", files_changed=["x"], raw_log="")

    def judge(**kw):
        passed = kw["run_tests"]() == "ok"
        return type("J", (), {"passed": passed, "failing_tests": []})()
    def tr(workdir, path=None):
        return "ok" if used and used[-1] == "wh" else "no"

    planner = lambda task: [("quick", "qk", 1), ("workhorse", "wh", 2)]
    p = str(tmp_path / "l.json"); ledger = Ledger(p)
    res = run_plan_parallel(
        [SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py", complexity="easy")],
        ledger, executor_factory=lambda spec: _Rec(spec), default_spec="gemini",
        rung_planner=planner, judge_fn=judge, test_runner=tr)
    assert used == ["qk", "wh"]                 # climbed
    assert "S" in res.completed
    assert ledger.get("S").final_rung == "workhorse"
    assert ledger.get("S").complexity == "easy"


def test_ladder_all_cheap_fail_yields_needs_repair(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult
    class _Fail:
        def __init__(self, spec): pass
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=["x"], raw_log="")
    judge = lambda **kw: type("J", (), {"passed": False, "failing_tests": ["t::x"]})()
    planner = lambda task: [("workhorse", "wh", 1)]
    p = str(tmp_path / "l.json"); ledger = Ledger(p)
    res = run_plan_parallel(
        [SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py", complexity="complex")],
        ledger, executor_factory=lambda s: _Fail(s), default_spec="gemini",
        rung_planner=planner, judge_fn=judge, test_runner=lambda *a, **k: "no")
    assert "S" in res.needs_repair and "S" not in res.failed and "S" not in res.completed
    assert ledger.get("S").status == "needs_repair"
    assert ledger.get("S").final_rung == "orchestrator"


def test_no_rung_planner_is_current_behavior(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult
    seen = []
    class _Ok:
        def __init__(self, spec): seen.append(spec)
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")
    res = run_plan_parallel(
        [SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py")],
        Ledger(str(tmp_path / "l.json")),
        executor_factory=lambda s: _Ok(s), default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed")
    assert seen == ["gemini"] and "S" in res.completed   # unchanged single-dispatch path


def test_chosen_by_recorded(tmp_path):
    """Ledger records chosen_by: "you" for explicit executor tag, "rec" for auto-routed."""
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    class _Ok:
        def __init__(self, spec): pass
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=["x"], raw_log="")

    slices = [
        SliceTask(id="A", brief="b", files=["x"], acceptance_test_path="t.py"),  # untagged -> rec
        SliceTask(id="B", brief="b", files=["y"], acceptance_test_path="t.py",
                  executor="opencode:opencode/deepseek-v4-pro"),  # tagged -> you
    ]
    p = str(tmp_path / "l.json")
    ledger = Ledger(p)
    run_plan_parallel(slices, ledger,
        executor_factory=lambda s: _Ok(s), default_spec="gemini",
        rung_planner=lambda task: [("workhorse", task.executor or "gemini", 2)],
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "ok")

    assert ledger.get("A").chosen_by == "rec"
    assert ledger.get("B").chosen_by == "you"


