---
name: cross-llm-{{PROVIDER_NAME}}-agy
description: >-
  For Antigravity leads only. Use when a large build has been decomposed into
  a multi-slice plan (contracts, acceptance tests, dependency DAG) so the
  {{PROVIDER_NAME}} headless executor implements each slice while Antigravity
  orchestrates and judges.
---
{{BANNER}}

# Cross-LLM Delivery -- Antigravity host, {{PROVIDER_NAME}} executor

This skill is for Antigravity. A Codex lead uses `cross-llm-{{PROVIDER_NAME}}`
instead; if you are not Antigravity, stop and use the skill for your host.

**Antigravity is the lead.** You decompose the build into testable slices, fix
the contracts, author the acceptance tests, judge every result, and integrate
verified work. The **{{PROVIDER_NAME}} headless executor** does the bulk
implementation typing inside isolated git worktrees. The vendored `cld` engine
and driver under `scripts/` run in place -- no package install and no source
checkout are needed.
{{EXECUTOR_POLICY}}

For executor choices, run `python scripts/list_models.py --json` and follow
the picker section of `references/delivery-core.md`. Present exact returned
IDs and supported efforts; discovery does not authorize dispatch.

## When to use (and when not to)

- **Use it** for any change pinned by a failing acceptance test and an explicit
  writable-file allowlist: a one-slice fix or a multi-slice plan with a
  dependency DAG. CLD adds independent acceptance, a recorded ledger, and moves
  implementation tokens off the lead.
- **Work directly instead** when there is no testable contract yet (root-cause
  investigation, exploratory design, visual or live-system judgement) or for a
  trivial edit where the test would cost more than the change. For debugging,
  find the cause and commit the failing reproduction test first; then CLD can
  implement the fix.
- **Planned with superpowers?** Convert the plan into slices with
  [superpowers-to-cld.md](references/superpowers-to-cld.md).

## Ground rules

- Respect the user's existing project instructions (AGENTS.md, GEMINI.md and
  friends). Never install, overwrite, or replace them.
- Preserve the user's exact executor/model/effort/tier selection. Present the
  shortlist only when no selection exists; a listing is not dispatch permission.
- Never claim the provider's cost is free. Check that billed dispatches are
  covered by the user's existing authorization; ask only if that is unclear.
- For gate-4 repairs, follow the user's authorization and the host's active
  approval policy. Never silently dispatch another paid attempt.
- `--step` and `--integrate` create Git worktrees, refs and commits. They need
  Git write access, so they cannot run inside Antigravity's terminal sandbox
  (it mounts `.git` read-only). Ask the user to allow these commands outside the
  sandbox; do not work around the restriction.
- CLD runs Antigravity executor dispatches one at a time, whatever the worker
  count: parallel `agy -p` children share one local state store and account
  limits. Other executors in the same layer still run in parallel.

## Drive the build

Call the driver by its absolute path in a single command, where `<skill-dir>` is
this skill's installed folder, with absolute plan and target-repo paths (keep the
quotes; paths can contain spaces), and pass
`--host antigravity` so telemetry records the lead.
Do not change folder first (`cd` or `Set-Location`), so each approval shows
one plain driver command. Headless `agy -p` cannot ask for approval and refuses
these commands, so lead from an interactive Antigravity session.
`--step` usually runs longer than the terminal tool's wait: it moves to the
background and you are woken when it finishes. Do not poll in a loop; end the
turn and wait, or check `--status` if the user interrupts. On Windows the shell
wrapper can report exit 1 for any non-zero driver exit, so the JSON
`gate_code`, not the shell's exit status, is authoritative.

```bash
python "<skill-dir>/scripts/run_delivery.py" "<plan.md>" --repo "<dir>" --dry-run --json --host antigravity
python "<skill-dir>/scripts/run_delivery.py" "<plan.md>" --repo "<dir>" --step --workers 1 --executor <exact-spec> --validation-policy <deny|unmetered|allow> --budget-attempts <N> --json --host antigravity
python "<skill-dir>/scripts/run_delivery.py" --status --repo "<dir>" --json --host antigravity
python "<skill-dir>/scripts/run_delivery.py" "<plan.md>" --repo "<dir>" --integrate --integration-tests <selector> --json --host antigravity
```

Choose the validation policy and cumulative attempt limit under the user's
authorization. Validation and retries count as dispatches. Prefer one worker
for a bounded sitting; the CLI default is four.

Exit codes: 0 ok, work remains; 2 failure/defer; 3 integrated and verified;
4 lead repair required; 5 invalid plan/state or missing prerequisite;
6 accepted work awaits integration.

## References

- `references/delivery-core.md` -- the shared, host-neutral gate (exit-code)
  contract and authorization rules; identical in every host bundle.
- `references/antigravity-workflow.md` -- the full Antigravity-led workflow:
  long-running steps, the sandbox and worker rules, gates, and the repair loop.
- `references/provider-setup.md` -- install and verify the {{PROVIDER_NAME}} CLI.
- `references/provider.md` -- {{PROVIDER_NAME}} executor specifics: locked
  invocation, auth, cost, and platform notes.
- [README.md](README.md) -- data handling, privacy, security reporting and a
  no-inference reviewer preview of this bundle.
