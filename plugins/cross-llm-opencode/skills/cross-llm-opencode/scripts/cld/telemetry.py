"""Agent-telemetry sinks (Slice S1).

Telemetry is the observability spine of the orchestrator: every dispatch emits a
structured record so that builds can be replayed/judged offline. A *sink* is the
pluggable destination for those records.

This module defines three names, stdlib only:

* ``Sink``      -- abstract base; subclasses implement ``emit(record)``.
* ``JsonlSink`` -- appends one compact JSON line per record to a file. Writes are
  serialized by a lock so the orchestrator's ThreadPoolExecutor can emit
  concurrently without interleaving/corrupting lines or losing records.
* ``MultiSink`` -- fans each record out to a list of child sinks. A raising child
  is isolated: the exception is swallowed so one bad sink can never break the
  build or starve its siblings.

Slice S2 (``emit`` / ``set_sink`` / ``get_sink``) is added later on top of these.
"""

import datetime
import json
import threading


_sink: "Sink | None" = None
_sink_lock = threading.Lock()
_run_id: "str | None" = None  # stable id per run; set once by run_delivery, shared by all events


def set_run_id(run_id) -> None:
    """Install the process-global run id stamped onto every emitted record."""
    global _run_id
    _run_id = run_id


class Sink:
    """Abstract telemetry sink.

    A sink consumes one record (a JSON-serializable dict) at a time via
    ``emit``. Subclasses override ``emit``; the base raises to flag
    "not wired up".
    """

    def emit(self, record) -> None:
        raise NotImplementedError


class JsonlSink(Sink):
    """Append one JSON line per record to a JSONL file, thread-safe.

    The file is opened once in append mode and every write is guarded by a
    per-sink lock, so concurrent emitters (the orchestrator uses a
    ThreadPoolExecutor) cannot interleave bytes within a line, drop a record,
    or corrupt the stream. Each record is written as ``json.dumps(record)``
    followed by a single ``\\n`` and flushed immediately.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._fh = open(path, "a", encoding="utf-8")

    def emit(self, record) -> None:
        line = json.dumps(record)
        with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()


class MultiSink(Sink):
    """Fan out records to many sinks, isolating failures.

    ``emit`` forwards the record to every child sink in order. If a child
    raises, the exception is swallowed (best-effort telemetry must never break
    the build) and the remaining children still receive the record.
    """

    def __init__(self, sinks) -> None:
        self._sinks = list(sinks)

    def emit(self, record) -> None:
        for s in self._sinks:
            try:
                s.emit(record)
            except Exception:
                # A failing sink must not stop the others nor surface upward.
                pass


class OtelSink(Sink):
    """Map the event stream to OpenTelemetry spans (GenAI semantic attributes).

    Each dispatch becomes one span: opened on ``dispatch_start`` and closed on
    ``dispatch_end``, carrying OpenTelemetry GenAI semantic-convention
    attributes (``gen_ai.request.model``, ``gen_ai.usage.input_tokens`` /
    ``gen_ai.usage.output_tokens``) plus cld-specific ones
    (``cld.slice_id``, ``cld.rung``). Spans are tracked by ``slice_id`` so the
    matching end event can stamp usage and finish them.

    With ``tracer=None`` (SDK absent / not configured) the sink is a silent
    no-op: telemetry stays best-effort and must never break the build.
    """

    def __init__(self, tracer=None) -> None:
        self._tracer = tracer
        self._spans: dict = {}  # slice_id -> open span

    def emit(self, record) -> None:
        if self._tracer is None:
            return
        try:
            self._handle(record)
        except Exception:
            # Best-effort telemetry: never break the build.
            pass

    def _handle(self, record) -> None:
        rtype = record.get("type")
        if rtype == "dispatch_start":
            slice_id = record.get("slice_id")
            if slice_id is None:
                return
            attrs = {
                "gen_ai.request.model": record.get("model"),
                "cld.slice_id": slice_id,
                "cld.rung": record.get("rung"),
                "cld.source": record.get("source"),
                "cld.attempt": record.get("attempt"),
            }
            attrs = {k: v for k, v in attrs.items() if v is not None}
            span = self._tracer.start_span("cld.dispatch", attributes=attrs)
            self._spans[slice_id] = span
        elif rtype == "dispatch_end":
            slice_id = record.get("slice_id")
            span = self._spans.pop(slice_id, None)
            if span is None:
                return
            tokens = record.get("tokens") or {}
            attrs = {
                "gen_ai.usage.input_tokens": tokens.get("input", 0),
                "gen_ai.usage.output_tokens": tokens.get("output", 0),
                "gen_ai.usage.total_tokens": tokens.get("total", 0),
                "cld.rc": record.get("rc"),
                "cld.ms": record.get("ms"),
            }
            attrs = {k: v for k, v in attrs.items() if v is not None}
            span.set_attributes(attrs)
            span.end()


def set_sink(sink) -> None:
    """Install the process-global telemetry sink (replaces any prior sink)."""
    global _sink
    with _sink_lock:
        _sink = sink


def get_sink():
    """Return the currently-installed telemetry sink (or ``None``)."""
    with _sink_lock:
        return _sink


def emit(event_type: str, **fields) -> None:
    """Emit one telemetry event to the global sink, best-effort.

    A record is built as ``{"type": event_type, **fields, "ts": <iso utc>}``
    and forwarded to the sink installed via :func:`set_sink`. Telemetry must
    never break the build: any exception raised by the sink (or if no sink is
    installed) is swallowed.
    """
    sink = get_sink()
    if sink is None:
        return
    record = {
        "type": event_type,
        **fields,
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if _run_id is not None:
        record["run_id"] = _run_id
    try:
        sink.emit(record)
    except Exception:
        # Best-effort telemetry: a failing sink must never break the build.
        pass
