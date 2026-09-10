# T03 — Checked collection and preservation

Date: 2026-09-10. Starting checkpoint: `a6b1b68`, `refactor/codex-support`.
Closing commit: resolve with `git log -1 --format=%h --grep='^fix: T03 '`.

## Implemented

- Collection returns a `CollectionResult` with checked commit/tree/ref or a specific
  error. It checks staging, commits, ancestry, tree equality, ref creation and readback.
  Existing executor commits and valid no-ops are reused without inventing a commit error.
- The tested tree is preserved under a separate recovery ref before commit hooks run.
  Both staged and unstaged hook changes reject acceptance. Accepted commits stay
  reachable through `refs/cld/accepted/<session>`, independently of slice branches.
- `outcome.json` records a verified collection before the final ledger save. The ledger
  now carries commit, collection metadata and evidence/worktree paths. Final save failure
  restores the previous in-memory entry and retains the physical worktree.
- Successful cleanup happens only after that save, with another candidate check.
  Cleanup failure or later edits leave the worktree in place and report its path/warning.
  Failed worktrees are always retained. Direct worktree contexts also retain on exception.
- Per-attempt dispatch/judge/error output and binary patches live under unique session
  directories. Patches include executor commits and later writes relative to the original
  base, not mutable HEAD. Each saved patch is applied in an isolated index and must
  reconstruct the captured tree exactly. If capture, writing, readback or reconstruction
  fails, no cleanup occurs; diagnostics identify the retained worktree.
- A restart can reconcile a valid `collected` journal after the final ledger save failed.
  It validates repository/ledger/task/base, accepted ref/tree and test fingerprint before
  saving DONE, without running the provider again. A changed ref blocks recovery; later
  physical edits survive cleanup. Broader interrupted-attempt recovery remains T04.

## Verification

Final full suite: **501 passed, 3 strict xfailed, 1 live evaluation deselected, 2 existing dependency deprecation warnings; exit 0 in 364.95s.**

A final CLI/summary change made retained paths visible in both whole-plan and step output. Its affected tests passed separately: **34 passed in 3.01s**. Collection/recovery code did not change after the full suite started.

Targeted checks already passed:

- Original review/preservation regressions: **9 passed, 3 strict xfailed**, 76.98s.
  The three R03 cases now pass without markers: rejecting commit hook (single and
  ladder paths), and judge exception preservation.
- Collection/recovery plus ledger/orchestration/summary checks: **77 passed**, 87.33s.
  Tests use real Git repositories, real pytest acceptance and local fault injection.
  They cover failed staging/commit/ref/patch verification, evidence write failure,
  staged/unstaged hook mutation, binary patch reconstruction, ledger failure/restart,
  cleanup failure, per-retry diagnostics, exception/cancellation and no-op collection.
- Final suite additionally includes valid executor-commit reuse and recovery with a
  changed ref or a later physical edit. No production code bypasses the new boundary.

Commands from the repository root:

```text
python -m pytest tests/integration/test_review_regressions.py tests/integration/test_preserve_diff.py -o addopts="" -q --tb=short
python -m pytest tests/integration/test_collection_recovery.py tests/test_bulk_loop.py tests/test_ledger.py tests/test_summary.py tests/test_orchestrator_parallel.py tests/test_orchestrator_resume.py -o addopts="" -q --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

Local full output: `.cld/t03-verification/full-suite.log` (ignored). Existing generator
tests build/smoke all three source bundles; provider tests use offline recorded responses.

## Recovery contract and limits

`<repo>/.cld/<slice>/<session>/outcome.json` is the recovery journal. It contains the
original base, worktree path, task fingerprint, latest checked patch/ref and any collected
commit. Within each `attempt-<n>/`, `dispatch.txt`, `judge.txt`, `tests-*.txt`, optional
`error.txt` and phase-specific `.patch` files retain that attempt's evidence. Attempt 0
contains baseline-test output. Recovery refs preserve complete tree objects, including
the separately pinned tested tree if a hook later overwrites the working files.

Inspect the journal and retained worktree first. To reconstruct a patch, start a separate
clean checkout of the journal's `base` and apply its absolute patch path with
`git apply --index --binary`. Do not apply it blindly to a current dirty checkout. Refs
under `refs/cld/recovery/` are preserved evidence, not a claim of test acceptance; only
a checked collected outcome qualifies for the narrow ledger reconciliation path.

The journal is schema version 1; ledger fields are additive to the old layout. T05 still
owns full ledger versioning, corrupt-ledger behavior, repository/build reconciliation
and writer locking. Existing `slice-<id>` branch/path naming is unchanged, so T04 still
must address retries/escalation across worktrees and other interrupted states. T06 still
owns dependency integration. No automatic garbage collection of retained worktrees or
recovery refs is introduced here.

Snapshot/capture restrictions from T02 remain: symlinks/junctions/submodules fail closed,
acceptance uses committed inputs, and Git isolation is not an OS security boundary.
Evidence I/O/Git failure can leave incomplete artifacts; the retained worktree is then
the recovery source. Arbitrary host failure/power-loss durability is not claimed beyond
checked Git operations and atomic flushed file writes.

Environment: Windows, Python 3.13.13, Git 2.54.0.windows.1. POSIX behavior was not newly
executed. No live provider calls; Kimi K3 via OpenCode remains selected for later work.
Executor token use is zero; lead token counters unavailable (10–16k was a task estimate).
Committed plugin copies remain unchanged pending T12/T17 distribution work. This slice
is a source refactoring-branch checkpoint, not a release or merge.

Next: pause for explicit user token confirmation before T04.
