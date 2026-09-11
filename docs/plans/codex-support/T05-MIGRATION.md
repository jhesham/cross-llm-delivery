# T05 — ledger migration and recovery

Schema 2 is the production state format from T05. These commands refer to a
consumer repository and its executable CLD slice plan, not IMPLEMENTATION_PLAN.md
or the initiative tracking documents.

## Paths and identity

The default ledger is `<repo>/.cld-ledger.json`, regardless of the caller's working
directory. An explicit relative `--ledger` still resolves against the invocation
working directory. Dispatch prints both resolved paths. A build records its
canonical repository, Git common directory, ledger path, plan path/hash/source hash,
initial base, stable run ID and task fingerprints/dependencies. Moving/copying a
bound ledger to another path is blocked; retain its original path or start a fresh
build with a separate ledger. Reconciliation cannot retarget state to another repo.

A schema-2 envelope contains `schema_version`, `build` and `entries`. Utility/test
ledgers may have `build: null`; they also require explicit migration before their
entries can be trusted for production delivery. Unknown schema, malformed JSON,
invalid entries and access errors block instead of returning empty state.

## Explicit state operations

```text
python skill/scripts/run_delivery.py plan.md --repo D:\path\repo --migrate-ledger
python skill/scripts/run_delivery.py plan.md --repo D:\path\repo --reconcile-plan
python skill/scripts/run_delivery.py plan.md --repo D:\path\repo --new-build
```

All three commands perform state preparation only and do not dispatch providers.
Use the original plan for migration. The exact original bytes are backed up beside
the ledger using a unique `.legacy-<id>.bak` or `.reconcile-<id>.bak` filename; the
result reports that path. Repeating migration on an unchanged migrated build is a
no-op.

Reachable old DONE commits/branches are recorded as evidence but do not establish
acceptance or integration. A matching T03/T04 collected journal must independently
verify before retaining DONE (meaning accepted under the pre-T06 engine).
Otherwise the entry becomes `needs_repair` and dispatch blocks. Inspect the backup,
refs and migration history before explicitly reconciling to redeliver those slices.
No migration sets an integrated SHA or claims that a build is integrated.

A changed plan/base blocks normal dispatch. Reconciliation creates a new run and
invalidates changed slices and their downstream dependents, including dependencies
removed from the new plan. Independent unchanged entries remain. A changed base or
`--new-build` invalidates all current slices. Old entry outcomes, backups, refs and
artifacts remain available; unaccepted work from a prior run is never automatically
promoted in the new run. Source/path changes also require deliberate reconciliation.

## Ownership and artifacts

`<ledger>.lock` is held from state loading through selection, dispatch, final saves
and CLI artifact/telemetry finalization. `<ledger>.owner.json` records PID, acquisition
time, ledger path and the run ID when already bound. Status/usage readers do not take
a writer lock. Process death releases the OS lock; a leftover owner file is not proof
of a live writer. Never delete lock files to force access. Retry after the current
writer exits. Stale loaded objects also fail a byte-for-byte comparison before save,
so a later writer cannot overwrite intervening changes.

New evidence lives under `.cld/runs/<run-id>/<slice>/<session>/`, with retry artifacts
inside each session. Events append to `.cld/runs/<run-id>/events.jsonl`; summary calls
receive separate directories under that run. `.cld/current-run.json` identifies the
current run and ledger. Legacy journals and `.cld/events.jsonl` stay untouched.
The current pointer is published after durable ledger state and can be repaired by
reopening the same valid build. The ledger is authoritative if pointer publication
was interrupted. Build directories are exclusively reserved before use.

Worktree branches remain `cld/<run>/<slice-slug>/<session>`. The Git common directory
also contains `cld-worktrees.lock`, which serializes registry add/remove operations
(with a bounded 10-second acquisition wait); executor work still runs in parallel.
Existing per-slice ownership remains an additional guard across builds/checkouts.

## Rollback limits

A failed atomic replacement retains the original ledger and any completed backup.
Restart with the same CLI/plan; do not infer acceptance from a directory or branch.
For rollback immediately after migration and before any new dispatch/state changes,
stop all writers and restore the exact backup to the original ledger path. Preserve
the schema-2 ledger too for inspection. Do not run a pre-T05 CLI against schema-2
state: older code can misread it as empty. After new work has run, automatic rollback
is not supported; retain both ledgers and reconcile their recorded refs/evidence.
No Git branch reset/deletion or worktree deletion is part of migration/rollback.

T06 adds integration state transitions. T07 still owns the complete gate/exit
protocol and verification of `--mark-repaired`; T10 adds aggregate usage and bounded
status indexing. Token accounting is not completed by this migration.

For direct engine callers, pass the complete plan through `plan_slices` when
executing only a layer. `Ledger.bind` requires `with ledger.writer(...)`; read-only
`Ledger.load` never migrates. The engine owns the writer lock for real delivery,
while explicit simulation retains its existing test-double behavior.
