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


def test_otel_target_is_the_configured_endpoint_only():
    from skill.scripts.run_delivery import _otel_target_from_env
    env = {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318/v1/traces",
           "OTEL_EXPORTER_OTLP_HEADERS": "x-key=secret",
           "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}
    assert _otel_target_from_env(env) == "http://collector:4318/v1/traces"


def test_otel_target_none_when_unconfigured():
    from skill.scripts.run_delivery import _otel_target_from_env
    assert _otel_target_from_env({}) is None


HEADER_VARIABLES = ("OTEL_EXPORTER_OTLP_HEADERS", "OTEL_EXPORTER_OTLP_TRACES_HEADERS")


def _export_one_span(monkeypatch, headers_env):
    """Export one span to a loopback collector through _maybe_otel_sink and return the POSTs.

    Every header variable is cleared or set to synthetic values first, so an ambient token
    can never reach the collector or a failure message."""
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from skill.scripts import run_delivery

    received = []

    class _Collector(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            received.append((self.path, self.headers.get("Authorization"), len(body)))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), _Collector)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        for name in HEADER_VARIABLES:
            monkeypatch.delenv(name, raising=False)
        for name, value in headers_env.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://127.0.0.1:{port}/v1/traces")
        sink = run_delivery._maybe_otel_sink()
        assert sink is not None, "OTLP sink was not built"
        sink.emit({"type": "dispatch_start", "slice_id": "T1", "model": "m",
                   "rung": "workhorse", "source": "tag"})
        sink.emit({"type": "dispatch_end", "slice_id": "T1", "model": "m", "rc": 0,
                   "tokens": {"input": 10, "output": 5, "total": 15}, "ms": 100})
        sink.close()

        deadline = time.time() + 5
        while not received and time.time() < deadline:
            time.sleep(0.05)
        return received
    finally:
        srv.shutdown()


def test_otel_live_export_round_trip(monkeypatch):
    """End-to-end: CLD's sink -> OTLP/HTTP exporter -> a real span POST to the configured
    endpoint, with no credentials added by CLD. Uses a loopback HTTP collector so no
    external backend is needed."""
    received = _export_one_span(monkeypatch, {})
    assert received, "no OTLP export POST received"
    path, auth, size = received[0]
    assert size > 0 and path.endswith("/v1/traces")
    assert auth is None


def test_sdk_applies_the_standard_headers_variable_itself(monkeypatch):
    """Documented boundary: CLD reads no header variable, but the OpenTelemetry SDK applies
    OTEL_EXPORTER_OTLP_HEADERS on its own. Synthetic value only."""
    received = _export_one_span(monkeypatch, {"OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer%20synthetic"})
    assert received, "no OTLP export POST received"
    assert received[0][1] == "Bearer synthetic"
