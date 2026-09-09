# T01 — Baseline and regression evidence

Date: 2026-09-10. Starting commit: `7cdc31ee5459afd61a2c9a2e7c42a90066964b48`.
Environment: Windows, Python 3.13.13, Git 2.54.0.windows.1. Working tree was clean before T01.

Scope: tests and progress documentation only. No production engine/provider changes, live LLM calls, installs, global Git configuration changes, or publication.

**Baseline**

`python -m pytest -o addopts="-m 'not eval'" -q --tb=short`

Result before test edits: **419 passed, 1 deselected, 2 warnings** (52.60s). Warnings are the existing optional behavioral dependency's deprecation. An earlier sandboxed invocation encountered pytest temporary-directory access errors; those are environmental setup errors, not engine regressions. The baseline was rerun with the necessary filesystem access.

**Harness changes**

- FileCreatingExecutor and the concurrent/step-through test executors now call the production `capture_diff` helper instead of maintaining separate diff implementations.
- Harness smoke assertions check real file content, Git status, reported filenames, and patch content. Existing collection tests independently inspect committed Git trees.
- The new regression module commits an assertion-failing acceptance test and implementation stub, verifies that baseline with real pytest, and uses real Git/worktrees. Provider processes are simulated file writers only.
- Git command failures are injectable at the runner boundary. Judge and ledger-save faults are injected separately. Hook rejection uses an actual test-local pre-commit hook, including Git for Windows' shell.
- Only explicit `ContractFailure` assertions qualify for temporary xfail. Fixture assertions, setup errors, and unexpected exceptions cannot silently become expected failures. All markers are strict: a fixed contract triggers XPASS failure until its marker is removed.

**New tests and closure ownership**

All names below are in `tests/integration/test_review_regressions.py`.

| Test | Baseline behavior / expected contract | Owner |
|---|---|---|
| `test_executor_commit_cannot_hide_forbidden_file` | Accepts a candidate whose executor committed a forbidden file; must reject | R01 / T02 |
| `test_failed_dispatch_after_writes_is_rejected` | Accepts `ok=False` after implementation/forbidden writes; must reject | R02 / T02 |
| `test_rejecting_commit_hook_preserves_candidate[single]` | Ignores actual commit-hook rejection and loses code; require nonacceptance plus recoverable candidate | R03 / T03 |
| `test_rejecting_commit_hook_preserves_candidate[ladder]` | Same defect through rung-planner collection path | R03 / T03 |
| `test_escalation_dispatches_second_rung` | Second rung never dispatches because slice branch exists | R04 / T04 |
| `test_dependent_dispatch_has_dependency_code` | B reads the old implementation instead of accepted A's code | R05 / T06 |
| `test_failed_dependency_blocks_dispatch` | B dispatches even though A's real acceptance test failed | R05 / T06 |
| `test_judge_exception_preserves_candidate` | Judge exception discards uncommitted implementation instead of preserving it | R03 / T03 |
| `test_diff_capture_error_cannot_accept_candidate` | Nonzero diff RC with empty captured output is accepted as an empty valid diff | R01 / T02 |
| `test_ledger_save_failure_leaves_reachable_implementation` | Passing control: failed final ledger write propagates, persisted state is not DONE, implementation remains on a reachable branch | T03/T05 recovery coverage |
| `test_cleanup_failure_retains_worktree_and_commit` | Passing control: failed removal retains the test-owned worktree and reachable implementation commit | T03/T04 recovery coverage |

The two passing fault controls verify preservation only. They do not claim that ledger reconciliation or cleanup-error reporting is complete; those remain future work.

**Verification commands and results**

```text
python -m pytest tests/integration -o addopts="" -q -rx --tb=short
10 passed, 9 xfailed (21.81s); no unexpected passes

python -m pytest tests/integration/test_review_regressions.py -o addopts="" -q --runxfail --tb=short
9 failed, 2 passed (17.79s); expected exit 1

python -m pytest -o addopts="-m 'not eval'" -q --tb=short
421 passed, 1 deselected, 9 xfailed, 2 warnings (66.86s); exit 0
```

With `--runxfail`, all nine failures reached their named contract assertions. The baseline defects are intentionally not repaired by T01. Remove each marker when its owning task fixes the contract; do not ship these temporary expected failures as permanent test exclusions.

Local full output is kept under ignored `.cld/t01-verification/` (`unmasked.log`, `full-suite.log`). These logs are supplementary; tests and this summary are portable and do not depend on archived temporary repositories or machine-local review scripts.

**Observed limitations**

- The first integration invocation had an intermittent failure in the preexisting concurrent-worktree test: A recorded FAILED with zero attempts, B completed. The original assertion omitted details; its assertion now includes `result.details` for future diagnosis. The next integration run and final full suite passed this test. No concurrency-engine fix is claimed; investigate recurrence under T04.
- The first diff-failure probe returned diagnostic text that the engine treated as a disallowed filename. It therefore did not test the intended silent-output error condition. The fixture now injects nonzero RC with empty output, which reproduces that condition. This is a test correction, not a production fix.
- Platform evidence here is Windows only. Fixtures are path-portable and use test-local state, but POSIX execution is left to CI.

**Token use:** lead-agent usage counters were not exposed; no measured total is claimed. Executor/model dispatch usage: zero. T02 must wait for the user's explicit token-availability confirmation.
