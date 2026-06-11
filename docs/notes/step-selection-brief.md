# Slice brief — next_pending_layer in src/cld/orchestrator.py

Add a function `next_pending_layer` to `src/cld/orchestrator.py` so
`tests/test_step_selection.py` passes. Do NOT modify the test file or any other function.

## next_pending_layer(slices, ledger) -> tuple[int, list[str], int] | None

Pure (reads the ledger, writes nothing). stdlib + `cld.dag.parallel_batches`.

- Build `deps = {s.id: list(s.deps) for s in slices}` and `layers = parallel_batches(deps)`.
- For each `(idx, layer)` in `enumerate(layers)`: compute
  `pending = [sid for sid in sorted(layer) if not ledger.is_done(sid)]`.
  If `pending` is non-empty, return `(idx, pending, len(layers))`.
- If NO layer has pending slices, return `None`.

`slices` is a list of SliceTask (has `.id` and `.deps`). `ledger` has `.is_done(slice_id) -> bool`.
Import `parallel_batches` from `cld.dag` (it is already imported at the top of orchestrator.py).

## Done
`python -m pytest tests/test_step_selection.py -q` passes; full suite stays green.
