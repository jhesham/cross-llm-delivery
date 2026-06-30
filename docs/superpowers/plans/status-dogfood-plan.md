# --status renderer — dogfood plan (cld/status.py)

Pure renderer slice for the telemetry feature's `--status` digest. Spec:
`docs/superpowers/specs/2026-06-25-agent-telemetry-and-monitoring-design.md` (Phase 1, item 3).
Package is `cld` under `engine/`; Python 3.11+, stdlib only.

## SLICE: STATUS
executor: opencode:opencode/glm-5.2
brief: Create `engine/cld/status.py` with a PURE function
  `render_status(events: list[dict], now=None) -> str` that reconstructs build state from a
  telemetry event stream and returns a compact ASCII digest (one or two short lines) for the lead
  agent. Each event is a dict with a string `"type"` and an ISO-8601 `"ts"`; stdlib only.
  Reconstruction rules:
  - run_id: take it from any event that has a `"run_id"`.
  - current layer: the LAST `"layer_start"` event. Show its position as `"{layer+1}/{total}"` using
    that event's `"layer"` and `"total"` fields. Its `"slice_ids"` list is the current layer's slices.
  - Classify each current-layer slice from the stream: a slice with a `"slice_done"` event is DONE
    (its `"status"` is "completed" or "failed"); a slice with a `"slice_start"` but no `"slice_done"`
    is RUNNING; a slice id in `"slice_ids"` with no `"slice_start"` is PENDING.
  - Show the count of DONE slices, the count of PENDING slices (use the word "pending"), and for each
    RUNNING slice show its id, the `model` and `rung` from its most recent `"dispatch_start"`, and
    elapsed WHOLE seconds as `"{n}s"` computed as `(now - that dispatch_start's ts)`. When `now` is
    None use `datetime.datetime.now(datetime.timezone.utc)`; parse ts with `datetime.fromisoformat`.
  - tokens: the sum of `tokens["total"]` over all `"dispatch_end"` events (print the integer).
  - gate: the `"gate"` field of a `"run_done"` event if present, else the literal `"pending"`; print
    it as `"gate: <value>"`.
  - Degrade gracefully: `render_status([])` returns a short string containing "no events".
  Suggested format (NOT rigid, but must satisfy the asserts):
    `run a1b2 | layer 1/3 | 4 slices: 2 done | T3 running opencode:opencode/glm-5.2@workhorse 47s | 1 pending | tokens 3000 | gate: pending`
  CRITICAL: the output MUST be cp1252-safe — use ONLY plain ASCII punctuation (`|`, `/`, `:`); NO
  check marks, box-drawing, bullets, or other non-cp1252 characters (the console crashes otherwise).
  Match the acceptance tests exactly. Do not edit the test file.
files: engine/cld/status.py
acceptance_test_path: tests/test_status.py
deps:
