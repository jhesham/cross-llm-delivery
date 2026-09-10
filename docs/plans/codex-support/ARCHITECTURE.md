# Architecture and implementation decisions

Status: proposed implementation contracts, selected to make the work actionable. Changes are allowed when recorded with a reason and corresponding task/test updates. These names and flags are targets; they are not available in v0.2.0.

**A01 — Separate the lead host from the executor provider.** A host supplies instructions, discovery metadata, installation layout, and how to invoke/interpret the shared CLI. A provider launches an implementation process and returns structured dispatch information. Neither the judge nor the scheduler should branch on whether the lead is Claude or Codex. Codex host support must not require a Codex provider, Claude CLI, Anthropic key, or an MCP server.

| Concern | Shared responsibility | Host/provider-specific responsibility |
|---|---|---|
| Plans, dependencies, tests, candidate verification | `engine/cld/` | None |
| Persistent state, gate results, usage | Shared engine and CLI | Parse provider usage at adapter boundary |
| Host instructions and installation | Shared workflow references | `skill/hosts/claude-code/`, `skill/hosts/codex/` (proposed) |
| Provider invocation | Shared process lifecycle contract | `engine/cld_providers/<provider>/` |
| Packaging | One generator with explicit target | Claude manifest vs Codex metadata/layout |
| Behavioral grading | Optional existing facility | No mandatory paid judge for either host |

**A02 — Trusted candidate, not trusted executor report.** Before dispatch record the immutable base SHA, allowed paths, protected acceptance inputs, run ID, and attempt ID. After the executor terminates, independently collect the complete candidate relative to that base, including staged, unstaged, untracked, binary, rename/delete, mode, and executor-committed changes. Parse Git filenames with NUL delimiters; do not split paths on lines or accept absolute/traversal paths. A failed or interrupted diff command is an error, not an empty diff.

The lead-authored acceptance tests must exist at the baseline and remain unchanged even if accidentally listed in `files`. Define protected test files plus relevant test configuration/fixtures in the plan contract. For deliberate test changes, create an explicit architect-owned operation outside ordinary executor acceptance. Establish the expected failing baseline where required; a missing test or collection/configuration error is not a meaningful red acceptance test.

Run judging on a frozen candidate snapshot with the trusted test inputs. Detect and reject test-time changes to candidate source; never stage unverified files created after the earlier diff check. Verification records a tree hash; collection must persist exactly that tree, not a later `git add -A` of arbitrary content. A worktree is Git isolation, not an OS security sandbox: provider execution must respect the actual host permission boundary.

T02 implementation decisions (2026-09-10): `CandidateVerifier` records the base before
dispatch and retains it across retries. Checked NUL-delimited Git capture supplies the
candidate tree and filenames; provider reports remain diagnostics. Judging materializes
the frozen index tree in a temporary directory and compares filesystem fingerprints
before/after execution, then recaptures the executor worktree. Collection rechecks that
tree and loads it into the index; T03 still owns commit-hook effects, checked commit
results, durable records and recovery. Tests run against Git content with trusted
environment dependencies, without the executor's ignored files or Git working metadata.

The baseline must run at least one passing test or have only assertion failures; missing
tests, collection/configuration/runtime errors and missing process RC are rejected before
dispatch. Standard test files, `tests/` contents, pytest configuration and `.gitattributes`
are protected automatically, including forbidden additions. `protected_inputs` declares
other committed fixture/data files. `allow_already_satisfied: true` permits a no-change
candidate only after a passing baseline. Both fields round-trip in slice Markdown.

Symlinks, junctions and submodules are conservatively rejected until portable safe
materialization is implemented. New bytecode/pytest cache artifacts are excluded from
the candidate; tracked cache-looking paths remain subject to ordinary checks. Git
assume-unchanged/skip-worktree flags cannot conceal edits. Python report-only callers must
explicitly select `simulation=True`, which cannot be combined with a Git boundary; the
CLI never enables simulation. Existing one-argument runners and executors without a
feedback parameter are adapted by inspecting signatures, never by retrying a TypeError.

**A03 — Persist first, report acceptance second.** Proposed lifecycle:

```text
pending -> running -> verifying -> collected -> accepted_pending_integration
                  \-> failed / needs_repair / interrupted
accepted_pending_integration -> integrated
```

An accepted slice has a verified reachable commit and durable attempt record. Build completion requires integrated slices and a passing integration gate. Save recovery artifacts before cleanup, including on dispatch, judge, commit, and ledger exceptions. Preserve the worktree if a complete recovery artifact cannot be verified. Ordinary cleanup never deletes the only copy of a candidate or accepted commit.

