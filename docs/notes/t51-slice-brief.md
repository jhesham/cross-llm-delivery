# T5.1 slice brief — DAG scheduler (pure functions)

Implement `src/cld/dag.py` so `tests/test_dag.py` passes. Only create `src/cld/dag.py`.
Do NOT modify the test file. stdlib only.

## Purpose

From a set of slices with `deps[]`, compute the order of execution as **layers** (batches): each
batch is a set of slices whose deps are all satisfied by earlier batches, so a batch's members can
run in PARALLEL. Detect dependency cycles.

## Contract (importable from `cld.dag`)

Input is a mapping `deps: dict[str, list[str]]` — slice_id → list of slice_ids it depends on.
(You may also accept a list of `SliceTask` in a helper, but the core works on the dict.)

### 1. `class CycleError(Exception)`
Raised when the dependency graph has a cycle. Its message should mention the cycle / the involved
ids if reasonably possible.

### 2. `topo_layers(deps: dict[str, list[str]]) -> list[list[str]]`
Return a list of layers (batches). Layer 0 = all ids with no deps; each subsequent layer = ids
whose deps are all in earlier layers. Within a layer, ids are sorted alphabetically (deterministic).
Raise `CycleError` if no progress can be made (a cycle exists). Empty input → `[]`.
- Every id mentioned (as a key OR inside any deps list) must appear in the output exactly once.
  An id that appears only as a dependency (never a key) is treated as a no-dep node in layer 0.

### 3. `parallel_batches(deps) -> list[list[str]]`
Alias/identical to `topo_layers` (the public name the orchestrator will call). May simply return
`topo_layers(deps)`.

### 4. `has_cycle(deps: dict[str, list[str]]) -> bool`
Return True iff the graph has a cycle (does not raise).

## Design rules (judged by Claude)
- Pure functions, no I/O, stdlib only.
- Deterministic output (sort within layers).
- Cycle detection must be correct (e.g. A→B→A, and self-loop A→A, both are cycles).

## Done
`python -m pytest tests/test_dag.py` passes; full suite stays green.
