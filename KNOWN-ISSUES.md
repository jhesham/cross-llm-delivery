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
and do not automatically retry or increase limits. Recent Kimi dogfood attempts
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

The Cursor adapter works around the recorded long-prompt Windows shim issue
by resolving the versioned Node entrypoint. If that layout changes, inspect the
resolver/configuration and `CURSOR_AGENT_CMD`; do not assume the workaround
applies to every CLI release. Provider-specific permission/auth caveats live
in generated `references/provider-setup.md`.

## State and acceptance

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
deleting previous run evidence. Optional OTLP export is separate from local
durable state and should be enabled only under the user's data-sharing policy.
