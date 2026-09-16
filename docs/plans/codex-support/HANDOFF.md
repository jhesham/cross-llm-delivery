# Current handoff

Updated: 2026-09-17. Initiative: Codex support and review remediation.

**State:** T01 through T07, M1 and M2 complete. Paused before T08 pending explicit
confirmation of token availability. Branch `refactor/codex-support`, remote `public`.
Starting commit `d30623e`; resolve the T07 closing commit with
`git log -1 --format=%h --grep="^fix: T07 "`. Verify commit/push before final pause.
This is a refactoring checkpoint, not a release or merge.

**Next after confirmation:** [T08: bounded subprocess execution](03-EXECUTION-BUDGETS.md#t08--bounded-subprocess-execution).
Estimate 8–14k. Read that contract, all provider default runners, executors/base.py,
orchestrator.py and the T07 TestRun contract before designing process.py. Bound
provider dispatch/model-listing deadlines, terminate process trees on timeout/cancel,
retain partial output/edits and preserve provider argv/encoding/permission behavior.
Use synthetic processes, no live services. Test Windows and POSIX separately;
do not claim unexecuted platform coverage. Stop after this slice's verification,
commit/push and token checkpoint; do not auto-start T09.

**T07 evidence:** [T07-EVIDENCE.md](T07-EVIDENCE.md). Full offline run: 603 passed,
three outdated expectations corrected, 1 live eval deselected, no xfails, two existing
deepeval warnings, 722.98s. Final follow-up: 52 passed (4.88s); selector follow-up:
68 passed (2.74s); **609 distinct current tests verified across runs**. Logs under
`.cld/t07-verification/`: full-suite.log, final-followup.log, selector-followup.log,
early-validation-followup.log (4 passed), targeted.log (75 passed).
The only production change after full-run startup was selector syntax tightening;
the follow-ups cover it. The full run's three failures were older assertions about
when unsafe selectors fail and the missing-Git exit code; all are now verified.

**Implemented contract:** [T07-CONTRACT.md](T07-CONTRACT.md). Plans validate IDs,
fields, dependencies, cycles, literal paths, selectors and single-line syntax before
dispatch; SUBSLICE is rejected. Subsets must match the full stored task contract.
TestRun is authoritative for acceptance, integration and validation-probe RC.
Legacy RC-prefixed runners remain supported; plain prose needs explicit simulation
adaptation. Result sidecars retain output, log path, timeout/error and candidate ID.

**Repair/gates:** --mark-repaired requires the original plan and a matching retained
owned worktree. It verifies a repaired candidate in a fresh owned worktree and
collects before marking accepted/intervened. It returns 6 until integration succeeds.
Needs-repair slices do not automatically redispatch. Integration failures persist
repair evidence and return 4. Invalid input/state, missing prerequisites, locks and
quota policy blocks use 5; failure/dependency defer uses 2. Code 3 requires verified
integration; 0 means successful operation with work remaining. Telemetry includes
operation gate codes; status overlays recorded state. Versioned --json remains T11.

**State compatibility:** Schema 2 remains; legacy accepted journals remain readable.
Use current source CLI for writes. T06 integration refs, baseline isolation,
reconciliation and preservation contracts remain; [integration guide](T06-INTEGRATION.md).
Successful/failed repair and integration worktrees remain inspectable. User checkout
is untouched. Do not delete ownership lock files; process exit releases OS locks.
Source README/SKILL template now reflect the workflow; committed plugin copies
remain for T12/T17. T10 still owns aggregate usage/budget accounting.

**Usage:** No sub-agents or live model calls; executor usage zero, lead counters
unavailable. If explicitly requested, Codex sub-agents must use gpt-5.6-luna at max.
Kimi K3 via OpenCode remains gated through T09; verify exact model ID before first
live dispatch without substitution. Windows tested; no new POSIX execution claimed.
