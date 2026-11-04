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


def test_otel_live_export_round_trip():
    """End-to-end: OtelSink -> OTLP/HTTP exporter -> a real span POST to the configured
    endpoint, with no credentials added by CLD. Uses a loopback HTTP collector so no
    external backend is needed."""
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, HTTPServer

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
        from skill.scripts.run_delivery import _otel_target_from_env
        endpoint = _otel_target_from_env({
            "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{port}/v1/traces"})

        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from cld.telemetry import OtelSink

        prov = TracerProvider()
        prov.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        sink = OtelSink(tracer=prov.get_tracer("cld"))
        sink.emit({"type": "dispatch_start", "slice_id": "T1", "model": "m",
                   "rung": "workhorse", "source": "tag"})
        sink.emit({"type": "dispatch_end", "slice_id": "T1", "model": "m", "rc": 0,
                   "tokens": {"input": 10, "output": 5, "total": 15}, "ms": 100})
        prov.force_flush()

        deadline = time.time() + 3
        while not received and time.time() < deadline:
            time.sleep(0.05)
        assert received, "no OTLP export POST received"
        path, auth, size = received[0]
        assert size > 0 and path.endswith("/v1/traces")
        assert auth is None
    finally:
        srv.shutdown()
