# Current handoff

Updated: 2026-09-15. Initiative: Codex support and review remediation.

**State:** T01 through T06 and M1 complete; paused before T07 pending explicit
confirmation of token availability. Branch `refactor/codex-support`, remote `public`
on GitHub. Starting commit `08e6eff`; resolve the T06 closing commit with
`git log -1 --format=%h --grep="^fix: T06 "`. Verify commit/push before final pause.

**Checkpoint:** Stop after verification, progress updates, commit and authorized
push. Await explicit token availability before T07. T07 has not started. This is
a refactoring checkpoint, not a release or merge.

**Next after confirmation:** [T07: validated plans and gate protocol](02-STATE-ORCHESTRATION.md#t07--validated-plans-and-gate-protocol).
Estimate 10–16k. Read that contract, plan/slice.py, dag.py, judge.py,
integration_gate.py, integration.py, summary.py and CLI. Finish structured test
results, validation before dispatch, verified `--mark-repaired`, code 4 for
integration repair and consistent gates/telemetry/status. Run M2's full offline suite.

**T06 evidence:** [T06-EVIDENCE.md](T06-EVIDENCE.md). Full run: **555 passed**,
1 live eval deselected, no xfails, 2 existing deepeval warnings, 634.58 seconds.
Final follow-up: **3 passed**, 19 deselected, 31.37 seconds; **556 distinct passing
tests** verified overall. Logs: `.cld/t06-verification/full-suite.log` and
`followup.log`. The full-run-startup follow-up is limited to an integration artifact
path boundary guard; reconciliation and the no-provider CLI were rechecked too.
Earlier focused run: 33 passes plus one test-variable typo fixed before full run.

**Integration contract:** [Operator/API guide](T06-INTEGRATION.md). DONE means
accepted; integrated requires immutable merge ref plus a passed frozen suite and
journal published with the ledger. `--step` reports 6 for acceptance awaiting
integration. `--integrate --integration-tests <selector>` runs without a provider;
selector persists. Whole-plan multi-layer dispatch requires that explicit option
and integrates between layers. Failed/deferred/repair/interrupted dependencies
block with reasons. Later worktrees use verified integration SHA; user HEAD may
advance without changing an existing build's base.

**Recovery:** Integration journals/logs live under
`.cld/runs/<run-id>/integration/<transaction-id>/`; refs under
`refs/cld/integration/<run-id>/<transaction-id>`. Worktrees, including successful
ones, are retained for inspection/manual cleanup. Interrupted incomplete attempts
remain and retry creates a fresh attempt. Passed-journal/failed-ledger retries
reuse and re-test the same commit; published integration is a no-op. Manual
resolutions require `--manual-integration <commit>` ancestry/scope/test verification.
Reconciliation preserves unaffected acceptance but never inherits integrated status.

**State compatibility:** Schema 2 remains. [T05 migration guide](T05-MIGRATION.md)
applies with T06's stable-base update. Explicit reconciliation/new-build adopts
current HEAD. Old artifacts/refs stay. Never use an older CLI to write this state.
The ledger writer lock spans dispatch/integration/publication; process exit releases
OS ownership, so do not delete lock files. Generated plugin copies remain for T12/T17.

```powershell
python -m pytest tests/integration/test_integration_lifecycle.py -o addopts="" -q --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

**Usage:** No sub-agents or live provider calls; executor usage zero, lead counters
unavailable. Any explicitly requested Codex sub-agents must use `gpt-5.6-luna` at
`max` with bounded briefs. Kimi K3 via OpenCode remains gated through T09; verify
its exact model ID before live dispatch without substitution. Windows tested;
no new POSIX execution claimed.
