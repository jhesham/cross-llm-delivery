# Current handoff

Updated: 2026-09-10. Initiative: Codex support and review remediation.

**State:** T01 through T03 complete; paused before T04 for explicit user confirmation
of token availability. Branch `refactor/codex-support`, remote `public` on GitHub.
T03 starts from `a6b1b68`; resolve its closing commit with
`git log -1 --format=%h --grep='^fix: T03 '`. Commit/push verification precedes
this sitting's final pause.

**Mandatory checkpoint:** Verify and commit each slice with its progress updates, then
wait for explicit confirmation of token availability before starting another. No
next-slice dispatch. T04 has not started.

**Next after confirmation:** [T04: resumable attempts/worktrees](01-ACCEPTANCE-RECOVERY.md#t04--resumable-attempts-and-worktrees).
Estimate 10–16k lead tokens. Read `worktree.py`, `recovery.py`, the worktree/cleanup
branches in `orchestrator.py`, and the remaining escalation regression. Add unique
attempt branch/path identities and safe configured roots, stale/active ownership and
resume behavior. Replace the hardcoded expected cleanup path when introducing new
roots. Preserve old `slice-<id>` branches and existing `refs/cld/accepted/` and recovery
refs. Do not delete failed candidates merely to avoid collisions.

**T03 evidence:** [Full record](T03-EVIDENCE.md). 501 passed, 3 strict xfailed, 1 live
evaluation deselected, 2 existing warnings. CLI/summary follow-up: 34 passed.
R01 through R03 closed; remaining xfails are escalation collision (T04) and dependency
visibility/failure blocking (T06). Log: `.cld/t03-verification/full-suite.log`.

**Implemented boundary:** `RecoverySession` writes per-attempt patches and raw logs,
checks binary patch reconstruction in an isolated index, and pins recovery trees.
`collect` checks commit/tree/ref and preserves the tested tree before hooks. A durable
`collected` journal precedes the final ledger DONE write. Save failures roll back the
in-memory entry and keep the worktree; success cleanup rechecks it. Failed worktrees
are always retained. Cleanup warnings/paths appear in both CLI modes and detail JSON.
The user's tracked checkout is unchanged.

**Restart:** The narrow collected-commit/final-ledger-save-failure case can reconcile
without provider redispatch after verifying repo/ledger/task/base/ref/tree/fingerprint.
Other interrupted states remain T04. Journal format is version 1; additive ledger fields
are `collection`, `recovery_path`, `worktree_path` plus existing `commit`. T05 still owns
full ledger versioning, corruption handling, build identity and locking.

**Commands** (repository root):

```text
python -m pytest tests/integration/test_review_regressions.py -o addopts="" -q --runxfail --tb=short
python -m pytest tests/integration/test_collection_recovery.py -o addopts="" -q --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

The unmasked command intentionally fails only for remaining T04/T06 defects. Source
bundle smoke/import tests pass. Committed plugin copies remain unchanged for T12/T17.
T02 restrictions still apply: committed protected acceptance, explicit simulation for
report-only doubles, no symlinks/junctions/submodules, and snapshots without Git metadata.

**Dogfooding/usage:** Kimi K3 via OpenCode remains selected; resolve its exact model ID
before the first live dispatch, without substitution. Bootstrap through T09 before
live delegation. No provider calls this sitting; executor usage zero, lead counters
unavailable. Windows, Python 3.13.13, Git 2.54.0.windows.1; no new POSIX execution.
This is a refactoring-branch checkpoint, not a release or merge.
