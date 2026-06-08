# T3.3 slice brief — Judge module

Implement `src/cld/judge.py` so that `tests/test_judge.py` passes.
Do NOT modify the test file. Do NOT touch anything outside `src/cld/judge.py`
(you may also create `src/cld/__init__.py` content only if needed — it already exists, leave it).

## Purpose

The Judge is the heart of the cross-llm-delivery loop: after an executor produces a diff in a
worktree, the Judge decides — objectively — whether the slice is acceptable. It (1) runs the
acceptance tests, (2) parses the result into structured data, and (3) enforces the structural
diff rule that the executor only touched files it was allowed to.

## Contract to implement (all importable from `cld.judge`)

### 1. `JudgeResult` (dataclass)
The verdict for one slice. Fields:
- `passed: bool` — True iff tests all passed AND no disallowed files were edited
- `tests_passed: int` — count of passing tests
- `tests_failed: int` — count of failing tests
- `failing_tests: list[str]` — node ids of failing tests (e.g. "tests/test_x.py::test_foo"); default empty
- `disallowed_edits: list[str]` — files changed that were NOT in the allowed set; default empty
- `raw_output: str` — the raw test runner output, for debugging; default ""

`failing_tests` and `disallowed_edits` MUST default via `field(default_factory=list)`.

### 2. `parse_pytest_output(output: str) -> tuple[int, int, list[str]]`
Pure function. Given raw pytest stdout, return `(passed_count, failed_count, failing_node_ids)`.
- Parse the summary line (e.g. `"5 passed, 2 failed in 0.3s"` or `"3 passed in 0.1s"`).
- A line may have passed only, failed only, or both; missing count = 0.
- Extract failing test node ids from `FAILED tests/...::test_name` lines (pytest prints these with
  `-v` or in the short summary). Collect every node id that appears after a `FAILED ` token.
- Must be robust to: no failures (empty failing list), the word "passed"/"failed" absent, and extra
  whitespace. Do not raise on unparseable input — return `(0, 0, [])`.

### 3. `check_diff_rule(files_changed: list[str], allowed: list[str]) -> list[str]`
Pure function. Return the sorted list of entries in `files_changed` that are NOT in `allowed`.
Empty list means the executor stayed within bounds. Both inputs are lists of path strings;
compare as exact strings (already normalized by the caller).

### 4. `judge(files_changed, allowed, *, run_tests) -> JudgeResult`
The orchestration. `run_tests` is an INJECTED callable (dependency injection — no hardcoded
subprocess) that returns the raw pytest output string when called with no arguments:
`run_tests() -> str`. Steps:
1. Call `run_tests()` to get raw output.
2. `parse_pytest_output(...)` → counts + failing node ids.
3. `check_diff_rule(files_changed, allowed)` → disallowed edits.
4. `passed` = (tests_failed == 0 AND tests_passed > 0 AND disallowed_edits == []).
   (Zero passed tests is NOT a pass — a run that collected nothing is a failure.)
5. Return a fully-populated `JudgeResult` with `raw_output` set to the runner output.

## Design rules (enforced by the judge-of-the-judge — Claude)
- `run_tests` MUST be injected (no `subprocess`/`os.system` hardcoded in `judge()`); this keeps
  tests deterministic and honors the project's injectable-boundary rule.
- stdlib only (`dataclasses`, `re`, `typing`). No third-party imports.
- Pure functions stay pure (no I/O in `parse_pytest_output` / `check_diff_rule`).
- Mutable dataclass defaults via `field(default_factory=...)`.

## Done
`python -m pytest tests/test_judge.py` → all tests pass.
