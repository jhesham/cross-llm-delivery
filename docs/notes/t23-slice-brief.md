# T2.3 slice brief — Executor registry + Composer stub

Implement so that `tests/executors/test_registry.py` passes. Only create/modify:
`src/cld/executors/__init__.py` (the registry) and `src/cld/executors/composer.py` (a stub).
Do NOT modify the test file, `base.py`, or `gemini.py` (they already exist — import from them).

## Purpose

Prove the executor layer is pluggable: a single `get_executor(name)` factory returns the right
adapter by name. Gemini is real (already built); Composer is a documented stub that raises
NotImplementedError when run — proving a second executor drops in without redesign.

## Contract

### 1. `src/cld/executors/composer.py`
Define `class ComposerExecutor` satisfying the Executor protocol shape (same `run(self, task,
workdir) -> ExecutorResult` signature as GeminiExecutor), BUT its `run` must raise
`NotImplementedError` with a message mentioning "Composer". Construction (`ComposerExecutor()`)
must succeed — only `run()` raises. Add a short docstring noting it's a deliberate stub
(cursor-agent / Composer is a future drop-in; see design doc).

### 2. `src/cld/executors/__init__.py` (the registry)
Implement `get_executor(name: str, **kwargs) -> Executor`:
- `name == "gemini"` → return `GeminiExecutor(**kwargs)` (import from `.gemini`)
- `name == "composer"` → return `ComposerExecutor(**kwargs)` (import from `.composer`)
- case-insensitive on `name` (e.g. "Gemini" works); strip surrounding whitespace.
- unknown name → raise `ValueError` whose message includes the bad name AND lists the known
  names ("gemini", "composer").
- Also expose a module-level `KNOWN_EXECUTORS: tuple[str, ...]` = the registered names.
- Re-export `get_executor` and `KNOWN_EXECUTORS` from this `__init__` (they are the public API).

`**kwargs` is passed through to the executor constructor (so callers can inject a `runner` or
`model` into GeminiExecutor, or nothing into Composer).

## Design rules (enforced by Claude as judge)
- stdlib + existing cld imports only. No third-party.
- Do not modify base.py / gemini.py / the test file.
- The registry must not instantiate executors at import time — only inside `get_executor`.
- Keep it minimal; this is a factory + a stub, not a framework.

## Done
`python -m pytest tests/executors/test_registry.py` → all tests pass.
(And the full suite must stay green — do not break existing tests.)
