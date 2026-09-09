# Current handoff

Updated: 2026-09-10. Initiative: Codex support and review remediation.

**State:** T01 complete; T02 has not started. Paused for explicit user confirmation of token availability. T01 changes are tests and documentation only. Source baseline: `c3ced8a5fbbb964019352f04da8d509858644ee8`; planning baseline: `7cdc31e`. Resolve the T01 commit with `git log -1 --format=%h -- tests/integration/test_review_regressions.py`.

**Mandatory checkpoint:** The user requires a stop after every slice to confirm token availability. Verify and commit each slice with its progress updates, then wait for an explicit user reply before starting another. Each Txx task is a checkpoint until split; child slices each require their own checkpoint. No automatic next-slice dispatch.

**Next after confirmation:** [T02: independent candidate verification](01-ACCEPTANCE-RECOVERY.md#t02--independent-candidate-verification). Budget 12–18k estimated lead tokens. Read capture/delivery/judge boundaries and T01 tests. Record immutable dispatch base and independently verify all edits, including committed changes and failed dispatch writes. Remove only the strict xfail markers whose contracts T02 actually fixes.

**Decisions:** Codex lead-agent support is required; a Codex executor is optional. Keep one engine and existing Claude bundles. Safety/recovery fixes precede live dogfooding. Full plan: [overview](../../../IMPLEMENTATION_PLAN.md); status: [tracker](TRACKER.md).

**Executor selection:** The user selected Kimi K3 via OpenCode for dogfooding. Preserve that choice; resolve its exact available model ID before first dispatch, without substituting another model. Bootstrap T01–T07 directly and finish T08/T09's bounded execution/validation before live delegation. Convert later tasks into executable slices only after their contracts and acceptance tests are prepared.

**T01 evidence:** [Full record](T01-EVIDENCE.md). Baseline: 419 passed, 1 deselected. Final: 421 passed, 9 strict xfailed, 1 deselected, 2 existing dependency warnings. Unmasked regressions: exactly 9 intended contract failures and 2 passing preservation controls. Shared production capture replaces duplicated integration-harness implementations. R01–R13 remain open; A04 is closed.

**Commands** (repository root):

```text
python -m pytest tests/integration/test_review_regressions.py -o addopts="" -q --runxfail --tb=short
python -m pytest tests/integration -o addopts="" -q -rx --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

The unmasked command intentionally fails until defects are fixed. Local logs: `.cld/t01-verification/`. One preexisting concurrent-worktree test failed intermittently before passing in the next integration run and final suite; its assertion now prints details. No concurrency fix claimed; investigate recurrence under T04.

**Codex compatibility:** Local `codex --version` reports 0.153.4. `exec --help` exposes JSONL output, stdin prompts, working-root and sandbox options; no live invocation tested. Official docs and version caveats: [SOURCES.md](SOURCES.md).

**Pending:** T02 onward and all live compatibility gates. Kimi K3/OpenCode selection persists; no live dispatch has occurred. Exact model availability and account cost remain to be checked.

**Environment/usage:** Windows, Python 3.13.13, Git 2.54.0.windows.1. No paid/provider calls, installs, global Git changes, or publication in T01. Lead token counters unavailable; executor usage zero.
