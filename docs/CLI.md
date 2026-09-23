# Host-neutral delivery CLI

The source entrypoint is `python skill/scripts/run_delivery.py`; an installed engine also supports
`python -m cld`. Both use `cld.cli`. The legacy script remains importable for existing callers.
No Claude executable or API key is needed for inspection, preview, or deterministic judging.
Provider authentication and model admission still apply when dispatching work.

## Machine commands

Append `--json` for one schema-version-1 JSON object on stdout. Progress is on stderr and in run
artifacts. JSON mode never prompts, including on a TTY. Use the exit code and `gate`, not text scraping.
`--host codex` or `--host claude-code` is optional telemetry provenance only; it does not select a
provider, authorize a model, or change acceptance. It is cleared after each invocation.

```text
python -m cld plan.md --repo PROJECT --dry-run --json
python -m cld plan.md --repo PROJECT --step --executor opencode:EXACT_MODEL_ID --json --host codex
python -m cld plan.md --repo PROJECT --integrate --integration-tests tests/test_build.py --json
python -m cld --repo PROJECT --status --json
python -m cld --repo PROJECT --usage --json
python -m cld --repo PROJECT --status --slice A --json
python -m cld --repo PROJECT --usage --slice A --attempt ATTEMPT_ID --json
python -m cld plan.md --repo PROJECT --mark-repaired A --json
python -m cld plan.md --repo PROJECT --reconcile-plan --json
```

`EXACT_MODEL_ID` is a placeholder, not an admitted model. The validation policy still defaults to
`deny`: establish trusted validation evidence or explicitly authorize the applicable validation flow.
Choose one action. Whole-plan delivery omits `--step`; a multi-layer plan needs an explicit integration
suite. `--new-build` and `--migrate-ledger` are also structured state actions. Repair verifies retained
work and acceptance before collecting it; it does not toggle a slice to done. JSON watch is rejected.

## Schema 1

Every response includes:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer 1 |
| `command` | preview, step, plan, integrate, repair, reconcile, migrate, new-build, status, usage, or help |
| `gate`, `gate_code`, `next_action` | Outcome and action from the table below |
| `run_id` | Persisted build identity, or null if no run is bound |
| `repository`, `ledger` | Resolved absolute paths; explicit relative ledger paths use invocation cwd |
| `artifacts` | Run directory and event path, or null entries if unavailable |
| `usage` | Persisted totals; unknown values are null, with available known subtotals/unknown counts |
| `budget` | Admission policy plus available reservations, overrun counts and block reason |
| `accepted_refs` | List of exact slice, ref and commit records |
| `errors` | List of bounded reasons and next actions |

| Exit | Gate | Next action |
| --- | --- | --- |
| 0 | pending | resume |
| 2 | failed | resume |
| 3 | passed | complete |
| 4 | needs_repair | repair |
| 5 | blocked | correct_input |
| 6 | integration_required | integrate |

Status reports the persisted build gate, so a successful status read can return 2/4/5/6.
`--usage` reports local accounting with exit 0; it does not query provider accounts or assert build
completion. Preview is read-only, returns execution `layers`, and creates no ledger. An empty status
has no invented run ID; unbound legacy entries need migration/reconciliation. Help is exit 0.

Default output is below 32 KiB. Limited collections retain their JSON types and expose truncation/count
metadata when trimmed. A host must not interpret an omitted collection tail as absent work. Use
`--slice` for bounded slice state and recovery/worktree paths, and `--attempt` for a retained accounting
record. Attempt IDs are checked for containment and must match a selected slice. History and raw logs
are not dumped in normal responses; inspect the artifact paths when deeper diagnostics are needed.

Accounting reservations are admission allowances, not provider-enforced in-flight limits. Unknown
completed usage remains unknown even when a known subtotal is available. Status is an inspection
snapshot, not a replacement for the verified integration gate before dependent work.

Host-specific skill generation/discovery is tracked separately in T12-T14. This CLI interface alone
does not assert that a generated skill has been installed or discovered by either host.
