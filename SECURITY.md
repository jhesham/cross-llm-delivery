# Security policy and execution boundaries

Use the repository's GitHub Security tab/private vulnerability reporting
channel for confidential reports. Do not include credentials or private code
in a public issue. If that channel is unavailable, obtain a private contact
from the maintainer before disclosing details.

## What CLD checks

CLD runs executor CLIs in managed Git worktrees, reconstructs the candidate
against the frozen baseline, protects acceptance/configuration inputs, enforces
the writable allowlist and independently runs pytest. Collection requires
checked commits/durable refs; integration verifies the frozen accepted
candidate in an owned worktree. Invalid/corrupt state and unsafe managed paths
fail closed, and failed attempts retain diagnostics.

These gates protect delivery integrity. They do not make generated code safe
to execute, prove test completeness, or replace code/security review.

## What CLD does not isolate

A **Git worktree is not a security sandbox**. Git hooks, executor tools and
project tests can execute code as the host user. CLI subprocesses inherit
authentication, environment and filesystem/network capabilities permitted
by the host/provider. Acceptance sees the candidate Git tree; it cannot undo
external side effects or observe every file outside the repository.

Provider permissions differ. Current Antigravity/OpenCode adapters include
headless permission flags; Cursor has its own CLI boundary. The Codex adapter
requests `workspace-write` (or explicit read-only), uses stdin and an ephemeral
session, and does not add full-access/approval-bypass flags. None is a universal
sandbox guarantee. Inspect the selected provider's setup/fragment and use
appropriate host isolation for untrusted projects.

Denied permissions/authentication should be resolved through the intended
provider configuration. Preserve the attempt and inspect its logs; do not
recommend blanket permission bypass to make acceptance pass. Recursive CLD
dispatch is refused at the executor boundary, not a substitute for OS isolation.

## Data and recovery

Prompts, model output, patches, worktrees, test/process logs and telemetry may
contain sensitive project material. Preserve necessary recovery evidence under
`.cld/`; redact it before sharing. The engine has no required third-party
runtime dependency, but provider processes, explicitly used behavioral grading
and opt-in telemetry export can make network calls.

Do not delete accepted refs/ledgers/worktrees during recovery. Stop writers,
back up state byte-for-byte, and use the documented migration/repair/integration
commands. Old engines cannot read schema-2 state. See [migration](docs/MIGRATION.md)
and [rollback](docs/plans/codex-support/T19B-ROLLBACK.md).

## Maintenance

There are no long-term support branches. Candidate source, supported released
versions and their evidence must be distinguished; a branch push is not a
published release or proof of every platform/provider's live compatibility.
