# T05 evidence — build identity and ledger migration

Started from `5d29be0d67f4e84cd76c872c681e5400b432b343` on
`refactor/codex-support`, 2026-09-11. Resolve the closing commit with
`git log -1 --format=%h --grep='^fix: T05 '`.

## Delivered boundaries

- Schema-2 envelopes with canonical repo/Git/ledger/plan identity, stable run ID,
  initial/integrated fields, task fingerprints, timestamps and outcome history.
- Default ledger under `--repo`; explicit relative-ledger paths retain cwd semantics.
- Whole-operation writer ownership, unlocked readers, stale-write rejection and
  atomic replacement; process exit releases ownership without PID/age heuristics.
- Explicit backed-up migration, plan reconciliation and new-build commands. Invalid,
  unreadable and unsupported state blocks; reachable legacy commits alone cannot
  establish acceptance/integration. Verified collected journals remain recoverable.
- Run-scoped evidence, append-only events, distinct summary directories and a current
  pointer. Old traces, candidates and accepted/recovery refs remain available.
- Serialized Git worktree registry mutations while executor work stays parallel.

See [migration and rollback instructions](T05-MIGRATION.md) for the schema and
compatibility changes. Committed plugin copies still await T12/T17 regeneration.

## Verification

- Initial ledger/CLI/telemetry/status selection: 60 passed in 3.75 seconds.
- Expanded state tests: 18 passed in 31.66 seconds before the copied-ledger case.
- Initial recovery/worktree compatibility selection: 33 passed, 1 failed. The saved
  journal identified Git reading another concurrently-created worktree's incomplete
  `commondir`; registry mutations now take a short repository OS lock.
- Post-fix worktree/concurrency checks: 5 passed in 39.56 seconds.
- Latest state/ledger/CLI/telemetry/status/selection checks: 75 passed in 35.50 seconds.
- Full offline run: **531 passed, 1 outdated fixture failed, 2 strict xfailed,
  1 live evaluation deselected, 2 existing deepeval warnings**, in 542.29 seconds.
  Log: `.cld/t05-verification/full-suite.log`.
- The missing-provider preflight fixture used a non-Git directory. State/repository
  checks now precede provider preflight, so the fixture was given a valid test repo;
  production code stayed unchanged after the full run began.
- Preflight/CLI/telemetry/status follow-up: **41 passed** in 3.72 seconds, including
  the corrected fixture. Log: `.cld/t05-verification/cli-followup.log`.
- Together these verify **532 distinct passing offline tests**, with only the two
  intentional T06 xfails remaining. This is full-run plus targeted-follow-up
  evidence, not a claim that one invocation reported 532 passes.

```text
python -m pytest tests/integration/test_build_state.py -o addopts="" -q --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

Real-Git/process tests cover repo/cwd isolation, copied state, plan invalidation and
independent retention, corrupt/unreadable/unsupported state, backed-up/idempotent
migration, ambiguous versus verified old DONE records, atomic-replace interruption,
stale writers, unlocked readers, process death, cross-run acceptance isolation,
trace retention and CLI blocking before provider work.

R08 and A03 are addressed. A09 trace preservation is addressed; bounded status
indexing remains T10. Dependency integration remains T06 and both existing expected
failures belong there. This slice does not complete T07 repair/gate semantics or
T10 usage accounting. Windows was exercised; no new POSIX execution is claimed.

No sub-agents or live provider calls. Executor token usage: zero; lead usage counters
unavailable. T05's 12–18k allowance is a planning estimate, not measured usage.
Commit/push this refactoring checkpoint, then pause before T06 for the user's
explicit token-availability confirmation.
