# T1.4 slice brief — Executor interface (== T2.1, kept)

Implement `src/cld/executors/base.py` so that `tests/executors/test_base.py` passes.
Do NOT modify the test file. Do NOT touch anything outside `src/cld/executors/`.

## Contract to implement

Three public names, all importable from `cld.executors.base`:

### 1. `SliceTask` (dataclass)
A unit of work handed to an executor. Fields:
- `id: str` — slice identifier (e.g. "T2.1")
- `brief: str` — the natural-language task / spec text
- `files: list[str]` — files the executor is allowed to create/modify
- `acceptance_test_path: str` — path to the pytest file that defines done
- `deps: list[str]` — ids of slices this one depends on; defaults to empty list

Must be safe to construct with `deps` omitted (defaults to `[]`), and two SliceTasks
with the same field values must compare equal.

### 2. `ExecutorResult` (dataclass)
The outcome of one executor dispatch. Fields:
- `ok: bool` — did the dispatch complete without executor-level error
- `diff: str` — unified diff of what changed (may be empty)
- `files_changed: list[str]` — paths the executor actually changed
- `token_usage: dict[str, int]` — token stats (e.g. {"total": N, "input": N, "output": N})
- `raw_log: str` — raw executor stdout/log for debugging; defaults to ""

`token_usage` and `files_changed` must default to empty (dict / list) when omitted.

### 3. `Executor` (typing.Protocol, runtime_checkable)
Structural interface every executor adapter satisfies. One method:
- `run(self, task: SliceTask, workdir: Path) -> ExecutorResult`

Use `typing.Protocol` and decorate with `@runtime_checkable` so `isinstance(obj, Executor)`
works structurally. `Path` is `pathlib.Path`. No concrete CLI here — this is the interface
only; GeminiExecutor (T2.2) implements it later.

## Design rules (enforced by the judge)
- Pure interface + data module: no I/O, no subprocess, no network, no model calls.
- Use `dataclasses` and `typing` from the stdlib only — no third-party imports.
- Mutable defaults (`deps`, `files_changed`, `token_usage`) MUST use `field(default_factory=...)`,
  never a bare mutable default.

## Done
`python -m pytest tests/executors/test_base.py` → all tests pass.
