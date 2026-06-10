# B1.3 slice brief — Fix BUG1/Defect1: capture untracked new files

Modify `src/cld/executors/gemini.py` so the failing test
`tests/integration/test_capture_untracked.py` passes. Do NOT modify the test file.
Do NOT break any existing test in `tests/executors/test_gemini.py`.

## The bug

`GeminiExecutor.run` captures changed files via:
```python
_, diff = self._runner(["git", "diff", "HEAD"], cwd)
_, names = self._runner(["git", "diff", "HEAD", "--name-only"], cwd)
```
`git diff HEAD` does NOT include UNTRACKED files. When a slice CREATES a new file (the
common case), it's untracked, so `files_changed` comes back empty and `diff` is empty —
the executor reports "nothing changed" for a slice that created files. This is BUG1/Defect1.

## The fix

Before capturing the diff, stage the worktree so new files become visible to `git diff`.
Run a `git add` step through the SAME `self._runner`, in the same `cwd`, BEFORE the two
diff commands. Two acceptable approaches (pick one):
- `git add -A` then `git diff --cached` (diff of staged changes), OR
- `git add --intent-to-add -A` (a.k.a. `-N`) then keep `git diff HEAD` (intent-to-add makes
  untracked files appear in `git diff` as new files without fully staging content).

Either way, after the change:
- `files_changed` MUST include newly-created files (e.g. `src/created_by_slice.py`).
- `diff` MUST be non-empty for a created file.

## Constraints
- Only touch the diff-capture block in `run` (after a successful dispatch). Do not change the
  dispatch argv, token parsing, or the `rc != 0` early return.
- Use `self._runner` for the new git command (keep it injectable/testable).
- Keep it minimal — one added `git add ...` runner call + (if you choose `--cached`) adjust the
  two diff commands to match.

## Done
- `python -m pytest tests/integration/test_capture_untracked.py -q` → passes.
- `python -m pytest tests/executors/test_gemini.py -q` → still all pass (existing tests rely on
  a RecordingRunner; ensure your added git command is matched/handled — the existing
  `_runner_ok` helper returns (0, "") for unmatched commands, so an extra `git add` call is
  harmless there).
- Full suite stays green.
