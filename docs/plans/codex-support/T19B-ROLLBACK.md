# T19 rollback and merge rehearsal

Use the ledger's original resolved path. Stop all writers first; never remove
lock files to force access. A copied schema-2 envelope still binds to its original
path and repository: an archive is preservation evidence, not a new active ledger.

Immediately after migration, **before any new dispatch or state changes**:

1. Find the exact backup path reported by `--migrate-ledger` and recorded in
   `build.backup`. Inspect it and the active ledger. Keep the original plan.
2. Copy the active schema-2 ledger to a new archive name; refuse overwriting an
   existing archive. Verify its SHA-256/bytes match the active ledger.
3. Restore the exact legacy backup bytes to the original ledger path only once
   the archive is verified and all writers have exited. Retain both copies.
4. A current engine requires explicit migration again; it must not silently
   accept the restored legacy state. The rehearsal verifies a new run ID and
   preserves the archived schema-2 bytes, original HEAD and existing backup.

After new work has run, automatic rollback is unsupported. **Keep the active
schema-2 ledger**, legacy backup, refs and `.cld/runs/` evidence. Do not run an
older engine against schema-2 state: old code is not required to understand it.
If downgrading application binaries, suspend this build until a schema-compatible
engine is restored; use a separate fresh consumer checkout/ledger for old code.
No branch reset, ref deletion, forced merge or worktree removal belongs here.
The post-dispatch rehearsal archives the new envelope, confirms accepted code
remains reachable and then integrates with a current compatible engine.

Inspect integration using the current driver and exact persisted selector:

```text
python -m cld plan.md --repo <consumer-repo> --ledger <original-ledger> --status --json
python -m cld plan.md --repo <consumer-repo> --ledger <original-ledger> --integrate --integration-tests <committed-selector> --json
```

Read `build.integrated_ref` and `build.integrated_sha` from that ledger. Verify
`git rev-parse <integrated-ref>` equals the saved SHA, and that each accepted
commit is an ancestor using `git merge-base --is-ancestor <accepted-sha>
<integrated-sha>`. Inspect `git diff HEAD <integrated-sha>` and the integration
proof before choosing a clean target branch and explicitly merging that exact
SHA (`git merge --no-ff <integrated-sha>`). Stop if the target is dirty, has moved
since review, or conflicts; resolve deliberately and run its own target tests.
CLD acceptance/integration does not merge the original checkout automatically.

The tests use disposable repositories only. No initiative branch/main merge or
release is authorized or performed by this document.
