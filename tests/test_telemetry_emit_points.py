"""Integration: run_plan_parallel / deliver_slice emit the expected ordered event stream.

The lead agent reconstructs build state from this stream, so the per-slice lifecycle
(slice_start -> dispatch_start -> dispatch_end -> judge_verdict -> slice_done) and the
field contract on each event are what `--status` and the OTel exporter rely on.
"""
import json

from cld import telemetry
from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.orchestrator import run_plan_parallel


class _Cap:
    def __init__(self):
        self.records = []

    def emit(self, r):
        self.records.append(r)


class _PassExec:
    def run(self, task, workdir, feedback=None):
        return ExecutorResult(ok=True, diff="+x", files_changed=[f"src/{task.id}.py"],
                              raw_log="1 passed in 0.1s", token_usage={"total": 10})


class _FailExec:
    def run(self, task, workdir, feedback=None):
        # writes a disallowed file so the judge fails every attempt
        return ExecutorResult(ok=True, diff="+x", files_changed=["NOT_ALLOWED.py"],
                              raw_log="", token_usage={"total": 3})


def _judge(files_changed, allowed, run_tests):
    from cld.judge import judge as _j
    return _j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


def test_passing_slice_emits_ordered_sequence(tmp_path):
    cap = _Cap()
    telemetry.set_sink(cap)
    telemetry.set_run_id("run1")
    try:
        led = Ledger(str(tmp_path / "l.json"))
        task = SliceTask(id="T1", brief="b", files=["src/T1.py"], acceptance_test_path="t.py")
        run_plan_parallel([task], led, executor=_PassExec(), judge_fn=_judge,
                          test_runner=lambda *a: "1 passed in 0.1s", max_workers=1)
    finally:
        telemetry.set_run_id(None)

    seq = [r["type"] for r in cap.records]
    assert seq == ["slice_start", "dispatch_start", "dispatch_end", "judge_verdict", "slice_done"]

    ds = next(r for r in cap.records if r["type"] == "dispatch_start")
    assert ds["slice_id"] == "T1" and "model" in ds and ds["attempt"] == 1 and "run_id" in ds
    de = next(r for r in cap.records if r["type"] == "dispatch_end")
    assert de["tokens"] == {"total": 10} and de["rc"] == 0 and "ms" in de
    jv = next(r for r in cap.records if r["type"] == "judge_verdict")
    assert jv["passed"] is True and jv["attempt"] == 1
    sd = next(r for r in cap.records if r["type"] == "slice_done")
    assert sd["status"] == "completed"


def test_failing_slice_emits_retry_then_failed(tmp_path):
    cap = _Cap()
    telemetry.set_sink(cap)
    telemetry.set_run_id("run2")
    try:
        led = Ledger(str(tmp_path / "l.json"))
        task = SliceTask(id="T9", brief="b", files=["src/T9.py"], acceptance_test_path="t.py")
        # max_retries=1 -> 2 attempts, both fail (disallowed edit)
        run_plan_parallel([task], led, executor=_FailExec(), judge_fn=_judge,
                          test_runner=lambda *a: "1 passed in 0.1s", max_workers=1, max_retries=1)
    finally:
        telemetry.set_run_id(None)

    seq = [r["type"] for r in cap.records]
    assert seq.count("dispatch_start") == 2  # original + one retry
    assert "retry" in seq
    assert seq[-1] == "slice_done"
    sd = cap.records[-1]
    assert sd["status"] == "failed"


def test_status_is_fresh_mid_run(tmp_path):
    """Spec P2: while a build is genuinely in-flight, polling the on-disk stream (as
    `--status` does) shows the slice as RUNNING -- proving per-event flush + running-slice
    reconstruction compose live, not just in isolation."""
    import threading
    from cld.telemetry import JsonlSink
    from cld.status import render_status
    import skill.scripts.run_delivery as rd

    events_path = tmp_path / ".cld" / "events.jsonl"
    events_path.parent.mkdir(parents=True)

    started = threading.Event()
    release = threading.Event()

    class _BlockingExec:
        def run(self, task, workdir, feedback=None):
            started.set()               # dispatch_start is already emitted + flushed by now
            release.wait(timeout=5)      # hold the slice in-flight while the test polls
            return ExecutorResult(ok=True, diff="+x", files_changed=[f"src/{task.id}.py"],
                                  raw_log="1 passed", token_usage={"total": 10})

    telemetry.set_sink(JsonlSink(str(events_path)))
    telemetry.set_run_id("live1")
    try:
        led = Ledger(str(tmp_path / "l.json"))
        task = SliceTask(id="T1", brief="b", files=["src/T1.py"], acceptance_test_path="t.py")
        th = threading.Thread(target=lambda: run_plan_parallel(
            [task], led, executor=_BlockingExec(), judge_fn=_judge,
            test_runner=lambda *a: "1 passed", max_workers=1))
        th.start()
        try:
            assert started.wait(timeout=5), "executor never started"
            out = render_status(rd._read_event_stream(str(tmp_path)))  # exactly what --status reads
            assert "T1" in out and "running" in out.lower()
        finally:
            release.set()
            th.join(timeout=5)
    finally:
        telemetry.set_sink(None)
        telemetry.set_run_id(None)


def test_run_delivery_writes_live_event_stream(tmp_path, monkeypatch):
    """run_delivery --step installs the JsonlSink, writes .cld/events.jsonl with a stable
    run_id, and brackets the layer with run_start/layer_start/layer_done/run_done."""
    import skill.scripts.run_delivery as rd
    from cld.orchestrator import PlanResult

    plan = tmp_path / "plan.md"
    plan.write_text("## SLICE: A\nbrief: b\nfiles: x.py\nacceptance_test_path: t.py\ndeps:\n",
                    encoding="utf-8")

    def fake_rpp(slices, ledger, **kw):
        r = PlanResult()
        for s in slices:
            telemetry.emit("slice_start", slice_id=s.id)
            ledger.set(s.id, status="done")
            ledger.save()
            telemetry.emit("slice_done", slice_id=s.id, status="completed")
            r.completed.append(s.id)
        return r

    monkeypatch.setattr(rd, "run_plan_parallel", fake_rpp)
    # Neutralize the preflights: this test is about the event stream, and must pass on machines
    # (e.g. CI, tmp dirs) with no executor CLI installed and no git repo at the target path.
    monkeypatch.setattr(rd, "_preflight_executor", lambda spec: None)
    monkeypatch.setattr(rd, "_preflight_git", lambda repo: None)
    try:
        rc = rd.main([str(plan), "--repo", str(tmp_path), "--ledger", str(tmp_path / "l.json"),
                      "--executor", "antigravity", "--step", "--workers", "1"])
    finally:
        telemetry.set_sink(None)
        telemetry.set_run_id(None)

    lines = (tmp_path / ".cld" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    recs = [json.loads(ln) for ln in lines if ln.strip()]
    types = [r["type"] for r in recs]
    for expected in ("run_start", "layer_start", "slice_start", "slice_done", "layer_done", "run_done"):
        assert expected in types, f"{expected} missing from {types}"
    # run_id present + stable across the whole stream
    rids = {r.get("run_id") for r in recs}
    assert len(rids) == 1 and None not in rids
    assert rc == 3  # single layer done -> build complete (the --step "no further layers" code)
