"""Acceptance tests for cld.telemetry (the agent-telemetry foundation).

Slice S1 = TestSinks (Sink / JsonlSink / MultiSink).
Slice S2 = TestEmit  (emit / set_sink / get_sink + event record building).

These are the committed-failing contracts the executor implements against.
"""
import json
import threading
from pathlib import Path


class TestSinks:  # ---- Slice S1 ----
    def test_jsonl_sink_appends_one_json_line_per_record(self, tmp_path):
        from cld.telemetry import JsonlSink
        p = tmp_path / "events.jsonl"
        s = JsonlSink(str(p))
        s.emit({"type": "a", "x": 1})
        s.emit({"type": "b", "y": 2})
        lines = p.read_text(encoding="utf-8").splitlines()
        assert [json.loads(ln) for ln in lines] == [{"type": "a", "x": 1}, {"type": "b", "y": 2}]

    def test_jsonl_sink_is_thread_safe(self, tmp_path):
        # the orchestrator emits from a ThreadPoolExecutor: concurrent writes must not
        # interleave/corrupt; every line must be intact JSON and none may be lost.
        from cld.telemetry import JsonlSink
        p = tmp_path / "e.jsonl"
        s = JsonlSink(str(p))

        def worker(n):
            for i in range(50):
                s.emit({"n": n, "i": i})

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 8 * 50
        for ln in lines:
            json.loads(ln)  # raises if any line is corrupted/interleaved

    def test_multisink_fans_out_and_isolates_a_failing_sink(self):
        from cld.telemetry import MultiSink
        got_a, got_b = [], []

        class A:
            def emit(self, record):
                got_a.append(record)

        class Boom:
            def emit(self, record):
                raise RuntimeError("sink down")

        class B:
            def emit(self, record):
                got_b.append(record)

        m = MultiSink([A(), Boom(), B()])
        m.emit({"k": 1})  # must NOT raise even though the middle sink throws
        assert got_a == [{"k": 1}]
        assert got_b == [{"k": 1}]  # a failing sink must not stop the others


class TestEmit:  # ---- Slice S2 ----
    def test_set_and_get_sink_roundtrip(self):
        from cld import telemetry

        class Cap:
            def emit(self, record):
                pass

        sink = Cap()
        telemetry.set_sink(sink)
        assert telemetry.get_sink() is sink

    def test_emit_builds_a_record_with_type_fields_and_timestamp(self):
        from cld import telemetry
        captured = []

        class Cap:
            def emit(self, record):
                captured.append(record)

        telemetry.set_sink(Cap())
        telemetry.emit("dispatch_start", slice_id="T1", model="opencode:glm-5.2")
        assert len(captured) == 1
        rec = captured[0]
        assert rec["type"] == "dispatch_start"
        assert rec["slice_id"] == "T1"
        assert rec["model"] == "opencode:glm-5.2"
        assert "ts" in rec and rec["ts"]  # an ISO-ish timestamp string is added

    def test_emit_is_best_effort_and_never_raises(self):
        from cld import telemetry

        class Boom:
            def emit(self, record):
                raise RuntimeError("sink down")

        telemetry.set_sink(Boom())
        telemetry.emit("anything", a=1)  # telemetry must never break the build


class TestRunId:  # ---- run_id threading (wiring contract) ----
    def test_set_run_id_is_injected_into_every_record(self):
        from cld import telemetry
        captured = []

        class Cap:
            def emit(self, record):
                captured.append(record)

        telemetry.set_sink(Cap())
        telemetry.set_run_id("a1b2c3")
        try:
            telemetry.emit("run_start", plan="p.md")
            assert captured[-1]["run_id"] == "a1b2c3"
        finally:
            telemetry.set_run_id(None)  # don't leak into other tests

    def test_run_id_absent_when_unset(self):
        from cld import telemetry
        captured = []

        class Cap:
            def emit(self, record):
                captured.append(record)

        telemetry.set_run_id(None)
        telemetry.set_sink(Cap())
        telemetry.emit("slice_start", slice_id="T1")
        assert "run_id" not in captured[-1]  # additive: omitted, not null
