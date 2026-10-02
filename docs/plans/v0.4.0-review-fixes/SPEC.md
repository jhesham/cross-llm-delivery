# v0.4.0 review fixes (R01–R06) — design

Status: design approved in conversation 2026-10-02; awaiting written-spec review.
Source: [REVIEW-2026-10-01](../v0.3.1-fixes/REVIEW-2026-10-01.md) (R07 already fixed
in the Claude executor work). Gate: v0.4.0 is not tagged until these land.

## Goal

`--gc` never removes unfinished, actively owned, foreign or ignored-data
worktrees; validation evidence follows OpenCode credentials referenced by its
configuration; a network failure late in a long log is still final. Each fix
lands red-first with the review's reproduction as its regression test. No
existing guarantee weakens.

## R01 — slice identity from recovery evidence

GC no longer infers a worktree's slice from its sanitized, truncated slug. For
a managed worktree `(run_id, session_id, path)`, GC looks for exactly one
`.cld/runs/<run_id>/<slice-dir>/<session_id>/outcome.json` whose record names
that session and the same resolved worktree path, and takes the slice ID from
that record. Missing, ambiguous, unreadable or mismatched evidence → `keep`
(reason states why). Status lookup then uses the true slice ID, never the slug.
Integration worktrees keep their transaction-record identity.

Tests (real Git): IDs `A.B` (needs_repair, dirty) and `A_B` (integrated) — only
`A_B`'s worktree may be removed; two IDs sharing their first 40 characters;
a worktree with no evidence is kept.

## R02 — ownership before decision and removal

For every slice-worktree candidate in any run, GC takes that slice's existing
repository-wide nonblocking lock (`cld.attempts.slice_owner`, keyed by the true
slice ID from R01) and holds it while it re-checks eligibility (status, dirty
state) and removes the worktree. If the lock is held elsewhere → `keep`
("active owner"). Integration worktrees of the current run follow the build
writer lock GC already holds; those of other runs are removable only when that
run's transaction `outcome.json` records `passed` or `failed`, otherwise `keep`.

Test: another process holds `slice_owner(repo, "A")` and a different ledger's
writer lock; GC with `--apply --include-previous` keeps the worktree.

## R03 — configuration-referenced environment

`Provider` gains `config_env: Optional[Callable[[Sequence[Path]], tuple[str, ...]]]`.
Admission adds its returned names to the provider's `context_env` patterns
before hashing (values hashed, never stored). OpenCode implements it by scanning
its existing config paths for `{env:NAME}` references.

Tests: an unchanged config with `"apiKey": "{env:ANTHROPIC_API_KEY}"` yields
different fingerprints for two credential values, including a custom variable
name; an unrelated session variable still leaves the fingerprint unchanged;
names are recorded, values are not.

## R04 — repository binding for GC

Before discovery or mutation, `--gc` requires a bound ledger's `build.repo`
and Git common directory to match `--repo` (the delivery binding rule). A
mismatch blocks with gate 5 and removes nothing, in text and JSON modes. An
unbound (empty) ledger keeps today's behaviour: every worktree is an
earlier-build candidate.

## R05 — ignored data counts as dirty

`worktree_dirty` uses `git status --porcelain --ignored`. A worktree is dirty
when it has tracked or untracked changes, or any ignored path that is not a
disposable cache under the existing candidate-noise rule (`_is_noise`). The
dirty check applies to **every** removal candidate, not only earlier builds;
a dirty candidate is kept with reason "uncommitted or ignored local data".

Tests: an ignored `cache/retained.db` keeps the worktree; ignored
`__pycache__`/`.pytest_cache` alone do not.

## R06 — classify network failures from complete output

Before falling back to the bounded `raw_log`, the orchestrator reads a bounded
tail (64 KiB each) of the retained `stdout_path` and `stderr_path` named in the
failed result's process metadata. Only failed dispatches are classified;
successful ones are never reclassified.

Tests: more than 4,000 characters of ordinary stdout followed by
`getaddrinfo ENOTFOUND` on stderr with `nonzero_exit` → one dispatch,
`network_unavailable`, no escalation; a successful dispatch mentioning a
recovered network error stays successful.

## Delivery and release

Lead-implemented (no CLD dogfood) under TDD, in finding order R04, R05, R01,
R02, R03, R06. Then: full offline suite; push for CI; regenerate bundles; one
`[Unreleased]` changelog covering the Claude executor and these fixes; update
`KNOWN-ISSUES.md`; tag v0.4.0 and publish only on the user's explicit go-ahead.
The review file is committed alongside, with each finding marked fixed.
