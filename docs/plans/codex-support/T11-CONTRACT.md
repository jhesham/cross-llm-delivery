# T11 — Host-neutral CLI contract

One executable slice: T11. User authorized Kimi K3 through OpenCode on 2026-09-23.
Exact discovery: OpenCode 1.18.29 lists opencode/kimi-k3. No substitution/fallback.

Move reusable handling into engine/cld/cli.py, add python -m cld, keep script entrypoint thin
and support existing arguments/import-based test injection. Default human behavior stays supported.
JSON mode disables prompts even on a TTY and writes exactly one schema-version-1 JSON object to
stdout; progress goes to stderr/artifacts. All CLI failures, including argparse, must be structured.
No Claude executable/key/API is required for deterministic commands or acceptance.

Required fields: schema_version=1, command, gate, gate_code, next_action, run_id, repository,
ledger, artifacts, usage, budget, accepted_refs, errors. Paths resolve exactly. Command preview
includes layers (list of ID lists), has gate_code 0 and no state mutation. Status/usage use local
persisted state only, including unknown usage as null. JSON status uses truthful gate exit codes:
pending=0/resume, failed=2/resume, needs_repair=4/repair, integration_required=6/integrate,
passed=3/complete, blocked=5/correct_input. Status success must not hide pending repair/integration.
Empty state is explicit; do not invent a run. Accepted refs retain exact commit/ref values.

Cover preview, step/whole-plan delivery, integrate, repair, migrate/reconcile/new-build, status and
usage. Preserve gate 0/2/3/4/5/6 meanings. Reject conflicting actions and JSON watch. Errors contain
bounded reason and useful next action, including auth/permission/admission errors. Default output
is bounded (<32 KiB in the acceptance fixture); never dump raw logs/history. --slice ID requests
bounded detail; --attempt ID selects a retained usage record with path containment and identity
checks. Include counts/truncation indications where collections are limited.

--host is optional provenance; telemetry.set_host stamps emitted events and is cleared after each
invocation. Host choice does not affect candidate judging, provider selection or admission policy.

Lead-owned tests/test_t11_cli_contract.py is the acceptance input. Existing tests are protected and
must remain green, including tests loading the old script with importlib then monkeypatching it.
Implementation can change only engine/cld/cli.py, engine/cld/__main__.py, engine/cld/cli_response.py,
engine/cld/telemetry.py and skill/scripts/run_delivery.py. No provider, accounting, acceptance,
Git-safety, tests, dependency, generated-bundle or publishing changes. Review will check behavior
beyond the explicit acceptance fixture. Generated bundles remain T12/T17 work.

Validation canary: one worker, one model, one attempt, 25,000-token/$1 admission reservation.
These are admission allowances, not provider hard limits or price estimates. Observe returned usage
before choosing the single production-attempt allowance. No automatic retry or escalation. Keep
canary/production accounting and recovery artifacts under .cld; report measured usage and unknown
cost honestly. Lead tokens estimated 8–14k; actual counters unavailable. Stop after this slice.
