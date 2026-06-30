# Telemetry foundation — dogfood plan (S1, S2)

Pilot slices for the agent-telemetry feature, used to evaluate GLM 5.2 (via opencode) as the
executor. Spec: `docs/superpowers/specs/2026-06-25-agent-telemetry-and-monitoring-design.md`.
Engine layout: the package is `cld` under `engine/` (pytest resolves it via pyproject `pythonpath`).
All code is Python 3.11+, standard library only.

## SLICE: S1
executor: opencode:opencode/glm-5.2
brief: Create the file `engine/cld/telemetry.py`. It must provide three names, stdlib only:
  (1) `Sink` — a `typing.Protocol` (runtime not required) declaring `def emit(self, record: dict) -> None`.
  (2) `JsonlSink` — `class JsonlSink:` constructed as `JsonlSink(path: str)`. Its `.emit(record: dict)`
      appends exactly ONE line to `path`: `json.dumps(record)` + "\n", opened with `encoding="utf-8"`,
      and flushed so the line is immediately on disk. It MUST be thread-safe: guard the write with a
      `threading.Lock` so concurrent `.emit()` calls from multiple threads never interleave or lose a
      line (the orchestrator emits from a thread pool). Create the parent directory if missing.
  (3) `MultiSink` — `class MultiSink:` constructed as `MultiSink(sinks: list)`. Its `.emit(record)`
      calls `.emit(record)` on each child sink in order, and is BEST-EFFORT: if one child raises, it
      is swallowed and the remaining children still receive the record (never re-raise).
  Do not add anything else in this slice (no `emit()` function yet). Match the acceptance tests exactly.
files: engine/cld/telemetry.py
acceptance_test_path: tests/test_telemetry.py::TestSinks
deps:

## SLICE: S2
executor: opencode:opencode/glm-5.2
brief: Extend `engine/cld/telemetry.py` (keep S1's `Sink`/`JsonlSink`/`MultiSink` intact) with a
  module-level emitter, stdlib only:
  (1) A module global current sink, defaulting to a no-op sink (an object whose `.emit` does nothing),
      with `set_sink(sink) -> None` and `get_sink()` accessors. `get_sink()` returns the sink last set
      by `set_sink` (roundtrip).
  (2) `emit(event_type: str, **fields) -> None` — builds a record
      `{"ts": <timestamp>, "type": event_type, **fields}` where `ts` is an ISO-8601-ish timestamp
      string (e.g. `datetime.now(timezone.utc).isoformat()`), then forwards it to the current sink via
      `.emit(record)`. It MUST be BEST-EFFORT: wrap the sink call in try/except and never raise (a
      failing/raising sink must not propagate — telemetry must never break a build).
  Match the acceptance tests exactly.
files: engine/cld/telemetry.py
acceptance_test_path: tests/test_telemetry.py::TestEmit
deps: S1
