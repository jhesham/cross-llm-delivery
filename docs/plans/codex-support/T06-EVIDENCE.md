# T06 — dependency and integration lifecycle evidence

Date: 2026-09-15. Starting commit: `08e6eff` (T05).
Branch: `refactor/codex-support`. Closing subject starts `fix: T06`.

**Complete.** 556 distinct passing offline tests verified; no remaining xfails.
Resolve the closing commit with `git log -1 --format=%h --grep="^fix: T06 "`.

## Implemented contract

- `integration.py` owns explicit suite selection, build-owned worktrees, stable
  accepted-commit merge order, frozen baseline/candidate tests, immutable refs,
  durable journals and atomic publication of integrated state.
- Orchestration checks integrated dependency status and ancestry before dispatch;
  later worktrees use the verified integration SHA. Whole-plan delivery uses the
  same lifecycle when configured; multi-layer execution without a suite is blocked.
- CLI `--integrate`, `--integration-tests` and `--manual-integration` perform no
  provider dispatch. Accepted work reports integration-required instead of build
  complete. Warning-only dependency behavior is removed from the execution path.
- User HEAD may advance without retargeting the build. Reconciliation preserves
  unaffected acceptance but requires fresh integration proof in its new run.
- Conflicts, failed suites and interrupted attempts keep their worktrees/journals.
  Retry after passed tests but failed ledger publication reuses and re-tests the
  same commit. Repeating a published integration does not merge or test again.

## Regression coverage

`tests/integration/test_integration_lifecycle.py` uses actual Git and subprocess
pytest without provider calls. It covers accepted-versus-integrated state,
idempotence, six unintegrated dependency states, explicit whole-plan configuration,
user HEAD advancing, baseline failure versus layer regression, conflict retention
and manual resolution, missing accepted ancestry, publication failure, interruptions
at merge/candidate boundaries, forged pass prose with nonzero RC, changed selectors,
deleted integration refs, reconciliation, provider-free CLI integration, frozen-tree
mutation, and artifact directory links escaping the run.

Both original R05 strict xfails in `test_review_regressions.py` are now ordinary
passing assertions. A's implementation is visible to B after actual integration;
failed A prevents B dispatch. B explicitly permits an already-satisfied no-op in
that fixture, retaining the production no-change acceptance guard.
`test_step_through.py` now integrates between layers, and the telemetry regression
expects accepted-only work to return 6 without emitting successful run completion.

## Validation record

- Focused development selection: 33 passed and one test-variable typo; corrected
  before the full run. Production dependency and integration assertions passed.
- Full offline suite: **555 passed**, 1 live eval deselected, no xfails, 2 existing
  deepeval deprecation warnings, 634.58 seconds; `.cld/t06-verification/full-suite.log`.
- Follow-up: **3 passed**, 19 deselected, 31.37 seconds;
  `.cld/t06-verification/followup.log`. Covers the final artifact-boundary guard,
  reconciliation and provider-free CLI. The boundary guard was the only production
  change after full-run startup.
- `compileall` and `git -c core.safecrlf=false diff --check` passed during development.

## Limits and next task

See [operator guide](T06-INTEGRATION.md). T07 retains ownership of R06/R11's final
protocol, structured runner results, full plan validation, verified repair marking,
code 4 for integration repair and telemetry/status consistency. T06's production
integration already rejects nonzero RC even when output says tests passed; the
older standalone integration-gate adapter is intentionally left for T07.

Successful integration worktrees are retained along with failures. Cleanup is
manual after inspection; user checkout update/merge is a separate operation.
Generated plugins remain unchanged until T12/T17. Verification is on Windows;
no new POSIX run is claimed. No sub-agents, live provider calls or executor tokens
were used. Lead token counters are unavailable. Commit/push T06, then pause for
explicit token availability before T07.
