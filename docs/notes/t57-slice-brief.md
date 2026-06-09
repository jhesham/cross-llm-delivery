# T5.7 slice brief — GeminiExecutor consumes retry feedback

Modify `src/cld/executors/gemini.py` so the NEW tests in `tests/executors/test_gemini.py`
pass. Do NOT modify the test file. Do NOT break existing GeminiExecutor tests.

## Why

`deliver_slice` already builds judge feedback (failing tests + disallowed edits) on a failed
attempt and tries `executor.run(task, workdir, feedback=...)`. But `GeminiExecutor.run`
currently has no `feedback` param, so the feedback is dropped and the retry re-dispatches the
SAME prompt, blind. This change makes the executor use the feedback to self-correct.

## Changes to `src/cld/executors/gemini.py`

### 1. `run` accepts an optional `feedback`
Change the signature to:
```python
def run(self, task: SliceTask, workdir, feedback: str | None = None) -> ExecutorResult:
```
`feedback` defaults to None (backward compatible — existing callers/tests pass no feedback).
Pass it through to prompt construction.

### 2. `_build_prompt` accepts and uses `feedback`
Change to `_build_prompt(self, task, feedback: str | None = None) -> str`. When `feedback`
is a non-empty string, APPEND a clearly-delimited section to the prompt, e.g.:
```
Your previous attempt did not pass. <feedback>
Address this specifically before trying again.
```
When `feedback` is None/empty, the prompt is unchanged from the current behavior.

## Design rules (judged by Claude)
- Backward compatible: `run(task, workdir)` with no feedback must behave exactly as before
  (existing T2.2 tests must still pass).
- The feedback text must end up inside the `-p` prompt argument that is dispatched to the CLI.
- Keep everything else (argv form, token parse, git diff capture) unchanged.
- stdlib + existing imports only.

## Done
`python -m pytest tests/executors/test_gemini.py` passes (old + new cases); full suite green.
