# Current handoff

Updated 2026-09-22. T01–T09 complete; **T10 verification in progress**. User authorized T10.
Read T10-CONTRACT.md and T10-EVIDENCE.md. Full offline local suite and Windows/Ubuntu CI
must finish before closing T10/M3. Focused accounting/budget/provider tests pass.

Implemented per-attempt durable journal, ledger aggregates, shared-lock reservations,
validation/retry/escalation budgets, explicit unknown usage policy, bounded status summary reads
and sink cleanup. Generated bundles remain T12/T17. No live calls/sub-agents; executor usage zero,
lead counters unavailable. Kimi K3 via OpenCode remains the later dogfood choice; verify exact
model ID/account before any live call, no substitution. No live canary budget chosen from stale prices.

Finish verification, update T10/M3 checklists and R12/A06, commit/push public/refactor/codex-support,
then pause before T11 for token confirmation. No release/merge. T11 is the host-neutral CLI interface.
