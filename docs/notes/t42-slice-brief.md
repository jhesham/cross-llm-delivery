# T4.2 slice brief — Resumable orchestrator layer (run_plan)

Add a NEW function `run_plan` (and a small result type) to `src/cld/orchestrator.py`.
Do NOT modify the existing `deliver_slice` or `DeliverResult` — `run_plan` CALLS `deliver_slice`.
Do NOT modify the test file. Only edit `src/cld/orchestrator.py`.

## Purpose

`run_plan` is the resumable layer: given a list of slices and a Ledger, it runs each slice that
isn't already done, recording progress to the ledger and saving after EACH slice — so a fresh
process started against the same ledger skips completed slices and resumes from where it stopped.
This is the machine-managed replacement for the hand-rolled STATUS.md.

## Existing pieces to use (do not modify)
- `deliver_slice(task, *, executor, judge_fn, max_retries=2) -> DeliverResult`
  (already in this module; returns `.accepted`, `.attempts`, `.final`, `.history`).
- `from cld.ledger import Ledger, DONE, FAILED, IN_PROGRESS` — Ledger has:
  `.is_done(id)`, `.set(id, *, status=, commit=, attempts=)`, `.save()`, `.get(id)`.
- `SliceTask` from `cld.executors.base` (has `.id`, `.files`, ...).

## Contract (add to cld.orchestrator)

### `PlanResult` (dataclass)
- `completed: list[str]` — ids accepted this run (default_factory list)
- `failed: list[str]` — ids that failed this run (default_factory list)
- `skipped: list[str]` — ids skipped because already done in the ledger (default_factory list)

### `run_plan(slices, ledger, *, executor, judge_fn, max_retries=2) -> PlanResult`
`slices: list[SliceTask]`, `ledger: Ledger`.
For each task in `slices`, in order:
1. **If `ledger.is_done(task.id)`** → add to `skipped`, do NOT dispatch, continue.
2. Else mark `ledger.set(task.id, status=IN_PROGRESS)` and `ledger.save()`.
3. Call `deliver_slice(task, executor=executor, judge_fn=judge_fn, max_retries=max_retries)`.
4. On `result.accepted`:
   - `ledger.set(task.id, status=DONE, attempts=result.attempts)` (commit may stay None here —
     the real git commit is wired later); add id to `completed`.
5. On not accepted:
   - `ledger.set(task.id, status=FAILED, attempts=result.attempts)`; add id to `failed`.
6. **`ledger.save()` after each slice** (so a crash/stop leaves a correct ledger on disk).
Return the populated `PlanResult`.

## Design rules (judged by Claude)
- `deliver_slice` and `DeliverResult` MUST remain unchanged — `run_plan` wraps, not edits.
- The ledger is saved after EVERY processed slice (the resumability guarantee).
- All effects injected (executor, judge_fn) — no live LLM. stdlib + existing cld imports only.
- Mutable dataclass defaults via `field(default_factory=...)`.

## Done
`python -m pytest tests/test_orchestrator_resume.py` passes; full suite stays green.
