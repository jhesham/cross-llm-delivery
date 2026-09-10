# T02 — Independent candidate verification

Date: 2026-09-10. Starting commit: `ddd4333`, branch `refactor/codex-support`.
The T01/planning checkpoint was already pushed before this sitting.
Closing commit: `a6b1b68`.

## Implemented contract

- `CandidateVerifier` records the original commit before dispatch and keeps it across
  retries. Its immutable `Candidate` contains base SHA, candidate tree, actual changed
  paths, binary-capable diff and protected-test/selector fingerprint.
- Capture checks Git exit codes and NUL terminators, includes committed, staged,
  unstaged, untracked and ignored source, and treats renames as both old/new paths.
  Binary contents, deletion and executable modes are included. Clearing Git index
  flags prevents assume-unchanged/skip-worktree from hiding edits.
- The engine rejects failed/malformed executor completions and forbidden changes
  independently of reported files or logs. The executor receives a copy of the task,
  so it cannot change the engine's selector or allowed-path contract.
- Preflight requires committed acceptance inputs and real baseline execution. Passing
  tests or assertion-only failures are valid; missing/empty tests, collection errors,
  runtime errors, ambiguous output and missing process RC block dispatch.
- Standard test inputs, `tests/` data, pytest configuration and `.gitattributes` are
  protected, even if listed as allowed edits. New test/config additions are rejected.
  Other fixture files can be listed in `protected_inputs`.
- Tests execute once per judge invocation in a temporary snapshot materialized from
  Git's frozen index tree. Filesystem fingerprints detect persistent test-time edits;
  the executor worktree is independently recaptured afterwards and before collection.
  The collection index is loaded from the verified tree instead of blindly staging
  post-judge files. T03 still owns commit results/hooks, durable acceptance and recovery.
- No-change success requires explicit `allow_already_satisfied: true`, a passing
  baseline and a passing candidate test. Both new plan fields round-trip through Markdown.
- Production Python calls require the Git/acceptance boundary. Report-only test doubles
  require `simulation=True`; it cannot be combined with Git arguments and is never used
  by the CLI. `run_plan` delegates real deliveries to the verified worktree path.
  Signature inspection preserves one-argument test runners and executors without
  feedback without catching/retrying errors raised inside those functions.

## Verification

Final full-suite result: **479 passed, 6 strict xfailed, 1 live evaluation deselected, 2 existing dependency deprecation warnings; exit 0 in 193.15s.**

The T01 diff-error regression was then tightened so its fault activates only after a
real executor write (not during baseline preflight). Its separate rerun passed: 1 passed
in 2.42s. No production code changed after the full-suite run began.

Commands, from the repository root:

```text
python -m pytest tests/integration tests/executors tests/test_deliver_feedback.py tests/test_deliver_real_judge.py tests/test_judge_scope.py tests/test_orchestrator_parallel.py -o addopts="" -q --tb=short
python -m pytest tests/integration/test_candidate_verification.py -o addopts="" -q --tb=short
python -m pytest tests/integration/test_candidate_verification.py -k "index_flags or index_mode or complete_git" tests/test_candidate_policy.py -o addopts="" -q --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

The initial targeted run passed 97 tests with 6 expected failures. The first 32 new
real-Git cases passed. A later flag-tampering regression found that combining both
`update-index` flag-clear options did not clear skip-worktree. Separate checked
invocations fixed it; the focused capture/mode/index-flag rerun passed all 4 selected
tests. An intermediate broad suite passed 461 tests before the final policy additions.
Only the final full-suite result above describes the final implementation.

R01/R02 T01 regressions now run normally: executor-committed forbidden edits, failed
dispatch after writes and nonzero diff capture. Additional real-Git cases cover empty
report spoofing, allowed writes after failed/malformed completion, committed test
tampering, test-time edits in either directory, missing/invalid/mixed-error baselines,
explicit no-op policy, fixture protection, task mutation and late collection changes.
Capture cases cover binary/staged/unstaged/ignored/rename/delete/mode changes, Unicode
and spaces. Symlink rejection was exercised on this Windows host. LF/CR/glob filenames
and native POSIX executable mode cases are conditional on POSIX and were not run here;
Windows index executable-bit changes were exercised.

Existing provider adapter tests use the checked NUL-delimited report format. Existing
generator tests build/smoke all three provider bundles and exercise isolated vendored
imports/driver startup. No live provider CLI was invoked.

## Compatibility and remaining work

- Verified on Windows with Python 3.13.13 and Git 2.54.0.windows.1. Python 3.11 support
  is retained in source, but was not separately executed. Symlinks, junctions and
  submodules are conservatively unsupported. This is Git isolation, not an OS sandbox;
  a hostile process with the same host permissions is outside this guarantee.
- Snapshots contain committed Git content and candidate edits, without a `.git`
  directory or the executor's ignored environment. Acceptance requiring Git metadata
  or generated ignored dependencies needs a future explicit trusted setup contract.
  Snapshot writes other than new bytecode/pytest cache artifacts cause rejection.
- Strict baseline classification requires recognizable pytest failure summaries;
  ambiguous or missing summaries fail closed. T07 owns the broader structured gate
  protocol; T08 owns timeouts/process lifecycle. Optional selector syntax is one literal
  path/node plus `-k`; extra flags/paths are not accepted. Markdown path lists remain
  comma/line based; unusual LF/CR filenames require the Python task contract.
- R03, R04 and R05 remain open: the six strict expected failures cover commit-hook
  preservation (single/ladder), judge-exception preservation, escalation collision,
  dependency visibility and failure blocking. Ledger/recovery work is not completed.
- The source engine and driver changed. Committed marketplace plugin copies retain
  their previous version; T12/T17 own distribution refresh and release verification.
  This checkpoint is pushed only to the refactoring branch, not released or merged.
- No paid/provider dispatches; Kimi K3 via OpenCode remains selected for later dogfooding.
  Lead token usage is unavailable; the 12–18k task allowance was an estimate, not a
  measured total. Local verification log: `.cld/t02-verification/full-suite.log`.

Next checkpoint: T03 only after the user confirms token availability.
