# Current handoff

Updated: 2026-09-09. Initiative: Codex support and review remediation.

**State:** Plan complete; implementation not started. Baseline source commit: `c3ced8a5fbbb964019352f04da8d509858644ee8`. The initial planning baseline contains 13 Markdown files; use Git history to identify its documentation commit. No source changes or installs were made in the planning sittings.

**Mandatory checkpoint:** The user requires a stop after every slice to confirm token availability. Verify and commit each slice with its progress updates, then wait for an explicit user reply before starting another. Each Txx task is a checkpoint until split; child slices each require their own checkpoint. No automatic next-slice dispatch.

**Next:** [T01](01-ACCEPTANCE-RECOVERY.md#t01--baseline-and-regression-harness). Read its section and inspect the existing Git harness. Establish portable regressions for the acceptance/recovery defects before changing engine behavior. Budget 6–10k estimated lead tokens.

**Decisions:** Codex lead-agent support is required; a Codex executor is optional. Keep one engine and existing Claude bundles. Safety/recovery fixes precede live dogfooding. Full plan: [overview](../../../IMPLEMENTATION_PLAN.md); status: [tracker](TRACKER.md).

**Executor selection:** The user selected Kimi K3 via OpenCode for dogfooding. Preserve that choice; resolve its exact available model ID before first dispatch, without substituting another model. Bootstrap T01–T07 directly and finish T08/T09's bounded execution/validation before live delegation. Convert later tasks into executable slices only after their contracts and acceptance tests are prepared.

**Evidence:** Previous review: 419 offline tests passed; 1 live evaluation deselected. Three bundle smoke checks passed. Wheel imports failed because provider Markdown resources were omitted. Eight failure probes were reproduced. The portable defect conditions are in [DEFECTS.md](DEFECTS.md); optional machine-local originals remain at `D:\claude_server\cld-review-artifacts`.

**Codex compatibility:** Local `codex --version` reports 0.153.4. `exec --help` exposes JSONL output, stdin prompts, working-root and sandbox options; no live invocation tested. Official docs and version caveats: [SOURCES.md](SOURCES.md).

**Pending:** All implementation tasks and all live compatibility gates. No credentials are needed for T01. The user's Kimi K3/OpenCode selection persists for implementation; no live dispatch has occurred. Exact model availability and account cost remain to be checked.

**Usage:** Planning-session token totals are not exposed here; no executor dispatch occurred. No invented usage estimate recorded as measured data.
