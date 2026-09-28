# Migration, resume and recovery

Use the same engine revision across bundles that share a ledger. Save the old
skills and ledger/worktree/ref evidence before switching. A new bundle does
not implicitly migrate state. Stop writers before copying/restoring state.

## State identity and paths

The default ledger is `<repo>/.cld-ledger.json`, bound to the canonical repo,
plan fingerprint and durable run ID. An explicitly relative `--ledger` uses
the invocation cwd; use an absolute path when changing cwd/hosts. Status is
read-only and does not invoke a provider:

```bash
python scripts/run_delivery.py --status --repo <absolute-repo> --json
```

Attempts/events/process logs live under `<repo>/.cld/runs/<run-id>/` and failed
worktrees are retained. Inspect the response's `artifacts`, `accepted_refs`
and diagnostics; do not guess an old slice-level log filename.

## Legacy ledger

Run with the original committed plan and repository:

```bash
python scripts/run_delivery.py <absolute-plan.md> --repo <absolute-repo> --migrate-ledger --json
```

This explicit state operation creates a backup and does not dispatch. Review
its backup path and reconciliation gate. Legacy entries without provable
refs/acceptance cannot become trusted merely because an old status says done.
Corrupt/unreadable state blocks; preserve it and diagnose before any recovery.

## Changed plan or new build

Use `--reconcile-plan` to back up state and invalidate changed slices and
dependents. Use `--new-build` only for an intentionally separate run with a
backup; neither command dispatches. Do not delete state to bypass identity,
accepted-ref, ownership, dependency or budget checks.

## Interrupted or failed work

Resume by repeating the original `--step` command with the same plan/repo/ledger
and authorized model/limits. Durable accepted work is reused; an unaccepted
attempt may require a new dispatch under the existing admission policy. Do not
assume incomplete logs report complete usage, and do not silently retry paid work.

For gate 4, inspect the retained attempt/worktree and edit only the authorized
source allowlist. Keep acceptance tests and protected/configuration inputs
unchanged. Verify/collect the repair without another provider call:

```bash
python scripts/run_delivery.py <absolute-plan.md> --repo <absolute-repo> --mark-repaired <slice-id> --json
python scripts/run_delivery.py <absolute-plan.md> --repo <absolute-repo> --integrate --integration-tests <committed-selector> --json
```

An accepted repair returns gate 6 until integrated. Integration failures retain
their candidate/conflict evidence. Resolve against the recorded integration
state, or use `--integrate --manual-integration <merge-commit-or-ref>` with an
explicit test selector to verify an existing merge. Final integration proof
records a ref/SHA; it does not modify the user's original checkout automatically.

If process/auth/permission/collection checks fail, preserve logs and partial
files. Restore provider access through its supported configuration, fix denied
paths or a failing hook, and re-enter the documented repair/recovery path.
Choose an accessible `--worktree-root` before a build rather than moving
recorded worktrees or enabling blanket permission bypass. Never fabricate a
passing ledger entry or delete a retained accepted ref to hide a failure.

## Downgrade and rollback

Old engines cannot read schema-2 state. Before any new accepted work, retain a
byte-identical schema-2 archive and the migration backup, then follow the
[rehearsed rollback guide](plans/codex-support/T19B-ROLLBACK.md). After new work,
keep schema-2 active and retain its branches/refs; restoring the old backup
would discard new progress. Replacing skills and restoring state are separate
operations. Do not let an old bundle write a new ledger.
