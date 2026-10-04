---
name: cross-llm-{{PROVIDER_NAME}}
description: >-
  Use when a large build has been decomposed into a multi-slice plan
  (contracts, acceptance tests, dependency DAG) so the {{PROVIDER_NAME}}
  headless executor implements each slice while Codex orchestrates and judges.
---
{{BANNER}}

# Cross-LLM Delivery -- Codex host, {{PROVIDER_NAME}} executor

**Codex is the lead.** You decompose the build into testable slices, fix the
contracts, author the acceptance tests, judge every result, and integrate
verified work. The **{{PROVIDER_NAME}} headless executor** does the bulk
implementation typing inside isolated
git worktrees. The vendored `cld` engine and driver under `scripts/` run
in place -- no package install and no source checkout are needed.
{{EXECUTOR_POLICY}}

For executor choices, run `python scripts/list_models.py --json` and follow
the picker section of `references/delivery-core.md`. Present exact returned
IDs and supported efforts; discovery does not authorize dispatch.

## When to use (and when not to)

- **Use it** on a large build expressed as a plan of independently testable
  slices with a dependency DAG, where executor tokens dwarf lead tokens.
- **Do not use it** for small one-file fixes; the per-dispatch overhead only
  pays off on large builds. Small work stays with Codex directly.

## Ground rules

- Respect the user's existing project instructions (AGENTS.md and friends).
  Never install, overwrite, or replace them.
- Preserve the user's exact executor/model/effort/tier selection. Present the
  shortlist only when no selection exists; a listing is not dispatch permission.
  Describe discovery only for the recorded host version and surface.
- Never claim the provider's cost is free. Check that billed dispatches are
  covered by the user's existing authorization; ask only if that is unclear.
- For gate-4 repairs, follow the user's authorization and the host's active
  approval policy. Never silently dispatch another paid attempt.
- `--step` and validation make paid network calls through the executor CLI.
  Check the active host permissions before dispatch. If network is disabled,
  use the host's supported authorization flow; do not bypass its restrictions.
  CLD blocks dispatch when `CODEX_SANDBOX_NETWORK_DISABLED=1` is set.

## Drive the build

Run these commands from the installed skill directory, using absolute plan and
target-repo paths. The driver is vendored in this bundle. Prefer `--json` for
machine-checkable gates and act on the JSON `gate_code`. On Windows a shell
wrapper (`pwsh -Command`) can report exit 1 for any non-zero driver exit, so
the JSON gate, not the shell's exit status, is authoritative.

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> --dry-run --json  # preview layers
python scripts/run_delivery.py <plan.md> --repo <dir> --step --workers 1 --executor <exact-spec> --validation-policy <deny|unmetered|allow> --budget-attempts <N> --json
python scripts/run_delivery.py --status --repo <dir> --json             # cheap digest
python scripts/run_delivery.py <plan.md> --repo <dir> --integrate --integration-tests <selector> --json
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
- `references/codex-workflow.md` -- the full Codex-led workflow: plan authoring,
  batch-stepping, the model picker, gates, and the repair loop.
- `references/provider-setup.md` -- install and verify the {{PROVIDER_NAME}} CLI.
- `references/provider.md` -- {{PROVIDER_NAME}} executor specifics: locked
  invocation, auth, cost, and platform notes.
