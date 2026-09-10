# Current handoff

Updated: 2026-09-10. Initiative: Codex support and review remediation.

**State:** T01 and T02 complete. Paused before T03 for explicit user confirmation of
token availability. Branch: `refactor/codex-support`, remote: `public` on GitHub.
T01 checkpoint `ddd4333` was already online. Resolve T02's closing commit with
`git log -1 --format=%h -- engine/cld/candidate.py`; this sitting commits/pushes its
verified changes before stopping.

**Mandatory checkpoint:** Verify and commit each slice with progress updates, then
wait for explicit user confirmation of token availability before starting another.
No automatic next-slice dispatch. T03 has not started.

**Next after confirmation:** [T03: checked collection and preservation](01-ACCEPTANCE-RECOVERY.md#t03--checked-collection-and-preservation).
Estimate 10–16k lead tokens. Read `candidate.py`, the two collection branches in
`orchestrator.py`, `worktree.py`, and T01's remaining preservation regressions.
Replace unchecked commits with verified commit/tree/reachability and durable outcome
recording before acceptance/cleanup. Preserve work on every exception; retain the
worktree when a recovery artifact cannot be verified. T04 owns attempt/ref collisions.

**T02 result:** [Evidence](T02-EVIDENCE.md). 479 passed, 6 strict xfailed, 1 deselected;
2 existing dependency warnings. A separately tightened post-dispatch diff-error
regression passed. R01/R02 acceptance closed; R03–R13 still open. Remaining xfails:
commit-hook preservation (single/ladder), judge-exception preservation, escalation
collision, dependency visibility and failure blocking. Log: `.cld/t02-verification/full-suite.log`.

**New contracts:** Immutable dispatch base and `Candidate` tree/test fingerprints;
engine capture ignores provider file reports. Baseline tests must be committed and
pass or fail only assertions. Protected tests/config/declared `protected_inputs`
cannot change. Judging uses a Git-materialized temporary snapshot and detects
persistent file mutations; collection rechecks and loads the tested tree. Commit-hook
and durable-save guarantees remain T03. No-op needs `allow_already_satisfied: true`
plus passing baseline/candidate tests. Real Python calls require Git and acceptance
runners; report-only doubles must explicitly set `simulation=True`. No CLI simulation.
Symlinks/junctions/submodules are rejected. Snapshots have no Git metadata or ignored
environment. Details: [architecture A02](ARCHITECTURE.md), [evidence](T02-EVIDENCE.md).

**Commands** (repository root):

```text
python -m pytest tests/integration/test_review_regressions.py -o addopts="" -q --runxfail --tb=short
python -m pytest tests/integration/test_candidate_verification.py -o addopts="" -q --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

The unmasked command still intentionally fails for defects owned by later tasks.
Committed marketplace plugin copies were not refreshed; generator smoke/import tests
pass for source-built bundles. Distribution refresh remains T12/T17.

**Dogfooding:** Kimi K3 via OpenCode remains selected; resolve its exact available model
ID before the first live dispatch, without substitution. Bootstrap through T09 before
live delegation. Codex remains lead for contracts, review and integration.

**Usage/environment:** Lead token counters unavailable; executor usage zero, no paid
provider calls. Windows, Python 3.13.13, Git 2.54.0.windows.1. Native POSIX cases have
not been executed. No release or merge; this is a refactoring-branch checkpoint.
