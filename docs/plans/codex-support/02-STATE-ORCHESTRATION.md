# Phase 2 — State, dependencies, and gates

Outcome: a stopped build resumes accurately, and downstream work only sees verified integrated dependencies. Relevant architecture: A05–A07. Migration is part of implementation, not deferred documentation.

## T05 — Build identity and ledger migration

Dependencies: T04. Estimate: 12–18k; split migration from locking if needed. Files: `engine/cld/ledger.py`, `orchestrator.py`, `skill/scripts/run_delivery.py`, telemetry/status, new migration fixtures.

- [x] Resolve the default ledger under `--repo`, preserve explicit relative-ledger semantics from A05, and include resolved paths in diagnostics.
- [x] Add a versioned envelope with run/repository/plan identity, initial and integrated SHAs, slice fingerprints, attempt refs, status, and timestamps. Keep schema reading separate from mutation.
- [x] Implement atomic updates and one active writer per build. Define stale-lock recovery with owner metadata and explicit checks; status readers must not require the writer lock.
- [x] Provide backed-up legacy migration. Verify old DONE entries against reachable commits/branches; ambiguous entries remain repair/reconcile work, not silently integrated.
- [x] Distinguish new/missing state from corrupt/unreadable/unsupported schema. Do not reset or truncate traces on load failure. Detect mismatched plan/repo and provide a deliberate reconciliation path that invalidates downstream work.
- [x] Store artifacts by run and attempt, with a current-run pointer. Preserve historical traces and failed-attempt output; do not overwrite earlier rung diagnostics.
- [x] Test two repos from one cwd, one repo from two cwds, changed plans, duplicate processes, unreadable/corrupt JSON, migration twice, and interruption during atomic replacement.

**Gate:** R08 and A03/A09 pass; no unrelated build is skipped or overwritten. Existing state is either safely migrated with evidence or explicitly blocked. Handoff includes schema version and rollback limits.

Completed 2026-09-11. [T05 evidence](T05-EVIDENCE.md) and [migration/rollback guide](T05-MIGRATION.md). Schema 2, explicit migration/reconciliation, full-operation writer ownership and run-scoped history are implemented. Verification covers 532 distinct passing offline tests across the full run and targeted fixture follow-up; only the two T06 xfails remain. T06 requires the next token checkpoint.

## T06 — Dependency and integration lifecycle

Dependencies: T05. Estimate: 10–16k; split integrating candidates and unattended loop if needed. Files: `orchestrator.py`, `integration_gate.py`, `worktree.py`, CLI, integration tests. Suggested new module: `engine/cld/integration.py`.

- [ ] Require successful integrated dependency SHAs before dispatch; fail/defer/repair/interrupted dependencies block dependents with an explicit reason.
- [ ] Add the build-owned integration worktree/ref and proposed `--integrate` action. Merge recorded accepted commits in stable order without touching the user's checkout.
- [ ] Run an explicit configured integration suite against the candidate merge. Distinguish baseline failure from a layer regression; avoid calling unrelated paid/live tests by default.
- [ ] Advance integration SHA and mark slices integrated only after the real suite succeeds. Preserve conflict or failed-gate candidates and repair evidence; retry integration idempotently.
- [ ] Base subsequent worktrees on recorded integration SHA. Support manual integration only after ancestry and test verification; remove warning-only dependency behavior.
- [ ] Route whole-plan mode through the same lifecycle or return a clear blocked result for unsupported unattended multi-layer runs until implemented. No alternate dependency-blind loop may remain.
- [ ] Test A→B visibility, A-fails→B-blocked, independent A/C with integration conflict, integration-suite failure, repeated integrate, user HEAD advancing, and restart between merge/test/state-save.

**Gate:** R05 passes with real Git/tests. A dependent receives A's implementation and never starts after failed A. A green slice alone cannot mark the entire build integrated. R11's integration RC behavior is completed in T07.

## T07 — Validated plans and gate protocol

Dependencies: T06. Estimate: 10–16k. Files: `plan/slice.py`, `dag.py`, `judge.py`, `integration_gate.py`, `summary.py`, CLI, plan/gate tests.

- [ ] Parse into a validated plan with source-line diagnostics. Reject duplicate/empty IDs, unsupported SUBSLICE blocks, unknown dependency IDs, cycles, invalid complexity, and missing acceptance selectors.
- [ ] Define allowed-path/protected-test semantics and supported selector syntax. Handle spaces and platform paths; reject traversal/absolute target escapes and unsupported multiline brief syntax rather than silently dropping text.
- [ ] Introduce a structured test-run result carrying return code, captured output/log path, timeout/error class, and candidate identity. Keep an explicit compatibility adapter for legacy injected runners; production never falls back to parsing prose for pass/fail.
- [ ] Apply the same RC authority to slice judging, validation probes, and integration. Cover collection/teardown errors, interrupted runs, zero collected tests, and passing runs with no summary line.
- [ ] Implement the A07 exit/gate table in both step and whole-plan commands. Include `needs_repair` everywhere; complete means integrated and verified. Update repair marking to verify evidence.
- [ ] Return useful integration-required, budget/policy-blocked, invalid-plan, and lock outcomes; never conflate them with build success. Keep human summaries and machine gates consistent.
- [ ] Exercise dry-run validation without provider execution, every exit code, old supported plans, obsolete block rejection, and no phantom pending nodes.

**Gate:** R06/R11 and A01/A02 pass. Run the full offline suite at **M2**. Record final CLI/state contracts for T11 before host-specific work starts.
