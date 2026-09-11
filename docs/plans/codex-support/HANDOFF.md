# Current handoff

Updated: 2026-09-11. Initiative: Codex support and review remediation.

**State:** T01 through T05 and M1 complete; paused before T06 pending explicit
confirmation of token availability. Branch `refactor/codex-support`, remote `public` on GitHub.
Starting commit `5d29be0`; resolve the T05 closing commit with
`git log -1 --format=%h --grep='^fix: T05 '`. Verify commit/push before final pause.

**Checkpoint:** Stop after verification, progress updates, commit and authorized
push. Await explicit token availability before T06. T06 has not started. This is
a refactoring checkpoint, not a release or merge.

**Next after confirmation:** [T06: dependency/integration lifecycle](02-STATE-ORCHESTRATION.md#t06--dependency-and-integration-lifecycle).
Estimate 10–16k. Read that contract, `build_state.py`, `ledger.py`, `orchestrator.py`,
`integration_gate.py`, and CLI `_execute`. Add build-owned integration state/ref,
verified dependency bases, conflict/failure preservation, and idempotent integration.
Both remaining strict xfails are T06 dependency regressions. T07 still owns the
complete exit/gate protocol and verification of `--mark-repaired`.

**T05 evidence:** [T05-EVIDENCE.md](T05-EVIDENCE.md). Latest targeted checks:
75 passed; post-registry-fix concurrency: 5 passed. Full run: 531 passed, one outdated
preflight fixture corrected, 2 T06 xfails, 1 deselected. CLI follow-up: 41 passed;
532 distinct offline tests verified. Production code unchanged after the full run.
Logs: `.cld/t05-verification/full-suite.log` and `cli-followup.log`. An earlier compatibility selection found Git
reading another worker's incomplete worktree registry entry; add/remove now take a
short repository OS lock while executor work stays parallel.

**Schema/migration:** [T05-MIGRATION.md](T05-MIGRATION.md) is the operator/API guide.
Schema 2 has `build` identity and `entries`; canonical repo/Git/ledger/plan identity,
stable run ID, fingerprints, initial base, integration placeholders, timestamps and
outcome histories. Default ledger is under `--repo`; explicit relative paths retain
cwd semantics. `--migrate-ledger`, `--reconcile-plan` and `--new-build` back up state
and do not dispatch. Reachability alone never validates legacy acceptance/integration.
Ambiguous old DONE entries need repair/reconciliation. Never use a pre-T05 CLI on
schema-2 state; backup rollback is safe only before further changes/dispatch.

**Ownership/evidence:** The ledger OS lock covers the entire write operation;
status readers remain unlocked, and stale snapshots cannot overwrite newer bytes.
Process death releases the lock; do not delete lock files. New evidence and append-only
events live under `.cld/runs/<run-id>`, with `.cld/current-run.json`. Old artifacts,
branches and refs remain. Direct callers executing a subset must pass the complete
`plan_slices`; raw loads never migrate. T10 still owns aggregate token accounting
and bounded status indexing.

```text
python -m pytest tests/integration/test_build_state.py -o addopts="" -q --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

Committed plugin copies remain unchanged for T12/T17; the full suite checks generated
source bundles. Windows tested; no new POSIX execution claimed.

**Usage:** No sub-agents or live provider calls in T05; executor usage zero, lead
counters unavailable. Any Codex sub-agents must use `gpt-5.6-luna` at `max` with bounded
briefs. Kimi K3 via OpenCode remains the later dogfooding route, gated through T09;
resolve the exact model ID before live dispatch without substitution.
