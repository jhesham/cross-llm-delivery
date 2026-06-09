# T5.3 slice brief — Integration gate

Implement `src/cld/integration_gate.py` so `tests/test_integration_gate.py` passes.
Only create `src/cld/integration_gate.py`. Do NOT modify the test file or other modules.

## Purpose

Slice-green ≠ system-green: after a batch of slices merges, contracts can drift or merges can
conflict. The integration gate runs the FULL test suite on the merged tree and decides whether
the batch is accepted or must be sent back for rework.

## Existing pieces to REUSE (import, do not reimplement)
- `from cld.judge import parse_pytest_output` — `(output) -> (passed:int, failed:int, failing:list[str])`.

## Contract (importable from `cld.integration_gate`)

### `GateResult` (dataclass)
- `passed: bool` — True iff the full suite ran with failures == 0 AND passed > 0
- `batch: list[str]` — the slice ids in the batch under test (default_factory list)
- `tests_passed: int` (default 0)
- `tests_failed: int` (default 0)
- `failing_tests: list[str]` — node ids that failed (default_factory list)
- `rework_batch: list[str]` — the batch ids that need rework; equals `batch` on failure,
  empty on success (default_factory list)
- `raw_output: str` (default "")

### `integration_gate(batch, *, run_full_suite) -> GateResult`
- `batch: list[str]` — the slice ids that were merged together.
- `run_full_suite` is an INJECTED callable `run_full_suite() -> str` returning the raw pytest
  output of running the WHOLE suite on the merged tree (no hardcoded subprocess — DI).
Steps:
1. Call `run_full_suite()` to get raw output.
2. `parse_pytest_output(...)` → (passed, failed, failing).
3. `passed` (bool) = (failed == 0 AND passed > 0).
4. On success: `rework_batch = []`. On failure: `rework_batch = list(batch)`.
5. Return a fully-populated `GateResult` (raw_output set, batch echoed).

## Design rules (judged by Claude)
- REUSE `parse_pytest_output` from cld.judge — do not write a second pytest parser.
- `run_full_suite` injected — no hardcoded subprocess. stdlib + cld imports only.
- Mutable dataclass defaults via `field(default_factory=...)`.
- Zero tests collected (passed == 0) counts as a FAIL (don't accept an empty run).

## Done
`python -m pytest tests/test_integration_gate.py` passes; full suite stays green.
