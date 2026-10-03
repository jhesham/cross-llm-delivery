# Engine architecture

The lead host supplies instructions and an installed driver. The provider
package supplies CLI execution. Neither host nor model prose replaces the
engine's candidate/acceptance/integration boundaries.

| Module | Responsibility |
|---|---|
| `cld.cli`, `cld.cli_response` | Legacy/vendored driver, machine JSON gates and inspection |
| `cld.plan.slice`, `cld.dag` | Validated single-line slice schema and dependency layering |
| `cld.providers_api`, `cld_providers.<name>` | Provider registration, explicit model configuration and adapters |
| `cld.process`, `cld.worktree` | Bounded child/process-tree handling and managed Git worktrees |
| `cld.candidate`, `cld.acceptance`, `cld.judge`, `cld.test_run` | Reconstructed frozen candidates, snapshot-owned project imports, protected inputs and authoritative pytest results |
| `cld.ledger`, `cld.build_state`, `cld.attempts`, `cld.recovery`, `cld.locking` | Durable identity, ownership and per-attempt recovery |
| `cld.orchestrator`, `cld.integration`, `cld.repair` | Verified dispatch/collection, dependency integration and lead repair |
| `cld.admission`, `cld.evidence`, `cld.validate` | Context-bound model evidence, provider-owned configuration inputs and explicit validation spend policy |
| `cld.accounting`, `cld.usage` | Persisted reservations, reported/unknown usage and admission ceilings |
| `cld.telemetry`, `cld.status` | Best-effort local/export events and build inspection |

The five adapters are antigravity, cursor, opencode, codex and claude. A generated
bundle vendors one selected provider and the engine; different bundles sharing
a ledger must come from the same source revision. Codex requires an exact
model and optional effort/tier; there is no static default.

Each executor returns a candidate result with process/usage evidence. On valid
completion the adapter captures the actual Git diff. The engine independently
reconstructs it against the original baseline, enforces protected inputs and
the allowlist, and runs committed acceptance tests. Collection checks the
resulting tree/commit/ref before durable acceptance. Dependent dispatch uses
verified integration, not an unmerged accepted commit.

The production acceptance gate is deterministic. `cld.behavioral` is an optional
G-Eval library facility using an explicitly constructed metric/API-backed
judge; it is not wired into automatic acceptance and does not replace pytest.
Absent dependencies are guarded at import; calling grading requires optional
dependencies and authorized credentials/spend.

Usage and cost come only from reported provider fields. Missing data remains
unknown. Limits admit dispatches using explicit reservations, not a hard token
cap or inferred subscription price. See [delivery-core.md](delivery-core.md)
for gates, admission, budget and recovery behavior.

A worktree is a Git/file-integrity boundary, not an OS sandbox. Provider
permissions and project tests inherit host capabilities. Optional telemetry
failure is not delivery success/failure; durable ledger/ref proofs are separate.
