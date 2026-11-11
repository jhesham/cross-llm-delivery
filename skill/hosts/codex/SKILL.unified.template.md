---
name: cross-llm-delivery
description: >-
  Run a multi-slice build with Codex as lead and a headless executor chosen
  per build (codex, claude, opencode, cursor or antigravity), using committed
  acceptance tests and isolated Git worktrees.
---
{{BANNER}}

# Cross-LLM Delivery -- Codex lead

**Codex is the lead.** You author the slice contracts and acceptance tests,
judge every result, and integrate verified commits. The executor CLI the user
chooses implements each slice: codex, claude, opencode, cursor or antigravity.
Only that executor's CLI needs to be installed. The engine and driver are
vendored under `scripts/`; no package install or source checkout is needed on
the target machine.
Every dispatch names its executor explicitly:
`--executor <provider>:<model-id>@<effort>`. Codex and Claude have no default
model; for requested Codex fast mode use `codex:gpt-6-luna@max+fast` and do not
silently drop the tier. Never pick a provider the user did not choose.

## Before dispatch

Use this for any change pinned by a failing acceptance test and an explicit
writable-file allowlist: a one-slice fix or a multi-slice plan with a dependency
DAG. Work directly when there is no testable contract yet (investigation,
exploratory design) or the test would cost more than a trivial edit; for
debugging, commit the failing reproduction test first, then let CLD implement.

Read [codex-workflow.md](references/codex-workflow.md) for the Codex-led
workflow and [delivery-core.md](references/delivery-core.md) when starting or
recovering a build. For the chosen executor, read
`references/providers/<provider>-setup.md` for CLI/authentication requirements
and `references/providers/<provider>.md` for its capabilities and limitations.
Catalog entries and CLI discovery do not prove headless access, price or
current validation.

Keep the user's exact executor/model/effort/tier selection. Honor their
existing authorization for billed validation and implementation; ask only
when it is unclear. Do not silently substitute models, remove a tier, increase
budgets or retry paid work. Preserve existing project instructions (AGENTS.md
and friends).

For executor choices, run `python scripts/list_models.py --json` and follow
the picker section of `references/delivery-core.md`. Present exact returned
IDs and supported efforts; discovery does not authorize dispatch.

## MCP tools

When `cld_*` tools are available, use them with absolute plan/repo paths.
Preview with `cld_preview`, then `cld_new_build` only when starting a new build.
Call `cld_step` with explicit `executor`, `validation_policy` and `budget_attempts`
under the user's authorization. Poll its `job_id` using `cld_job` with
`wait_seconds=45` until terminal. For finished jobs, act on `result.gate_code`;
then call `cld_integrate` with `integration_tests` and poll the same way.
Inspect `died`, `lost` or `exit_unconfirmed` jobs before further mutation.
To stop a job, call `cld_cancel`, then keep polling `cld_job` while its state is `running` or `cancelling`; any other state is final, and an unconfirmed or lost job blocks the repository until the processes it names are gone.
Use the CLI instructions below when tools are unavailable.

## Plan and run

Author and commit failing acceptance tests first. Keep tests and pytest
configuration outside the slice's writable allowlist. Read
[authoring-plans.md](references/authoring-plans.md) for the supported schema,
and [superpowers-to-cld.md](references/superpowers-to-cld.md) to convert a
superpowers plan into slices.

`--step` and validation make paid network calls through the executor CLI.
Check the active host permissions before dispatch; CLD blocks dispatch when
`CODEX_SANDBOX_NETWORK_DISABLED=1` is set. On Windows a shell wrapper can report
exit 1 for any non-zero driver exit, so the JSON `gate_code` is authoritative.

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> --dry-run --json --host codex
python scripts/run_delivery.py <plan.md> --repo <dir> --step --workers 1 --executor <exact-spec> --validation-policy <deny|unmetered|allow> --budget-attempts <N> --json --host codex
python scripts/run_delivery.py --status --repo <dir> --json --host codex
python scripts/run_delivery.py <plan.md> --repo <dir> --integrate --integration-tests <selector> --json --host codex
```

Exit codes: 0 ok, work remains; 2 failure/defer; 3 integrated and verified;
4 lead repair required; 5 invalid plan/state or missing prerequisite;
6 accepted work awaits integration.

Acceptance is the independently verified Git diff plus a real passing pytest
run with tests collected. An executor's prose or file events are not acceptance.
Resume using the same plan, repository and ledger. Never reset or delete a
ledger or worktree to make an error disappear. A Git worktree isolates
candidate files; it is not a security sandbox.

Read [observability.md](references/observability.md) only for event logs or
optional exports, and [architecture.md](references/architecture.md) for engine
extension/debugging. For data handling, privacy, security reporting and a
no-inference reviewer preview of this bundle, see [README.md](README.md).
