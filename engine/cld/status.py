"""cld.status — compact ASCII digest of a telemetry event stream (Slice STATUS).

``render_status`` is a PURE function: a list of telemetry records (the JSONL the
orchestrator emits) plus a deterministic ``now`` goes in, a one-screen digest
the lead agent reads off ``--status`` comes out. No I/O, no globals, no wall
clock — pass ``now`` for exact elapsed. Output is cp1252-safe (ASCII only) so it
never crashes a Windows console.

Reconstructed state, all derived from the event stream:

* run id / plan          — from ``run_start``
* layer position         — from ``layer_start`` (``layer`` is 0-indexed; shown as
                            ``index+1 / total``)
* done / pending / run   — ``slice_done`` counts done; slices in the layer that
                            never ``slice_start`` are pending; slices with a
                            ``dispatch_start`` but no ``slice_done`` are running
* in-flight model+elapsed— the running slice's last ``dispatch_start`` model and
                            ``now - dispatch_start.ts``
* cumulative tokens      — sum of ``dispatch_end.tokens.total`` across the run
* gate                   — from ``run_done.gate`` when the run has finished
"""

import datetime
from typing import Any, Iterable, Mapping


def _parse_ts(ts: str) -> "datetime.datetime | None":
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _elapsed_seconds(start_ts: str, now: "datetime.datetime | None") -> int:
    start = _parse_ts(start_ts)
    if start is None or now is None:
        return 0
    return max(0, int((now - start).total_seconds()))


def render_status(
    events: "Iterable[Mapping[str, Any]]",
    *,
    now: "datetime.datetime | None" = None,
) -> str:
    """Render a compact cp1252-safe status digest from a telemetry event stream.

    Degrades gracefully: an empty stream yields ``"no events"`` and a stream
    missing ``run_start``/``layer_start`` still renders what it can. Never
    raises on malformed records — a bad timestamp or missing field is treated
    as absent so the digest stays readable mid-build.
    """
    events = list(events)
    if not events:
        return "no events"
    # Default to wall-clock now so the CLI (`--status`, which passes no `now`) shows real
    # elapsed for in-flight slices — without this, _elapsed_seconds sees now=None and returns 0.
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)

    run_id: "str | None" = None
    plan: "str | None" = None
    layer_index: "int | None" = None
    layer_total: "int | None" = None
    layer_slice_ids: list[str] = []
    started: set[str] = set()
    done: dict[str, str] = {}
    dispatch: dict[str, tuple[str, str]] = {}  # slice_id -> (model, ts)
    # Per-model rollup, cumulative across the whole run (not reset per layer):
    # model -> {"slice_ids": [...], "tokens": int, "source": str}
    by_model: dict[str, dict[str, Any]] = {}
    total_tokens = 0
    gate: "str | None" = None

    for ev in events:
        etype = ev.get("type")
        if etype == "run_start":
            run_id = ev.get("run_id", run_id)
            plan = ev.get("plan", plan)
        elif etype == "layer_start":
            layer_index = ev.get("layer", layer_index)
            layer_total = ev.get("total", layer_total)
            layer_slice_ids = list(ev.get("slice_ids") or [])
            # Per-layer rollup: reseed counters for the new layer so pending /
            # running / done reflect the CURRENT layer, not the whole run.
            started, done, dispatch = set(), {}, {}
        elif etype == "slice_start":
            sid = ev.get("slice_id")
            if sid is not None:
                started.add(sid)
        elif etype == "dispatch_start":
            sid = ev.get("slice_id")
            if sid is not None:
                dispatch[sid] = (ev.get("model", "") or "", ev.get("ts", "") or "")
            model = ev.get("model", "") or ""
            if model:
                entry = by_model.setdefault(
                    model, {"slice_ids": [], "tokens": 0, "source": ""}
                )
                if sid is not None and sid not in entry["slice_ids"]:
                    entry["slice_ids"].append(sid)
                src = ev.get("source", "") or ""
                if src:
                    entry["source"] = src
        elif etype == "dispatch_end":
            tok = ev.get("tokens") or {}
            try:
                t = int(tok.get("total", 0) or 0)
            except (TypeError, ValueError):
                t = 0
            total_tokens += t
            model = ev.get("model", "") or ""
            if model:
                bm = by_model.setdefault(
                    model, {"slice_ids": [], "tokens": 0, "source": "", "cost": 0.0}
                )
                bm["tokens"] += t
                c = ev.get("cost")
                if isinstance(c, (int, float)) and not isinstance(c, bool):
                    bm["cost"] = bm.get("cost", 0.0) + c
        elif etype == "slice_done":
            sid = ev.get("slice_id")
            if sid is not None:
                done[sid] = ev.get("status", "") or ""
        elif etype == "run_done":
            gate = ev.get("gate", gate)

        if run_id is None and ev.get("run_id") is not None:
            run_id = ev.get("run_id")

    # Running: dispatched, not yet done. Prefer the current layer's slices;
    # fall back to any dispatched-not-done slice when no layer context exists.
    running = [
        (sid, dispatch[sid])
        for sid in layer_slice_ids
        if sid in dispatch and sid not in done
    ]
    if not running:
        running = [(sid, dispatch[sid]) for sid in dispatch if sid not in done]

    # Pending: in the layer but never started (and not done).
    pending = [sid for sid in layer_slice_ids if sid not in started and sid not in done]

    total_cost = sum(float(i.get("cost", 0) or 0) for i in by_model.values())

    lines: list[str] = []
    head = f"cld status - run {run_id or '?'}"
    if plan:
        head += f"  ({plan})"
    lines.append(head)

    if layer_index is not None or layer_total is not None:
        pos = (layer_index + 1) if layer_index is not None else 0
        tot = layer_total if layer_total is not None else 0
        lines.append(
            f"layer {pos}/{tot}  done: {len(done)}  pending: {len(pending)}  "
            f"running: {len(running)}  tokens: {total_tokens}  cost: ${total_cost:.2f}"
        )
    else:
        lines.append(
            f"done: {len(done)}  pending: {len(pending)}  "
            f"running: {len(running)}  tokens: {total_tokens}  cost: ${total_cost:.2f}"
        )

    for sid, (model, ts) in running:
        lines.append(
            f"running: {sid}  model: {model}  elapsed: {_elapsed_seconds(ts, now)}s"
        )

    lines.append("by model:")
    if by_model:
        for model, info in by_model.items():
            slices = ",".join(info["slice_ids"]) if info["slice_ids"] else "--"
            lines.append(
                f"  {model}  slices: {slices}  tokens: {info['tokens']}  "
                f"cost: ${float(info.get('cost', 0) or 0):.2f}  source: {info['source'] or '--'}"
            )
    else:
        lines.append("  --")

    lines.append(f"gate: {gate}" if gate is not None else "gate: --")
    return "\n".join(lines)
