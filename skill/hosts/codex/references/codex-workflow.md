# Codex-led delivery workflow

Codex authors the contract and committed acceptance tests; the chosen provider
implements the slice. Use this bundle's `scripts/run_delivery.py` from the skill
directory with absolute plan/repo paths, or invoke that driver by its absolute
path. No target-machine package install is needed.

Read [delivery-core.md](delivery-core.md) for JSON gates, spend/admission,
budgets and recovery. Read [authoring-plans.md](authoring-plans.md) before
authoring a plan: top-level slices, single-line briefs, protected tests and
explicit dependencies. Read [provider-setup.md](provider-setup.md) when checking
CLI/auth access and [provider.md](provider.md) for the selected adapter.

## Preview, step and integrate

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> --dry-run --json
python scripts/run_delivery.py <plan.md> --repo <dir> --step --workers 1 --executor <exact-spec> --validation-policy <deny|unmetered|allow> --budget-attempts <N> --json
python scripts/run_delivery.py --status --repo <dir> --json
python scripts/run_delivery.py <plan.md> --repo <dir> --integrate --integration-tests <committed-selector> --json
```

Pick the exact executor/model/effort/tier under the user's existing
authorization. A configured default or catalogue listing is not permission or
proof of access. Present available choices only when the user has not already
selected one. Codex has no static model catalog/default; accept an explicit
user-selected supported spec. The production admission gate is
`cld.admission.Admission`, not a hand-invoked legacy interactive helper.

A step runs a pending layer; validation/production/retries count against its
cumulative limits. Dispatching commands (`--step`, validation) need network
access through the executor CLI: inside your own `workspace-write` sandbox run
them with network-enabled or escalated permissions. CLD blocks before dispatch
when `CODEX_SANDBOX_NETWORK_DISABLED=1` is set, and a connection failure is a
final `network_unavailable` error (gate 5, no retry), not a model verdict. Do not silently substitute, retry paid work, raise budgets
or remove a requested tier. Prefer one worker for a bounded sitting; CLI's
default remains four. Every planned fallback rung still requires admission.

Inspect the returned gate: 0 work remains, 2 failure/defer, 3 integrated and
verified, 4 repair, 5 blocked input/state/prerequisite/policy, 6 integration
required. Accepted work must be integrated before dependent dispatch. Review
the final recorded ref/SHA before merging into the intended user branch.

## Resume and repair

Keep the same bound plan/repo/ledger. Read the response's artifact paths and
only the relevant attempt logs under `.cld/runs/<run-id>/`. Do not reset state
to clear a failure. Follow the user's existing authorization and host policy
when fixing retained source; keep protected tests/configuration unchanged.

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> --mark-repaired <slice-id> --json
python scripts/run_delivery.py <plan.md> --repo <dir> --integrate --integration-tests <committed-selector> --json
```

Repair verification/integration do not invoke inference. Explicit legacy
migration, changed-plan reconciliation and rollback limits are in the core
reference. Missing usage stays unknown; a Git worktree is not a sandbox.
Read [observability.md](observability.md) or [architecture.md](architecture.md)
only when inspecting telemetry or extending/debugging the engine.
