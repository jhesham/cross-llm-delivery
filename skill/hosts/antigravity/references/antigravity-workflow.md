# Antigravity-led delivery workflow

Antigravity authors the contract and committed acceptance tests; the chosen
provider implements the slice. Call this bundle's driver by its absolute path,
`<skill-dir>/scripts/run_delivery.py`, in a single command with absolute plan/repo
paths; do not `cd` or `Set-Location` into the skill folder first, so each approval
shows one plain driver command. Headless `agy -p` cannot ask for approval and
refuses these commands; lead from an interactive Antigravity session.
No target-machine package install is needed.

Read [delivery-core.md](delivery-core.md) for JSON gates, spend/admission,
budgets and recovery. Read [authoring-plans.md](authoring-plans.md) before
authoring a plan: top-level slices, single-line briefs, protected tests and
explicit dependencies. Read [provider-setup.md](provider-setup.md) when checking
CLI/auth access and [provider.md](provider.md) for the selected adapter.

## Before the first step

- **Terminal sandbox.** Antigravity's terminal sandbox mounts the repository's
  `.git` read-only. `--step` and `--integrate` create worktrees, write
  `refs/cld/*` and commit verified candidates, so they fail inside it. Run them
  with the sandbox off for this workspace, or with the user's explicit grant to
  run them outside it. Preview (`--dry-run`) and `--status` only read.
- **Antigravity as executor.** Concurrent `agy -p` children share one local
  conversation store and the account's limits, so CLD runs Antigravity
  dispatches one at a time on this machine, whatever `--workers` says and
  even across separate builds; a waiting dispatch starts when the slot frees.
  Other executors in the same layer still run in parallel. Leading from the Antigravity app or IDE and
  dispatching `agy -p` is supported; when leading from the `agy` terminal UI
  itself, prefer another executor.
- **Codex skills in the same repo.** Codex also reads `.agents/skills`. Its
  skills are named `cross-llm-<provider>` and `cross-llm-delivery`; yours end in
  `-agy`. Use only the `-agy` skill.

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

## Preview, step and integrate

```bash
python "<skill-dir>/scripts/run_delivery.py" "<plan.md>" --repo "<dir>" --dry-run --json --host antigravity
python "<skill-dir>/scripts/run_delivery.py" "<plan.md>" --repo "<dir>" --step --workers 1 --executor <exact-spec> --validation-policy <deny|unmetered|allow> --budget-attempts <N> --json --host antigravity
python "<skill-dir>/scripts/run_delivery.py" --status --repo "<dir>" --json --host antigravity
python "<skill-dir>/scripts/run_delivery.py" "<plan.md>" --repo "<dir>" --integrate --integration-tests <committed-selector> --json --host antigravity
```

`--host antigravity` only labels telemetry; it never changes judging or
admission.

## Long-running steps

A `--step` usually takes minutes. The terminal tool waits about ten seconds,
then moves the command to a background task and wakes you with its full output
when it exits. Do not poll in a loop and do not start a second `--step` while
one runs. End the turn and wait for the completion message. If the user
interrupts before it arrives, check the task through the host's task tools or
run `--status --json`, which needs no provider call.

On Windows the PowerShell wrapper reports exit 1 for any non-zero exit. Read
`gate_code` from the JSON on stdout; it is authoritative.

## Gates and authorization

Pick the exact executor/model/effort/tier under the user's existing
authorization. A configured default or catalogue listing is not permission or
proof of access. Present available choices only when the user has not already
selected one. Do not silently substitute, retry paid work, raise budgets or
remove a requested tier. Every planned fallback rung still requires admission.

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
python "<skill-dir>/scripts/run_delivery.py" "<plan.md>" --repo "<dir>" --mark-repaired <slice-id> --json --host antigravity
python "<skill-dir>/scripts/run_delivery.py" "<plan.md>" --repo "<dir>" --integrate --integration-tests <committed-selector> --json --host antigravity
```

Repair verification/integration do not invoke inference. Explicit legacy
migration, changed-plan reconciliation and rollback limits are in the core
reference. Missing usage stays unknown; a Git worktree is not a sandbox.
Read [observability.md](observability.md) or [architecture.md](architecture.md)
only when inspecting telemetry or extending/debugging the engine.
