# Telemetry dogfood — by-model rollup + OtelSink (independent slices)

Two pure, independent slices for the telemetry feature. Package `cld` under `engine/`,
Python 3.11+. Spec: docs/superpowers/specs/2026-06-25-agent-telemetry-and-monitoring-design.md.

## SLICE: BYMODEL
executor: opencode:opencode/glm-5.2
brief: Extend `engine/cld/status.py` (keep `render_status`'s existing behaviour and the existing
  tests/test_status.py passing) to add a "by model" rollup to the digest. From the event stream,
  attribute each slice to the model that ran it (the `model` on its `dispatch_start`), and for each
  distinct model show: the model string, the slice ids that ran on it, the summed tokens for those
  slices (sum of `tokens["total"]` from each slice's `dispatch_end`), and the `source` (tag / default
  / auto / escalated) seen for that model's dispatches. Emit one extra line beginning with the text
  `by model:` listing each model group. Example shape (NOT rigid):
    `by model: antigravity:Gemini 3.1 Pro (High) [T1 (default) 1000tok] | opencode:opencode/glm-5.2 [T2 (tag) 5000tok]`
  Keep it cp1252-safe (ASCII punctuation only). Do not edit the test file. Match tests/test_status_bymodel.py.
files: engine/cld/status.py
acceptance_test_path: tests/test_status_bymodel.py
deps:

## SLICE: OTEL
executor: opencode:opencode/glm-5.2
brief: Add `class OtelSink(Sink)` to `engine/cld/telemetry.py` (keep everything else intact). It maps
  the telemetry event stream to OpenTelemetry spans, GUARDED so a missing/None tracer is a silent
  no-op (telemetry must never break a build).
  Constructor: `OtelSink(tracer=None)` where `tracer` is an OpenTelemetry Tracer (or None). When None,
  every `emit` is a no-op and must not raise.
  Behaviour with a tracer: maintain a per-slice dispatch span.
  - On a `dispatch_start` event: start a span named `cld.dispatch` (use
    `tracer.start_span("cld.dispatch")`), keyed by the event's `slice_id`, and set attributes
    `cld.slice_id`=slice_id, `cld.rung`=rung, `cld.source`=source, `gen_ai.request.model`=model.
  - On the matching `dispatch_end` (same `slice_id`): set `gen_ai.usage.input_tokens`,
    `gen_ai.usage.output_tokens` (from the event's `tokens` dict keys "input"/"output", when present),
    `cld.rc`=rc, then `.end()` the span.
  - All other event types: ignore.
  - Never raise from `emit` (wrap span work in try/except; a failing export must be swallowed).
  Stdlib + `opentelemetry` only; import opentelemetry lazily/guarded if needed, but the tracer is
  injected so no global setup is required. Do not edit the test file. Match tests/test_otel_sink.py.
files: engine/cld/telemetry.py
acceptance_test_path: tests/test_otel_sink.py
deps:
