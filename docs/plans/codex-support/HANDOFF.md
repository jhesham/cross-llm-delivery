# Current handoff

Updated 2026-09-18. **T01 through T09, M1 and M2 complete. Paused before T10.**
Read [T09-CONTRACT.md](T09-CONTRACT.md) and [T09-EVIDENCE.md](T09-EVIDENCE.md).
Do not start T10 without explicit token-availability confirmation.

T09 code/test head `3caf863` is pushed to `public/refactor/codex-support` (initial implementation
`22b55dc`). Resolve the closing docs commit with
`git log -1 --format=%h --grep="^docs: close T09"` and verify its remote push.
CI: https://github.com/jhesham/cross-llm-delivery/actions/runs/35287083313
**Windows 685 passed; Ubuntu 682 passed, three Windows-only skips.** Both generator smoke
checks pass. Local Python 3.13: 681 passed, one live eval excluded, two existing warnings;
four later malformed-status regressions pass in the 38-test follow-up (685 distinct tests).

T09 unifies admission for defaults, tags, unknown IDs and frozen escalation rungs. Every selected
provider and writable location is preflighted. Validation defaults to deny; fresh context-matching
verified evidence permits reuse, otherwise explicit unmetered/allow policy is required. Forced
validation bypasses static/durable shortcuts. Atomic synchronized evidence fails closed on
corruption. Fresh retained probe repositories use the shared candidate/judge/process boundary.
Usage and artifacts survive failed/inconclusive probes. Normal pytest nonzero_exit classification
was corrected in validation and CLI so a failing assertion remains a valid baseline.
R09 and defect A07 are closed. Schema 2 and T06/T07 acceptance/integration gates remain.

Next is **T10 — usage and admission budgets**, estimate 8–12k lead tokens. Read phase 3,
usage.py, ledger.py, telemetry.py, status.py, orchestrator.py and the T09 contract. Add cumulative
attempt/validation/retry/escalation usage and provenance, explicit token/cost policies and locked
budget reservations; unknown usage/cost must remain unknown. M3 completes only after T10.

No live calls or sub-agents this slice; executor usage zero; lead token counters unavailable.
Kimi K3 via OpenCode remains the later dogfood choice; verify exact installed model ID before
first live dispatch and never silently substitute. If sub-agents are explicitly requested, use
`gpt-5.6-luna` at `max`. Generated plugins refresh in T12/T17. This is a refactor checkpoint,
not a release or merge. Commit/push each slice, then stop for the user's token checkpoint.
