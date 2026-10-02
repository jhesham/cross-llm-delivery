# Delivery core: gates and authorization (shared, host-neutral)

This reference is vendored identically into every host variant of the
cross-llm delivery skill. It fixes the two things that must not drift between
hosts: the driver's gate (exit-code) contract and the authorization rules the
lead agent follows, whichever host orchestrates the build. Host-specific
workflow details live in each host's own references, not here.

## Gate contract (driver exit codes)

Every `python scripts/run_delivery.py` invocation ends at a gate. Prefer
`--json` so the gate and summary are machine-checkable, then act on the exit
code:

- **0** -- the operation succeeded; work remains. Continue with the next step.
- **2** -- execution/test failure or dependency defer; inspect the named
  evidence under `<repo>/.cld/runs/<run-id>/` before retrying anything.
- **3** -- every slice is integrated and verified; review the recorded
  commit/ref. The build is done.
- **4** -- lead repair is required; follow the host's repair loop. Failed
  worktrees are retained for that purpose.
- **5** -- invalid plan/state, missing prerequisite, lock or policy block;
  resolve the named cause first. Do not retry blindly.
- **6** -- accepted commits await integration; integrate before dispatching
  any dependent slice.

Acceptance and integration are separate: an accepted slice is not verified
until `--integrate --integration-tests <selector>` has merged and re-tested
the frozen candidate. The selector is frozen for the build and every selected
test must pass after each layer is integrated: for a layered plan, choose tests
that are already green or belong to earlier layers, never a later slice's
still-red acceptance test.

## Final executor errors and network access

Some executor errors cannot succeed on retry: authentication, missing binary,
access denied, launch error, missing capability, invalid invocation, recursive
dispatch, Codex service-tier warning/mismatch, timeout, network unavailable and
diff capture. Each costs at most one dispatch: CLD stops the slice without
retrying or escalating to another model, keeps its worktree and evidence, and
returns gate 5 with the action to take. The slice stays pending; resume after
fixing the cause.

`--step`, validation and every other dispatching command make paid network
calls through the executor CLI. Inside a Codex sandbox (default
`workspace-write` has no network), run them with network-enabled or escalated
permissions. CLD blocks before dispatch when `CODEX_SANDBOX_NETWORK_DISABLED=1`
is set, and treats connection failures as `network_unavailable` instead of
retrying.

## Validation and budget policy

The production CLI admits the default, per-slice overrides and every planned
fallback rung through `cld.admission.Admission`. Static catalog labels do not
authorize dispatch. Validation defaults to `deny`; `unmetered` permits only
catalogued free/flat probes, and `allow` permits metered/unknown-cost probes.
Fresh evidence binds the exact executor spec, CLI/config/account context and
maximum age (30 days by default). Only provider-declared environment variables
and proxy/certificate settings enter that context; per-session host variables
do not, so evidence carries across lead sessions. `--revalidate-models` still requires the
selected validation-spend policy. Corrupt evidence blocks; no automatic paid
validation is implied by first use or an outdated catalog.

`--budget-attempts` counts validation, production and retries. Token/cost
ceilings require positive `--attempt-tokens`/`--attempt-cost` reservations.
Reservations admit calls; they cannot stop a running provider at an exact
token/dollar boundary. Actual overruns block later calls. Missing usage remains
unknown; under a ceiling it blocks by default, unless `--unknown-usage reserve`
explicitly charges the recorded allowance. Never infer zero usage/cost from a
subscription. Start with one worker and only the allowance needed for this
sitting; public CLI defaults remain four workers.

## Recovery and integration

Use absolute plan/repo/ledger paths when changing cwd. Default state is
`<repo>/.cld-ledger.json`; an explicit relative `--ledger` uses invocation cwd.
Resume the original plan and bound repo; inspect `--status --json` first.
Attempts and durable run events live under `.cld/runs/<run-id>/`. Status,
integration, repair verification and explicit migration operations do not
dispatch a provider.

Legacy state requires `--migrate-ledger` with its original plan. Changed plans
require `--reconcile-plan`; an intentional fresh run uses `--new-build`. These
operations preserve backups and do not grant dispatch permission. Do not
delete ledgers/worktrees/accepted refs or write a passing entry by hand.
`--gc --json` previews which CLD-managed worktrees are safe to remove;
`--gc --apply` removes only integrated slices' and superseded integration
worktrees (`--include-previous` adds clean earlier-build worktrees). It never
removes failed or repair-pending worktrees, run evidence or `refs/cld/*`.

