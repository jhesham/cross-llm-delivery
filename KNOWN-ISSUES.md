# Known issues and limitations

## Evidence scope

Offline CI covers Windows/Ubuntu × Python 3.11/3.14 and eight host/provider
bundles. Recorded Windows discovery and live provider checks apply only to the
versions/surfaces named in [the evidence matrix](docs/plans/codex-support/T19B-MATRIX.md).
New fast-tier live service, updated Claude picker discovery, fourth Codex-plugin
discovery, live Claude-lead execution, live provider mid-process interruption,
Ubuntu Codex flag inspection/live POSIX dispatch and macOS remain unverified.
Offline success must not be advertised as live support on those surfaces.

## Usage, timeouts and model access

Only reported usage is known. Antigravity usage may be entirely unavailable;
Cursor/Codex dollar cost is unknown when no CLI cost field is supplied.
OpenCode `step_finish` events can supply usage/cost, but an unfinished turn may
not provide a complete total. Unknown is never zero or a subscription-derived
estimate. Budget ceilings admit dispatches with reservations and cannot stop
a provider at an exact token/dollar boundary.

The dispatch default is 600 seconds, probe default 30 seconds. Explicitly
configure `CLD_DISPATCH_TIMEOUT` for a larger slice; preserve failure evidence
and do not automatically retry or increase limits. Since 0.3.1 a timeout, like
authentication, launch, capability, network and Codex service-tier errors, is
a final executor error: one dispatch, no retry or escalation, gate 5. Recent Kimi dogfood attempts
timed out without a candidate; that history is not a reason to substitute models
or treat incomplete usage as free.

Codex requires an exact model spec. `codex:gpt-6-luna@max+fast` requests fast
explicitly; warnings/fallback diagnostics or reported tier mismatch fail before
diff capture. Missing actual-tier telemetry cannot establish that the server
delivered fast service. No account entitlement or static default is inferred.

## CLI drift

Provider catalogs/setup notes describe observed snapshots, not guaranteed
current availability. Inspect the installed CLI and explicitly validate a
changed model/account/configuration under the authorized policy. The default
policy denies validation spend; first use is not an automatic paid probe.

The Codex adapter launches the native binary without a shell: `CODEX_CLI_CMD`,
then `codex.exe` on PATH, then the native executable inside an npm install. A
shim-only install blocks dispatch with a message naming `CODEX_CLI_CMD`. The
npm package layout is an observed snapshot and may change.

The Cursor adapter works around the recorded long-prompt Windows shim issue
by resolving the versioned Node entrypoint. If that layout changes, inspect the
resolver/configuration and `CURSOR_AGENT_CMD`; do not assume the workaround
applies to every CLI release. Provider-specific permission/auth caveats live
in generated `references/provider-setup.md`.

## Codex Windows sandbox setup

For backup, fallback, model-free checks and rollback instructions, see
[Codex Windows sandbox troubleshooting](docs/CODEX-WINDOWS-TROUBLESHOOTING.md).

On one Windows Server 2025 machine, standalone Codex CLI 0.158.0 with
`windows.sandbox = "elevated"` fails shell startup with
`helper_unknown_error: setup refresh had errors`. The helper log reports
`CreateFileW` failure while validating a 291-character Codex runtime path.
That directory opens with an extended-path prefix but not normally; this
suggests a helper path-handling problem. It is not established as a
0.158.0-specific regression or a failure on every Windows installation.

Inspect `CODEX_HOME/.sandbox/` logs and use model-free `codex sandbox` checks
before spending on another validation dispatch. On that machine, the
operator-approved `unelevated` fallback restores shell execution and editing
in a workspace directory with inherited ACLs. This changes native Codex
isolation globally and is weaker than `elevated`; CLD must not switch it
automatically. See [official OpenAI Windows sandbox guidance](https://learn.chatgpt.com/docs/windows/windows-sandbox).

Version 0.3.0 release bundles also have a Windows workspace-permissions
compatibility issue: Python 3.13.13 private temporary directories and
administrator-created files can lack write permission for the restricted
token's current-user account. Creating a new sandbox-owned file can succeed
while editing pre-existing `calc.py` or a checked-out file fails.

Repository source now grants inheritable Modify permission to the exact current
user on newly created CLD probe repos and worktrees, before dispatch. It keeps
private probe parents/evidence unchanged, preserves existing denies, and blocks
dispatch on permission-setup failure. Model-free regressions exercise the
installed sandbox's edits and protection of source, Git metadata and evidence.
The elevated-helper failure is separate and still requires local setup repair
or an operator-selected fallback. Existing v0.3.0 release assets predate this
source fix: build a coherent set from updated source; do not edit installed
engine files individually or mark a real model verified from these offline
fixture checks. No paid retry was performed.

## Claude Code executor

The `claude` executor bills only the logged-in Claude subscription
(`authMethod: "claude.ai"`); API-key variables are removed from its
environment. Its shell is **not sandboxed** and runs with the user's
privileges, like OpenCode, Cursor and Antigravity. Each dispatch is an isolated
`claude -p --safe-mode --restricted` session with no hooks, plugins, skills,
MCP servers, CLAUDE.md or saved session. The CLI's dollar figure is recorded as
an estimate only; CLD cost stays unknown, so use token and attempt budgets.
Plan usage limits stop a slice with the final `usage_limit` error.

Live evidence (Windows, CLI 2.1.286): an isolation probe, a validation plus
one-slice delivery, and a Codex-lead (`gpt-6.1-sol`) two-slice build to gate 3.
The canary lead ran unsandboxed (`--sandbox danger-full-access`); a sandboxed
Codex lead with explicit writable roots, live POSIX/macOS and live
mid-process interruption remain unverified.

## State and acceptance

Candidate capture ignores new, untracked tool caches and packaging metadata
(`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.hypothesis`,
`.tox`, `.nox`, `htmlcov`, `.eggs`, `*.egg-info`, `.coverage*` and
`CACHEDIR.TAG` directories); tracked files with those names are still judged.
The judge snapshot checks tracked candidate files only: new files a test run
creates are listed in attempt evidence rather than rejected.

Plans currently require top-level slice blocks and single-line values.
Nested sub-slices and multiline briefs are unsupported. Behavioral grading is
an optional library facility; it is not wired into the delivery acceptance gate
and cannot override a failed deterministic verdict.

Schema-2 ledgers require explicit legacy migration; changed plans require
reconciliation. Integration does not automatically merge the user's checkout.
A collected/accepted slice and an integrated/verified build are different
states. See [migration/recovery](docs/MIGRATION.md).

Run events/artifacts are retained per run under `.cld/runs/<run-id>/`; compatibility
event/summary paths may also exist. Starting a new build does not authorize
deleting previous run evidence. `--gc` removes only CLD-managed worktrees that
are safe to remove (preview by default): the slice must be proven from recovery
evidence and not actively owned, the worktree must hold no changes or ignored
non-cache data, and the ledger must belong to `--repo`. Anything unprovable is
kept. It never deletes run evidence or refs. Optional OTLP export is separate from local
durable state and should be enabled only under the user's data-sharing policy.
