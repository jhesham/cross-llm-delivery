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
