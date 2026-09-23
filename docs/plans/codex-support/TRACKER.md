# Progress tracker

Status: T01 through T11 and M1–M3 complete. **T12A complete**; T12B requires the user's next token checkpoint.

User checkpoint policy: verify and commit each slice, then stop and obtain explicit confirmation of token availability before the next. Apply this to every Txx task and any child slices. Do not auto-advance.

Tick a task only after its detailed checkboxes and acceptance gate pass. Add evidence and a commit SHA, or explicitly record that the verified changes are still uncommitted. `blocked`, `in progress`, and `deferred` belong in the evidence column; an unchecked box must not be treated as completed. Update the matching milestone in [the overview](../../../IMPLEMENTATION_PLAN.md).

**Task completion checklist**

- [x] T01 — Baseline and real regressions
- [x] T02 — Independent candidate verification
- [x] T03 — Checked collection and preservation
- [x] T04 — Resumable attempts and worktrees
- [x] T05 — Build identity and ledger migration
- [x] T06 — Dependency and integration lifecycle
- [x] T07 — Validated plans and gate protocol
- [x] T08 — Bounded subprocess execution
- [x] T09 — Model validation and preflight
- [x] T10 — Usage and admission budgets
- [x] T11 — Host-neutral CLI interface
- [ ] T12 — Host-aware skill generation
  - [x] T12A — Standalone Codex generator
  - [ ] T12B — Host metadata and parity
- [ ] T13 — Codex installation and discovery
- [ ] T14 — Cross-host acceptance
- [ ] T15 — Optional Codex executor contract (deferred)
- [ ] T16 — Optional Codex executor implementation (deferred)
- [ ] T17 — Wheel, bundle, and CI coverage
- [ ] T18 — Checked release automation
- [ ] T19 — Migration and interruption rehearsal
- [ ] T20 — Documentation and release candidate

The checklist above is the task-level completion record. The table below holds its dependencies, estimates, and evidence. Budgets are estimated **lead-agent input + output tokens per sitting**, excluding separately reported executor/model usage. They are neither context-window sizes nor a hard runtime limit. See [session rules](SESSION-GUIDE.md).

