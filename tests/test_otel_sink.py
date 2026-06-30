"""Acceptance test for cld.telemetry.OtelSink — the OpenTelemetry export seam (Phase 3).

Maps the event stream to spans with GenAI semantic attributes, exported via OTel.
Tested against the SDK's InMemorySpanExporter. Guarded: a None tracer is a no-op.
"""
import pytest


def _otel_pieces():
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("cld"), exporter


def test_otel_sink_emits_dispatch_span_with_genai_attrs():
    tracer, exporter = _otel_pieces()
    from cld.telemetry import OtelSink
    sink = OtelSink(tracer=tracer)
    sink.emit({"type": "run_start", "run_id": "r1", "plan": "p.md"})
    sink.emit({"type": "dispatch_start", "slice_id": "T1", "model": "opencode:opencode/glm-5.2",
               "rung": "workhorse", "source": "tag", "attempt": 1})
    sink.emit({"type": "dispatch_end", "slice_id": "T1", "model": "opencode:opencode/glm-5.2",
               "rc": 0, "tokens": {"input": 10, "output": 5, "total": 15}, "ms": 120})
    sink.emit({"type": "run_done", "gate": "passed"})

    spans = exporter.get_finished_spans()
    disp = [s for s in spans if "dispatch" in s.name.lower()]
    assert disp, [s.name for s in spans]
    attrs = dict(disp[0].attributes or {})
    assert attrs.get("gen_ai.request.model") == "opencode:opencode/glm-5.2"
    assert attrs.get("gen_ai.usage.input_tokens") == 10
    assert attrs.get("gen_ai.usage.output_tokens") == 5
    assert attrs.get("cld.slice_id") == "T1"
    assert attrs.get("cld.rung") == "workhorse"


def test_otel_sink_is_noop_without_tracer():
    from cld.telemetry import OtelSink
    # No tracer (SDK absent / not configured) must never raise — telemetry stays best-effort.
    OtelSink(tracer=None).emit({"type": "dispatch_start", "slice_id": "X", "model": "m"})
