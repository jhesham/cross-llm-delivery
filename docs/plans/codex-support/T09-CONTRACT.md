# T09 — Model admission contract

2026-09-18. Applies to the source delivery CLI. Generated bundles refresh in T12/T17.

Every selected production entry and escalation rung passes one canonical resolution and
admission policy before executor construction. Unknown providers fail explicitly; explicit
model IDs remain selected. Providers and writable worktree, artifact and evidence locations
are checked before validation dispatch. The entire selected set is checked for policy blocks
before spending on any probe. Rungs are frozen for the invocation. Context is rechecked before
production executor construction; a change defers work with gate 5.

## Permission and evidence

- `--validation-policy deny` is the default. Fresh matching verified evidence permits production;
  a needed validation is blocked. Static verified/likely catalog labels are insufficient.
- `unmetered` permits probes for catalogued free/flat models; `allow` also permits metered or
  unknown-cost probes. Classification is not an account billing guarantee. All selected rungs
  are checked up front, so a fallback may be validated without later production use.
- Failed evidence or a failed catalog classification blocks until `--revalidate-models`.
  A fresh verified local verdict supersedes an older catalog failure. Forced validation bypasses
  static and durable shortcuts, then deduplicates the new result per model/context in this run.
- Verified evidence defaults to a 30-day maximum age, configurable in seconds. Identity includes
  canonical model/effort, repository, CLI executable/script contents, tracked configuration and
  environment. Legacy contextless evidence is not fresh. Changed or expired evidence needs a probe.
- Common provider config paths and OPENCODE_CONFIG are tracked. Additional files use repeatable
  `--validation-config`; opaque external/account changes use `--validation-context`. Hidden remote
  configuration changes cannot be detected automatically. Only the hash is stored, not environment
  values or configuration contents. Binary/script hashes provide CLI identity without version calls.
- Evidence writes take an OS-held lock, reread the latest records, and atomically replace the file.
  Missing evidence is a cache miss; corrupt/unreadable evidence blocks even forced validation.

## Trusted validation and recovery

Each probe has a new retained Git repository with a committed failing assertion and stub.
The shared candidate verifier protects acceptance tests and judges an isolated snapshot;
executor prose and reported file lists cannot grant acceptance. Probe Git hooks/signing are
locally disabled. Test execution uses T08 containment and bounded deadlines. A normal pytest
nonzero exit is a test outcome, not a process-infrastructure error (also corrected in the CLI).

Validation uses one attempt, with no retry or fallback. Failed candidate acceptance produces
`revalidate`; executor/auth/test infrastructure failure produces `untested`, preserving the
reason without asserting that the model lacks capability. Interruptions retain evidence and
propagate. Unconfirmed process cleanup prevents inspection. Artifacts live outside the candidate
repository so they cannot contaminate immutable tree comparisons.

Each probe retains validation.json, usage supplied by the executor, recovery state and patches.
The run validation directory holds admission.json and blocked diagnostics. Unknown usage remains
unknown; T10 owns cumulative build accounting and budget reservations. Full CLI JSON is T11.
The older injectable resolve_and_validate helper remains compatible for library callers; production
CLI admission uses the stricter context-aware Admission gate.

## Regression boundary

Offline tests cover defaults, tags, explicit unknown IDs, escalation, failed/forced/fresh/expired
verdicts, provider/filesystem/policy blocks without model calls, concurrent evidence writers,
atomic replace failure, tampered and committed acceptance tests, auth failure, cancellation,
fresh probe isolation, and CLI validation-before-production ordering. No live provider calls.
