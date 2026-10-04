---
name: cross-llm-codex
description: >-
  Run a multi-slice build with Claude Code as lead and the codex
  headless executor, using committed acceptance tests and isolated Git worktrees.
---
<!-- GENERATED from cross-llm-delivery (provider: codex, v0.4.2) - do not edit here; edit the monorepo source. -->

# Cross-LLM Delivery -- Claude Code lead

Claude authors the slice contracts and acceptance tests, reviews candidates,
and integrates verified commits. The codex CLI implements each
slice. The engine and driver are vendored under `scripts/`; no package install
or source checkout is needed on the target machine.
An exact model ID is required; this provider has no default model. Pass `--executor codex:<model-id>@<effort>` explicitly. For requested fast mode, use `codex:gpt-6-luna@max+fast`; do not silently drop the tier.

## Before dispatch

Use this for a build with independently testable slices and a dependency DAG.
For a small direct edit, the dispatch overhead may outweigh the benefit.

Read [delivery-core.md](references/delivery-core.md) when starting a build or
recovering one. Read [provider-setup.md](references/provider-setup.md) to check
CLI/authentication requirements, and [provider.md](references/provider.md) for
the selected executor's capabilities and limitations. Catalog entries and CLI
discovery do not prove headless access, price or current validation.

Keep the user's exact executor/model/effort/tier selection. Honor their
existing authorization for billed validation and implementation; ask only
when it is unclear. Do not silently substitute models, remove a tier, increase
budgets or retry paid work. Preserve existing project instructions.

For executor choices, run `python scripts/list_models.py --json` and follow
the picker section of `references/delivery-core.md`. Present exact returned
IDs and supported efforts; discovery does not authorize dispatch.

## Plan and run

Author and commit failing acceptance tests first. Keep tests and pytest
configuration outside the slice's writable allowlist. Plan values are one
line; split large work into top-level `## SLICE:` blocks with `deps`.
Read [authoring-plans.md](references/authoring-plans.md) for the supported schema.

Run from this installed skill directory with absolute plan/repository paths,
or use the absolute driver path from another cwd. Select the executor explicitly
for dispatch, and prefer `--json` to inspect the gate and evidence paths.

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> --dry-run --json
python scripts/run_delivery.py <plan.md> --repo <dir> --step --workers 1 --executor <exact-spec> --validation-policy <deny|unmetered|allow> --budget-attempts <N> --json
python scripts/run_delivery.py --status --repo <dir> --json
python scripts/run_delivery.py <plan.md> --repo <dir> --integrate --integration-tests <selector> --json
```

Choose the validation policy and attempt limit under the user's authorization:
validation and retries count as dispatches. Start with one worker and only the
production/validation allowance needed for this sitting. The public CLI default
is four workers, so pass `--workers 1` when limiting concurrency.

## Act on the result

- 0: the operation succeeded; work remains.
- 2: failure or dependency defer; inspect the named evidence.
- 3: all slices are integrated and verified.
- 4: lead repair required; retained work is available.
- 5: invalid input/state, prerequisite, lock or budget/admission block.
- 6: accepted work awaits integration before dependent dispatch.

Acceptance is the independently verified Git diff plus a real passing pytest
run with tests collected. An executor's prose or file events are not acceptance.
Integration runs an explicit committed suite against the recorded candidate in
an owned worktree; inspect its final ref/SHA before merging into the user's branch.

Resume using the same plan, repository and ledger. Status needs no provider call.
For repair, inspect the retained attempt, edit only authorized source files,
then run `--mark-repaired <slice-id>` with the original plan and integrate after
gate 6. Never reset/delete a ledger or worktree to make an error disappear.
Read the recovery section of [delivery-core.md](references/delivery-core.md)
for migration, changed plans, collection failure and rollback.

A Git worktree isolates candidate files; it is not a security sandbox. Tests
and executor processes inherit host capabilities. Provider permissions differ.
Denied permissions require inspecting the log/configuration, not blanket bypass.

Missing token/cost usage stays unknown. Token/dollar budgets admit calls using
explicit reservations; they cannot stop an already running provider at an exact
usage boundary. See the budget section of the core reference.

Read [observability.md](references/observability.md) only for event logs or
optional exports, and [architecture.md](references/architecture.md) for engine
extension/debugging. Do not load every reference for an ordinary step.
