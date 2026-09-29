# Phase 3 — Processes, model validation, and usage budgets

Outcome: external work is bounded, failures are diagnosable, and usage survives retries/resume. Relevant architecture: A09–A11. Use synthetic executables and fixtures until the later live gates.

## T08 — Bounded subprocess execution

Dependencies: T04. Estimate: 8–14k. Files: all three provider default runners, `executors/base.py`, `orchestrator.py`; proposed `engine/cld/process.py` and local process fixtures.

- [x] Define a common process result and lifecycle supporting argv, cwd, environment additions, prompt stdin, deadline, cancellation, separate stdout/stderr artifacts, and exit/error classification.
- [x] Apply configurable dispatch deadlines to all providers and remove Cursor's unused timeout behavior. Set deadlines for model-listing/preflight commands too.
- [x] Terminate spawned process trees on timeout/cancellation on supported platforms, wait for termination, then inspect/preserve edits before cleanup. Test Windows and POSIX implementations separately.
- [x] Classify missing binary, access denial, authentication failure when observable, timeout, malformed output, and nonzero dispatch distinctly. Keep bounded error feedback plus full-log paths.
- [x] Keep provider argv/encoding/shim fixes intact. Do not log secrets or silently change approval/sandbox policy. Preserve raw failure output from both streams.
- [x] Test a sleeper, child-spawning sleeper, nonzero exit after file writes, long prompt, invalid UTF-8, cancellation, and cleanup after partial output. These tests use no external service.

**Gate:** R10 passes; deadline and cancellation terminate the test child tree, and R02 remains closed. Provider contract suites pass with existing fixtures.

**Complete 2026-09-17:** [contract](T08-CONTRACT.md), [evidence](T08-EVIDENCE.md).
Final CI on `53cc2c0`: Windows 645 passed; Ubuntu 642 passed, three Windows-only
skips. Both platforms pass generator smoke checks. No live provider calls.

## T09 — Model validation and preflight

Dependencies: T07/T08. Estimate: 8–14k. Files: `validate.py`, `evidence.py`, `models.py`, `providers_api.py`, CLI, provider/preflight tests.

- [x] Apply a single resolution/validation policy to build defaults, slice tags, explicit unknown IDs, and escalation rungs. Cache results per resolved model/context during a run.
- [x] Respect durable failed/verified evidence, explicit revalidation, CLI/model/config changes, and configured evidence expiry. Ensure forced revalidation actually bypasses every cached/static short circuit.
- [x] Define noninteractive behavior: unknown or potentially billed validation needs a recorded spend policy; absence yields a structured blocked result instead of stdin prompts or automatic premium fallback.
- [x] Run validation through the same trusted candidate/judge/process contracts, in a fresh isolated repository per probe. Count validation usage, and distinguish executor/auth failure from model capability failure.
- [x] Make evidence writes atomic and synchronized so concurrent validations retain all records; distinguish unreadable/corrupt evidence from a clean cache miss in diagnostics.
- [x] Preflight every selected provider, not just the build default. Check writable worktree/artifact location and surface restricted-workspace limitations before dispatch.
- [x] Verify default/tag/escalation/unknown/known-bad/forced-validation behavior with fake dispatches. Assert no model is called when policy, CLI, or filesystem preflight blocks it.

**Gate:** R09/A07 close. A fresh unknown model cannot go straight to a production slice. Validation, retries, and blocked reasons are observable without interactive prompting.

**Complete 2026-09-18:** [contract](T09-CONTRACT.md), [evidence](T09-EVIDENCE.md).
Final CI on `3caf863`: Windows 685 passed; Ubuntu 682 passed, three Windows-only
skips. Both generator smoke checks pass. R09 and defect A07 closed. No live calls.

## T10 — Usage and admission budgets

Dependencies: T05/T08/T09. Estimate: 8–12k. Files: `orchestrator.py`, `ledger.py`, `telemetry.py`, `usage.py`, `status.py`, provider usage parsers, budget tests.

- [x] Store per-attempt usage, model/provider/effort, retry/escalation reason, CLI version, validation usage, and cost provenance. Accumulate across all attempts and resumed invocations.
- [x] Define normalized input/output/cached/total semantics; retain raw provider usage and distinguish derived totals. Do not double-count caches or sum overlapping categories.
- [x] Populate rendered costs from persisted data. Unknown usage/cost stays unknown; implement Antigravity parsing only if a real documented/recorded source exists, otherwise correct its claims.
- [x] Add explicit attempt and cumulative token/cost admission policies. Reserve available budget under the build lock before concurrent dispatch; include validation and escalation. Use unknown-cost policy rather than treating null as zero.
- [x] Stop admitting new work at the limit and report any already-in-flight allowance/overrun. Support status output explaining why budget blocked the next action. Do not promise a provider-level token kill switch where none exists.
- [x] Bound status reads using per-run indexing/snapshots or a measured incremental reader, and reconcile snapshots after crash. Close/flush telemetry sinks cleanly and preserve complete artifacts.
- [x] Test two failures then success, mixed-model escalation, interrupted/resumed attempt, concurrent admission at threshold, unknown costs, and exact agreement between ledger and status aggregates.

**Gate:** R12/A06 close, A09 remains covered, and M3 passes its full offline suite. Record measured versus estimated usage separately in the task evidence. Decide initial canary budgets based on selected provider/account rather than fixed stale price assumptions.

**Complete 2026-09-23; M3 closed:** [contract](T10-CONTRACT.md), [evidence](T10-EVIDENCE.md).
Final CI on `8f3c5db`: Windows 709 passed; Ubuntu 706 passed, three Windows-only skips.
Both generator smoke checks passed. R12/A06 closed; A09 recovery remains covered. No live calls.
Canary allowances remain contingent on verifying the selected model/account; no stale prices or
unverified live-spend allowance are introduced by this offline gate.
