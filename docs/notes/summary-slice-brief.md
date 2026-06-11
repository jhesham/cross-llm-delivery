# Slice brief — src/cld/summary.py (summarize_layer + classify_gate)

Implement `src/cld/summary.py` so `tests/test_summary.py` passes. Do NOT modify the test file.
stdlib only. Both functions are PURE (no I/O). Import `PlanResult`, `SliceDetail` from
`cld.orchestrator` only if needed for type hints (not required at runtime).

## 1. summarize_layer(result, *, layer_index, total_layers, next_layer) -> str

Returns a COMPACT multi-line string summarizing one DAG layer's outcome. Reads
`result.details` (a dict of slice_id -> SliceDetail with fields: slice_id, status,
files_changed, attempts, diff_lines, failing_tests).

Format (sort slice lines by id):
- Header line: `LAYER {layer_index+1} of {total_layers}  —  done`
- One line per slice in `result.details` (sorted by slice_id):
  - if status == "completed": `  {id}  ✓ pass   {n} file(s) (+{diff_lines})   attempt {attempts}`
    where {n} = len(files_changed). Use "file" if n==1 else "files".
  - if status == "failed": `  {id}  ✗ FAIL   {first_failing_test}   attempt {attempts}`
    where {first_failing_test} = failing_tests[0] if failing_tests else "(no test id)".
  - other statuses (skipped/deferred): `  {id}  - {status}`
- A GATE line: `GATE: {n_pass} passed, {n_fail} failed.` (n_pass = count completed,
  n_fail = count failed in details). If any failed, append ` Inspect {comma-joined failed ids}?`
- A NEXT line:
  - if next_layer is non-empty: `NEXT: layer {layer_index+2} → [{comma-joined next_layer ids}]`
  - else: `NEXT: build complete — no further layers.`

MUST NOT include any raw diff text (`diff --git`), `-o json` blobs (`stats`), or pytest logs.
Keep it compact — the whole output for a 3-slice layer must be <= 12 lines.

## 2. classify_gate(result, *, more_layers) -> int

Pure. Maps a PlanResult to an exit code:
- if result.failed OR result.deferred (either non-empty) -> return 2
- elif more_layers (truthy) -> return 0
- else -> return 3

## Done
`python -m pytest tests/test_summary.py -q` passes; full suite stays green.
