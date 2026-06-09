# T4.1 slice brief — Ledger schema (resumable progress)

Implement `src/cld/ledger.py` so that `tests/test_ledger.py` passes. Only create/modify
`src/cld/ledger.py`. Do NOT modify the test file.

## Purpose

The ledger persists build progress so a fresh session resumes mid-build instead of re-deriving
everything. It is the machine-managed replacement for the hand-rolled STATUS.md ledger. It must
survive a crash mid-write (atomic write) and a corrupted/partial file on disk (safe load).

## Contract (all importable from `cld.ledger`)

### Status constants
Provide these string status values (module-level constants AND accepted as plain strings):
`PENDING = "pending"`, `IN_PROGRESS = "in_progress"`, `DONE = "done"`, `FAILED = "failed"`.

### `LedgerEntry` (dataclass)
Per-slice record. Fields:
- `slice_id: str`
- `status: str` — one of the four status strings; defaults to `"pending"`
- `commit: str | None` — git hash when done; default `None`
- `attempts: int` — dispatch attempts so far; default `0`

### `Ledger` class
Holds entries keyed by slice_id and reads/writes a JSON file.

- `Ledger(path: str)` — construct bound to a file path (file need not exist yet).
- `Ledger.load(path) -> Ledger` (classmethod) — read the JSON file and return a populated
  Ledger. **Corruption-safe:** if the file is missing, empty, or not valid JSON, return a fresh
  empty Ledger bound to that path (do NOT raise).
- `.get(slice_id) -> LedgerEntry | None`
- `.set(slice_id, *, status=None, commit=None, attempts=None)` — create or update the entry,
  changing only the provided fields (None means "leave as is"); creates a PENDING entry first if
  the id is new.
- `.mark_attempt(slice_id)` — increment that entry's `attempts` by 1 (create as PENDING if new).
- `.pending_ids() -> list[str]` — ids whose status is NOT `done` (i.e. pending/in_progress/failed),
  in insertion order.
- `.is_done(slice_id) -> bool`
- `.save()` — **atomic write**: write JSON to a temp file in the SAME directory, then
  `os.replace()` it onto the target path (so a crash mid-write never corrupts the existing file).
- `.entries -> dict[str, LedgerEntry]` accessor (or property) for inspection.

### JSON shape
A dict mapping slice_id → {status, commit, attempts}. `load(save())` must round-trip exactly
(same ids, statuses, commits, attempts).

## Design rules (enforced by Claude as judge)
- stdlib only (`json`, `os`, `dataclasses`, `tempfile` or manual temp+`os.replace`, `typing`).
- Atomic write MUST use temp-file-in-same-dir + `os.replace` (rename is atomic on the same
  filesystem). Do not write in place.
- Corruption-safe load MUST NOT raise on missing/empty/garbage files — return a fresh Ledger.
- Mutable defaults via `field(default_factory=...)` where applicable.

## Done
`python -m pytest tests/test_ledger.py` → all tests pass. Full suite stays green.