| Task / suggested sitting | Depends on | Estimate | Evidence / commit |
|---|---|---|---|
| [T01 — baseline and real regressions](01-ACCEPTANCE-RECOVERY.md#t01--baseline-and-regression-harness) | — | 6–10k | Complete: [evidence](T01-EVIDENCE.md); 421 passed, 9 xfailed, 1 deselected; commit `ddd4333` |
| [T02 — independent candidate verification](01-ACCEPTANCE-RECOVERY.md#t02--independent-candidate-verification) | T01 | 12–18k | Complete: [evidence](T02-EVIDENCE.md); 479 passed, 6 xfailed, 1 deselected; commit `a6b1b68` |
| [T03 — checked collection and preservation](01-ACCEPTANCE-RECOVERY.md#t03--checked-collection-and-preservation) | T02 | 10–16k | Complete: [evidence](T03-EVIDENCE.md); 501 passed, 3 xfailed, 1 deselected; closing commit subject starts `fix: T03` |
| [T04 — resumable attempts and worktrees](01-ACCEPTANCE-RECOVERY.md#t04--resumable-attempts-and-worktrees) | T03 | 10–16k | Complete: [evidence](T04-EVIDENCE.md); M1 513 passed, 2 xfailed, 1 deselected; closing commit subject starts `fix: T04` |
| [T05 — build identity and ledger migration](02-STATE-ORCHESTRATION.md#t05--build-identity-and-ledger-migration) | T04 | 12–18k | Complete: [evidence](T05-EVIDENCE.md); 532 distinct tests verified across full run/follow-up, 2 T06 xfails; closing commit subject starts `fix: T05` |
| [T06 — dependency and integration lifecycle](02-STATE-ORCHESTRATION.md#t06--dependency-and-integration-lifecycle) | T05 | 10–16k | Complete: [evidence](T06-EVIDENCE.md); 556 distinct passing tests, no xfails; closing subject starts `fix: T06` |
| [T07 — validated plans and gate protocol](02-STATE-ORCHESTRATION.md#t07--validated-plans-and-gate-protocol) | T06 | 10–16k | Complete: [evidence](T07-EVIDENCE.md); 609 distinct passing tests across full run/follow-ups; closing subject starts `fix: T07` |
| [T08 — bounded subprocess execution](03-EXECUTION-BUDGETS.md#t08--bounded-subprocess-execution) | T04 | 8–14k | Complete: [evidence](T08-EVIDENCE.md); Windows CI 645 passed, Ubuntu 642 passed/3 Windows-only skips; code/test head `53cc2c0` |
| [T09 — model validation and preflight](03-EXECUTION-BUDGETS.md#t09--model-validation-and-preflight) | T07, T08 | 8–14k | Complete: [evidence](T09-EVIDENCE.md); Windows CI 685 passed, Ubuntu 682 passed/3 Windows-only skips; code/test head `3caf863` |
| [T10 — usage and admission budgets](03-EXECUTION-BUDGETS.md#t10--usage-and-admission-budgets) | T05, T08, T09 | 8–12k | Complete: [evidence](T10-EVIDENCE.md); Windows CI 709 passed, Ubuntu 706 passed/3 Windows-only skips; code/test head `8f3c5db` |
| [T11 — host-neutral CLI interface](04-CODEX-HOST.md#t11--host-neutral-cli-interface) | T07, T09, T10 | 8–14k | Complete: [evidence](T11-EVIDENCE.md); Windows 761 passed, Ubuntu 758 passed/3 Windows-only skips; both generator smoke checks passed; code/test head `8759ce7` |
| [T12 — host-aware skill generation](04-CODEX-HOST.md#t12--host-aware-skill-generation) | T11 | 10–16k | T12A complete: [evidence](T12A-EVIDENCE.md), code/test `8ef2a38`, Windows/Ubuntu CI green; T12B not started, parent open |
| [T13 — Codex installation and discovery](04-CODEX-HOST.md#t13--codex-installation-and-discovery) | T12 | 8–14k | Not started |
| [T14 — cross-host acceptance](04-CODEX-HOST.md#t14--cross-host-acceptance) | T13, T17 | 10–16k | Not started |
| [T15 — optional Codex executor contract](05-CODEX-EXECUTOR.md#t15--codex-executor-contract-and-fixtures) | T08, T09, T11 | 8–12k | Deferred by default |
| [T16 — optional Codex executor implementation](05-CODEX-EXECUTOR.md#t16--codex-provider-and-end-to-end-proof) | T15, T13 | 10–18k | Deferred by default |
| [T17 — wheel, bundle, and CI coverage](06-PACKAGING-RELEASE.md#t17--wheel-bundles-and-ci) | T12 | 8–12k | Not started |
| [T18 — checked release automation](06-PACKAGING-RELEASE.md#t18--checked-release-automation) | T17 | 8–12k | Not started |
| [T19 — migration and interruption rehearsal](06-PACKAGING-RELEASE.md#t19--migration-and-interruption-rehearsal) | T14, T18 | 10–18k | Not started |
| [T20 — documentation and release candidate](06-PACKAGING-RELEASE.md#t20--documentation-and-release-candidate) | T19 | 6–10k | Not started |

Default sitting order: **T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10 → T11 → T12 → T13 → T17 → T14 → T18 → T19 → T20**. Optional T15/T16 can follow M5 or be inserted after T13 if the user wants the fourth provider in the same release. Do not let optional provider work defer review fixes.

The dependency graph permits some independent work, but does not authorize spawning agents. One implementer is the default. Any separately authorized parallel implementation must own disjoint files, and generated bundles should be regenerated by one owner after source changes settle.

**Completion record template**

```text
Date / task:
Changed files:
Checks and results:
Evidence path / commit:
Lead token usage: measured / estimated / unavailable
Executor usage and cost: measured / unknown / no dispatch
Remaining limitation:
Next task:
```

**Progress log**


- 2026-09-09 — Planning files created from the full-build review and verified Codex documentation; local CLI reports 0.153.4. No implementation tasks completed and no live model calls made.
- 2026-09-09 — User selected Kimi K3 via OpenCode for dogfooding. Codex retains lead/test/review responsibilities. Exact model ID remains to be verified; no automatic model substitution. The 20 task units have not yet been converted to executable acceptance-test-backed CLD slices.
- 2026-09-09 — Prepared the 13-file planning baseline for commit before T01. User requires verification/commit and an explicit token-availability checkpoint after every slice; no implementation task started.
- 2026-09-10 — T01 complete: shared production capture in integration harnesses; 11 portable regressions/control cases, including 9 strict expected failures verified with `--runxfail`. Final suite 421 passed, 9 xfailed, 1 deselected. No live model use; lead usage unavailable. Next T02 requires explicit user confirmation. Commit: `ddd4333` (T01).

- 2026-09-10 — T02 complete: immutable base/candidate capture, protected acceptance preflight, isolated snapshot judging, rechecked collection tree and explicit simulation boundary. R01/R02 acceptance defects closed. Final suite 479 passed, 6 xfailed, 1 deselected; targeted post-dispatch capture fault passed separately. No live model dispatch; lead usage unavailable. Refactoring branch checkpoint is committed/pushed before pausing for T03.

- 2026-09-10 — T03 complete: checked collection/ref persistence, per-attempt reconstructable recovery patches and diagnostics, final-ledger-save rollback/reconciliation, and delayed cleanup. R03 closed; final suite 501 passed, 3 xfailed, 1 deselected. CLI/summary follow-up: 34 passed. No live model dispatch; lead usage unavailable. Commit/push checkpoint then pause for T04.

- 2026-09-11 — T04/M1 complete: unique run/session worktrees, configured roots, pre-creation reservation, bounded restart/escalation context, OS-held slice ownership and legacy preservation. Fixed a Windows parent-creation/path-resolution race found by the first full run. Final suite: 513 passed, 2 xfailed (T06), 1 deselected. No sub-agents/provider calls; lead usage unavailable. Codex sub-agent preference saved as `gpt-5.6-luna` at `max`. Commit/push then pause for T05.

- 2026-09-11 — T05 complete: schema-2 identity, explicit backed-up migration/reconciliation/new builds, whole-operation writer ownership, stale-write rejection, repo-scoped default state and preserved run histories. Registry operations serialized after a real-Git race was exposed. Full run: 531 passed plus one outdated fixture corrected; CLI follow-up: 41 passed (532 distinct verified tests), 2 T06 xfails, 1 deselected. No sub-agents/provider calls; lead usage unavailable. Commit/push then pause for T06.

- 2026-09-15 — T06 complete: verified dependency bases, build-owned integration worktrees/refs, explicit frozen suite, failure/interruption preservation, idempotent retry, manual verification and whole-plan integration. Full suite: 555 passed, 1 live eval deselected; follow-up: 3 passed, 556 distinct tests verified. Both R05 xfails removed. No sub-agents/provider calls; lead usage unavailable. Commit/push then pause for T07.

- 2026-09-17 — T07/M2 complete: validated plans, structured RC-authoritative test results, verified repair, consistent gates and recorded status. Full offline run: 603 passed, three outdated test expectations corrected; final follow-up: 52 passed, selector follow-up: 68 passed. 609 distinct tests verified, no xfails, one live evaluation excluded. R06/R11/A01/A02 closed. No sub-agents/live model calls; lead usage unavailable. Commit/push then pause for T08.

- 2026-09-18 — T09 complete: unified model/context admission, recorded validation spend policy, trusted isolated probes, synchronized atomic evidence and all-selected-provider preflight. R09/A07 closed. Final CI: Windows 685 passed; Ubuntu 682 passed/3 Windows-only skips; both generator smoke checks pass. Local full run plus follow-up covers 685 distinct tests. No sub-agents/live calls; executor usage zero, lead counters unavailable. Code/test head `3caf863`; closing docs subject starts `docs: close T09`. Pause before T10.

- 2026-09-23 — T10/M3 complete: durable per-attempt usage, cumulative ledger totals, validation/retry/escalation budget reservations, explicit unknown policy, bounded status snapshots and sink cleanup. R12/A06 closed. CI: Windows 709 passed; Ubuntu 706 passed/3 Windows-only skips; both generator smoke checks passed. No live calls/sub-agents; executor usage zero, lead counters unavailable. Code/test head `8f3c5db`; closing docs subject starts `docs: close T10`. Pause before T11.

- 2026-09-23 — T12A complete: Codex standalone skill generation for all three providers, YAML-first entry metadata, bundle references and isolated driver. Kimi K3/OpenCode timed out after producing the permitted draft; the lead corrected two faulty acceptance assertions and reviewed/manual-integrated the code. Nine corrected tests remained red on baseline; 25 focused passed on feature. Local full suite and Windows/Ubuntu CI with default generator smoke passed; Codex smoke passed locally. Code/test `8ef2a38`, [evidence](T12A-EVIDENCE.md). Production usage unknown, partial lower bounds retained. Parent T12 remains open; pause before T12B.
