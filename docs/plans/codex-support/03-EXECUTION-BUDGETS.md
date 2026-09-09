# Phase 3 — Processes, model validation, and usage budgets

Outcome: external work is bounded, failures are diagnosable, and usage survives retries/resume. Relevant architecture: A09–A11. Use synthetic executables and fixtures until the later live gates.

## T08 — Bounded subprocess execution

Dependencies: T04. Estimate: 8–14k. Files: all three provider default runners, `executors/base.py`, `orchestrator.py`; proposed `engine/cld/process.py` and local process fixtures.

- [ ] Define a common process result and lifecycle supporting argv, cwd, environment additions, prompt stdin, deadline, cancellation, separate stdout/stderr artifacts, and exit/error classification.
- [ ] Apply configurable dispatch deadlines to all providers and remove Cursor's unused timeout behavior. Set deadlines for model-listing/preflight commands too.
- [ ] Terminate spawned process trees on timeout/cancellation on supported platforms, wait for termination, then inspect/preserve edits before cleanup. Test Windows and POSIX implementations separately.
- [ ] Classify missing binary, access denial, authentication failure when observable, timeout, malformed output, and nonzero dispatch distinctly. Keep bounded error feedback plus full-log paths.
- [ ] Keep provider argv/encoding/shim fixes intact. Do not log secrets or silently change approval/sandbox policy. Preserve raw failure output from both streams.
- [ ] Test a sleeper, child-spawning sleeper, nonzero exit after file writes, long prompt, invalid UTF-8, cancellation, and cleanup after partial output. These tests use no external service.

**Gate:** R10 passes; deadline and cancellation terminate the test child tree, and R02 remains closed. Provider contract suites pass with existing fixtures.

## T09 — Model validation and preflight

Dependencies: T07/T08. Estimate: 8–14k. Files: `validate.py`, `evidence.py`, `models.py`, `providers_api.py`, CLI, provider/preflight tests.

- [ ] Apply a single resolution/validation policy to build defaults, slice tags, explicit unknown IDs, and escalation rungs. Cache results per resolved model/context during a run.
- [ ] Respect durable failed/verified evidence, explicit revalidation, CLI/model/config changes, and configured evidence expiry. Ensure forced revalidation actually bypasses every cached/static short circuit.
- [ ] Define noninteractive behavior: unknown or potentially billed validation needs a recorded spend policy; absence yields a structured blocked result instead of stdin prompts or automatic premium fallback.
- [ ] Run validation through the same trusted candidate/judge/process contracts, in a fresh isolated repository per probe. Count validation usage, and distinguish executor/auth failure from model capability failure.
- [ ] Make evidence writes atomic and synchronized so concurrent validations retain all records; distinguish unreadable/corrupt evidence from a clean cache miss in diagnostics.
- [ ] Preflight every selected provider, not just the build default. Check writable worktree/artifact location and surface restricted-workspace limitations before dispatch.
- [ ] Verify default/tag/escalation/unknown/known-bad/forced-validation behavior with fake dispatches. Assert no model is called when policy, CLI, or filesystem preflight blocks it.

**Gate:** R09/A07 close. A fresh unknown model cannot go straight to a production slice. Validation, retries, and blocked reasons are observable without interactive prompting.

## T10 — Usage and admission budgets

Dependencies: T05/T08/T09. Estimate: 8–12k. Files: `orchestrator.py`, `ledger.py`, `telemetry.py`, `usage.py`, `status.py`, provider usage parsers, budget tests.

- [ ] Store per-attempt usage, model/provider/effort, retry/escalation reason, CLI version, validation usage, and cost provenance. Accumulate across all attempts and resumed invocations.
- [ ] Define normalized input/output/cached/total semantics; retain raw provider usage and distinguish derived totals. Do not double-count caches or sum overlapping categories.
- [ ] Populate rendered costs from persisted data. Unknown usage/cost stays unknown; implement Antigravity parsing only if a real documented/recorded source exists, otherwise correct its claims.
- [ ] Add explicit attempt and cumulative token/cost admission policies. Reserve available budget under the build lock before concurrent dispatch; include validation and escalation. Use unknown-cost policy rather than treating null as zero.
- [ ] Stop admitting new work at the limit and report any already-in-flight allowance/overrun. Support status output explaining why budget blocked the next action. Do not promise a provider-level token kill switch where none exists.
- [ ] Bound status reads using per-run indexing/snapshots or a measured incremental reader, and reconcile snapshots after crash. Close/flush telemetry sinks cleanly and preserve complete artifacts.
- [ ] Test two failures then success, mixed-model escalation, interrupted/resumed attempt, concurrent admission at threshold, unknown costs, and exact agreement between ledger and status aggregates.

**Gate:** R12/A06 close, A09 remains covered, and M3 passes its full offline suite. Record measured versus estimated usage separately in the task evidence. Decide initial canary budgets based on selected provider/account rather than fixed stale price assumptions.
