"""T5.5: dispatch span emission — observability for executor runs.

record_dispatch emits a Langfuse span per dispatch with the dispatch facts, and
is a safe no-op when no tracer is available (Langfuse keys absent). An injected
tracer lets us assert the payload without a live Langfuse.
"""

from cld.tracing import record_dispatch


class FakeTracer:
    """Captures span payloads. Mirrors the minimal interface record_dispatch uses."""

    def __init__(self):
        self.spans = []

    def span(self, *, name, metadata):
        self.spans.append({"name": name, "metadata": metadata})


def test_record_dispatch_emits_span_with_payload():
    tr = FakeTracer()
    record_dispatch(
        slice_id="T3.3",
        model="gemini-3.1-pro-preview",
        token_usage={"total": 78494, "output": 1063},
        accepted=True,
        attempts=1,
        diff_len=512,
        failing_tests=[],
        tracer=tr,
    )
    assert len(tr.spans) == 1
    md = tr.spans[0]["metadata"]
    assert md["slice_id"] == "T3.3"
    assert md["model"] == "gemini-3.1-pro-preview"
    assert md["accepted"] is True
    assert md["attempts"] == 1
    assert md["token_usage"]["total"] == 78494
    assert md["diff_len"] == 512
    assert md["failing_tests"] == []


def test_record_dispatch_span_name_includes_slice():
    tr = FakeTracer()
    record_dispatch(
        slice_id="T9", model="m", token_usage={}, accepted=False,
        attempts=3, diff_len=0, failing_tests=["t.py::x"], tracer=tr,
    )
    assert "T9" in tr.spans[0]["name"]
    assert tr.spans[0]["metadata"]["accepted"] is False
    assert tr.spans[0]["metadata"]["failing_tests"] == ["t.py::x"]


def test_record_dispatch_noop_when_no_tracer(monkeypatch):
    # No tracer passed AND no Langfuse keys -> must NOT raise (safe no-op).
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    # Should simply return without error.
    record_dispatch(
        slice_id="T1", model="m", token_usage={}, accepted=True,
        attempts=1, diff_len=10, failing_tests=[],
    )


def test_record_dispatch_swallows_tracer_errors():
    class BrokenTracer:
        def span(self, *, name, metadata):
            raise RuntimeError("langfuse down")

    # A tracer failure must never break the build pipeline.
    record_dispatch(
        slice_id="T1", model="m", token_usage={}, accepted=True,
        attempts=1, diff_len=10, failing_tests=[], tracer=BrokenTracer(),
    )