For gate 4, inspect the retained worktree, edit only authorized source files,
then run `--mark-repaired <slice-id>` with the original plan. Gate 6 requires
`--integrate --integration-tests <committed-selector>`. Integration checks the
accepted frozen commits in an owned worktree; inspect its ref/SHA before an
explicit merge into the user's intended branch. Failed collection, tests or
integration retain evidence. Restore denied access through provider/host
configuration rather than blanket permission bypass.

Old engines cannot read schema-2 ledgers. Before rollback, stop writers and
preserve byte-identical active state, migration backups, worktrees and refs.
After new accepted work, retain schema-2 rather than restoring a stale backup
and losing that progress. Source-repo recovery instructions are in
`docs/MIGRATION.md` and `docs/plans/codex-support/T19B-ROLLBACK.md`.

## Explicit Codex service tier and deadline

### Executor picker (read-only discovery)

Run `python scripts/list_models.py --json` from the installed skill directory
to build the agent's model menu from its vendored provider. The source checkout
discovers all installed provider modules; standalone skills include only their
own executor. For Codex, use the `cross-llm-codex` skill. Present the returned
exact IDs and efforts, let the user choose, and pass that explicit spec to the
delivery driver. Host/lead models are selected in Claude Code or Codex itself,
not through this executor menu.

Codex discovery uses `codex debug models --bundled` under `CLD_PROBE_TIMEOUT`.
It makes no inference call or catalog refresh. The installed binary's catalog
can be stale and does not establish account access, successful validation or
price. Hidden entries are excluded. Missing/older CLI discovery yields no
Codex rows; the user can still enter an exact `codex:<model-id>@<effort>` spec.
Do not invent other family/version combinations or substitute a listed ID.

Codex rows stay `untested` / `metered-unknown`: model-only evidence does not
validate another effort, tier or current context. In the chat browse/search
helpers use `headless_only=False` to show them, with the untested label.
`spec_with_effort` retains the explicit Codex effort even for the picker default.
The CLI's Browse option offers executor, provider, model, effort, then tier.
The default effort is `low` if supported, otherwise `medium`; if neither is
listed, require an explicit effort choice. This applies to Sol and Astra too.
Higher effort, including `max`/`ultra`, is an explicit choice. Tier defaults to
standard (no override); `+fast` is opt-in and is not proof of access or pricing.
Honor an existing exact user selection rather than resetting it to these defaults.

When the user selects Codex max effort with fast mode, preserve the full spec
`codex:gpt-6-luna@max+fast` on default, per-slice and rung selections. Only
Codex accepts `+fast`; invalid suffixes fail locally. Validation evidence for
this spec is separate from `codex:gpt-6-luna@max`. CLD sends explicit effort
and service-tier config arguments, rejects warning/fallback diagnostics before
Git diff capture, and never retries after silently removing the tier. Missing
actual-tier telemetry cannot prove server-side fast processing.

The shared `CLD_DISPATCH_TIMEOUT` environment setting defaults to 600 seconds.
For a longer max-effort slice the lead can explicitly set a finite positive
value, such as 1200 seconds, under the user's existing budget authorization.
Read-only probes keep their separate `CLD_PROBE_TIMEOUT` (default 30 seconds).
This does not raise attempt or token limits or authorize another paid call.
A timeout is a final error: the slice stops instead of retrying the same config.
See `references/provider-setup.md` for shell examples.

## Authorization guidance (all hosts)

- **The user picks the executor and model.** Present the shortlist once,
  before the first dispatch of a build, and keep that choice for the whole
  build. A default existing is not permission to choose on the user's behalf;
  never silently choose or switch models.
- **Billed work needs existing authorization.** Never claim a provider's cost
  is free. Before dispatching on a metered model (including validation runs on
  one), confirm the spend is covered by the user's existing authorization; ask
  only when that is unclear. Declining falls back to the default with the
  user's agreement.
- **Repairs follow the host's active approval policy.** On gate 4, fix only
  the permitted source files in the retained worktree; keep committed
  acceptance tests and protected inputs unchanged. Repair verification and
  integration never invoke the provider, and never modify the user's checkout.
- **No silent re-dispatch.** Never silently dispatch another paid attempt
  after a failure; surface the evidence and let the user steer.
- **Respect the user's project instructions** (AGENTS.md and friends). Never
  install, overwrite, or replace them, and never claim discovery, capability,
  or submission readiness that has not actually been verified.