T03 implementation (2026-09-10): `RecoverySession` creates UUID-scoped evidence under
`.cld/<slice>/<session>/`. Dispatch/judge checkpoints save raw diagnostics, checked
binary patches, tree hashes and independent `refs/cld/recovery/<session>/...` refs.
Patch reconstruction uses a temporary bare repository/index referencing the original
object store. It never stages or resets the user's checkout. The tested tree gets its
own `verified` recovery ref before collection invokes hooks.

Collection checks every Git result, reuses an existing matching commit/no-op, rejects
hook mutations, and pins the verified commit at `refs/cld/accepted/<session>`.
An atomic, flushed/read-back `outcome.json` records `collected` before the ledger writes
DONE with commit/tree/ref/base/test fingerprints and recovery/worktree paths. The final
ledger save is flushed and atomic; an exception rolls back the in-memory status and
retains the worktree. Cleanup then rechecks the physical candidate; failures or later
edits retain that directory and surface a warning without changing the accepted commit.

All failed worktrees are retained, even with a verified recovery patch. This deliberately
keeps recovery simple until T04 introduces attempt naming/resume and cleanup policies.
For the narrow commit-success/ledger-save-failure case, restart verifies the collected
journal against the same repository, ledger, task fingerprint, original base and durable
accepted ref, then saves the ledger without another provider call. Other interrupted
states are not promoted to acceptance. T04 owns branch/worktree recovery; T05 owns the
versioned build ledger, corruption handling, locking and general identity/migration.

**A04 — Attempts have identities.** Use run-scoped unique branches/paths (for example `cld/<run>/<slice>/<attempt>`), rather than creating `slice-A` repeatedly. Store actual refs and worktree paths in the ledger; host instructions must use those recorded refs. Retain existing accepted branches during migration. Detect interrupted attempts and stale worktrees, inspect their state, and resume/retry explicitly without assuming that an existing branch is disposable. One active CLI writer per build is enforced with a recoverable lock.

T04 implementation (2026-09-11): each invocation fixes a base SHA and a run UUID;
each rung/session exclusively reserves a UUID journal before creating
`cld/<run>/<slice-slug>/<session>` and its worktree. Retry ordinals retain separate
recovery refs and artifacts within that session. The default root is
`<repo>/.cld/worktrees`; `--worktree-root` accepts an absolute directory or a path
relative to `--repo`. Roots and leaves are canonicalized and rechecked before
creation/cleanup; cleanup also verifies the recorded branch and Git common directory.

Retries within a session keep the prior candidate. Escalation and restart use a
fresh base, with bounded diagnostics and pointers to preserved refs/worktrees and
journal evidence. No automatic reset, cherry-pick or acceptance of failed work.
A hard stop before a snapshot still leaves the reserved branch/worktree discoverable.
Missing worktrees or refs are reported in the next journal without deleting remaining
artifacts. Legacy `slice-<id>` refs are inspected read-only; legacy collected worktrees
are retained for manual cleanup. Collected outcomes still reconcile without dispatch.

An OS-held, nonblocking lock per slice in the Git common directory prevents duplicate
active owners across processes/checkouts. Process exit releases ownership; PID metadata
is diagnostic, never the basis for stealing a lock. Keep lock files on disk. T05 must
add the build-wide ledger writer lock and versioned migration: this slice lock does
not prevent two separate processes delivering different slices from overwriting a
shared legacy ledger. Schema-1 journals gain `run_id`, `branch`, `worktree_root`,
`owner_pid`, `retry_policy`, and `previous`; retain these and existing accepted/recovery
refs when migrating. A configured worktree root does not relocate Python/Git test
temporary directories or provide executor sandbox enforcement (T08/T13).

**A05 — Build state is scoped and versioned.** Keep the default ledger at `<repo>/.cld-ledger.json` for continuity, but introduce a versioned envelope containing repository identity, canonical plan hash/path, initial base, run ID, integrated ref/SHA, slice fingerprints, attempt history, budgets, and integration results. Resolve explicit relative `--ledger` paths relative to the invocation directory; show the resolved path. Default path behavior changes to the target repo and must be documented.

Provide an explicit legacy migration with a backup; old DONE entries without verifiable commits do not automatically become integrated. Distinguish missing from corrupt/unreadable ledgers. Changing the plan invalidates affected slices and downstream dependencies through an explicit reconcile operation, never a silent reset. New builds get new IDs and preserve earlier evidence.

**A06 — Integrate in a build-owned branch.** `--step` dispatches one ready layer and produces accepted commits. Proposed `--integrate` combines those exact commits in deterministic order into a build-owned integration worktree, runs the configured integration suite, and advances the recorded integration SHA only on success. Later slices branch from that SHA. The user's checkout/branch remains untouched until an explicit final merge action. A failed gate or conflict preserves its candidate and cannot unblock dependents.

Keep manual integration as a compatibility path: inspect recorded accepted SHAs and prove ancestry plus suite success before advancing state. Do not merely warn about missing dependency commits. Whole-plan mode must use the same integration lifecycle; until that works, reject multi-layer unattended execution with an actionable message rather than silently running against stale HEAD. No destructive reset of the user's checkout is part of integration recovery.

**A07 — Versioned, host-neutral result protocol.** Proposed `--json` emits one JSON object on stdout for ordinary commands; human progress goes to stderr and logs stay in artifacts. Include `schema_version`, `run_id`, canonical repository/ledger, layer/slice status, `gate`, `next_action`, accepted refs, bounded failure summaries, artifact paths, usage, and budget status. Document schema and test that machine output has no banners/prompts mixed in. `--status --json` is a point-in-time snapshot; do not make hosts scrape terminal prose.

| Exit | Proposed meaning | Host action |
|---|---|---|
| 0 | Requested operation succeeded; more work remains | Follow `next_action`, often integrate or dispatch |
| 2 | Slice dispatch/test failed or deferred | Inspect bounded evidence; retry within policy |
| 3 | Build complete and integrated gate passed | Report final evidence/ref |
| 4 | Repair required, including integration conflict/failure | Lead repairs with evidence; reverify |
| 5 | Invalid input, unsafe/unreadable state, lock, policy, or budget blocks progress | Show specific reason; do not dispatch |
| 6 | Accepted work awaits integration before dispatch can continue | Run authorized integration action |

Preserve current meanings of 0/2/3/4 where they were truthful; document new 5/6 and correct the old whole-plan success bug. Repeated status/step/integrate calls must be idempotent. `--mark-repaired` must verify a reachable candidate and tests rather than setting DONE blindly.

**A08 — Host artifacts use shared source.** Add a `--host claude-code|codex` generator option; default remains Claude Code. Preserve `dist/cross-llm-<provider>` and existing Claude plugin paths. Put new Codex output under a separate root, such as `dist/codex/cross-llm-<provider>`. Generate metadata from source; never maintain copied engines by hand. YAML frontmatter is first in SKILL.md; provenance comments follow it. Keep primary skill instructions short and load references by need.

Codex standalone skills are the required route for CLI and IDE compatibility. Codex plugin distribution is additive and uses its own validated manifest/marketplace layout; do not assume the Claude manifest can be renamed unchanged. Do not overwrite user/global AGENTS.md, install hooks, or copy a repository's instructions into arbitrary target projects. A short root AGENTS.md for *this repository* can point maintainers to this plan and test commands.

**A09 — Permission-aware invocation.** Use argument arrays and explicit cwd, avoid shell-built commands, and let the host enforce its configured approvals/sandbox. Make worktree roots configurable and preflight that the requested location is writable; the existing sibling-worktree convention may be outside Codex's allowed workspace. Prefer a documented writable build-artifact location, excluded from candidate capture. Do not respond to permission errors by automatically enabling unrestricted mode or expanding write roots.

Preserve clear diagnostics for denied execution, unavailable provider CLIs, and authentication failures. Existing providers' broad permission flags need an explicit policy/capability description; they are not evidence of sandboxing. Codex-as-lead can orchestrate without granting every child unrestricted host access.

**A10 — Budgets and evidence are shared across attempts.** Model validation, retries, and escalations all count. Record per-attempt input/output/cached tokens and reported cost, with provider/model IDs and reason. Unknown cost is null/unknown, not zero. Distinguish reported total tokens from any derived total and avoid double-counting cached input. Serialize budget reservations before parallel admission; distinguish admission limits from in-flight hard limits a provider cannot enforce. Validation evidence writes must be atomic/locked and keyed to relevant model/provider/CLI/test context.

**A11 — Optional Codex executor stays optional.** Implement only after the shared execution contracts stabilize. Use capability-checked local CLI flags and sanitized real JSONL fixtures. Prefer stdin for long prompts, explicit model/config, `workspace-write`, and bounded process lifecycle. Do not guess currently available model IDs, claim a flat/free cost, inherit an unrelated interactive session, or recursively invoke CLD from the executor prompt. Authentication remains with the user's CLI, not a bundled secret.

**A12 — Migration and release discipline.** Track state/schema changes in the changelog; test upgrade and interrupted recovery with fixtures. Do not downgrade state in place; retain backups and record the compatible engine version. Public release staging must explicitly exclude machine-local evidence/credentials. Plan documents contain no secrets and can be version-controlled. Exact shipping version is chosen at T20 based on compatibility changes, not precommitted here.
