# Current handoff

Updated 2026-09-23. **T01 through T10 and M1–M3 complete. Paused before T11.**
Read [T10-CONTRACT.md](T10-CONTRACT.md) and [T10-EVIDENCE.md](T10-EVIDENCE.md).
Do not start T11 without explicit token-availability confirmation.

Code/test head `8f3c5db` (initial implementation `c73209d`) is pushed to
`public/refactor/codex-support`. Resolve the closing docs commit with
`git log -1 --format=%h --grep="^docs: close T10"` and verify its remote push.
CI: https://github.com/jhesham/cross-llm-delivery/actions/runs/35712951008
**Windows 709 passed; Ubuntu 706 passed, three Windows-only skips.** Both generator smoke
checks passed. Local full run: 699 passed plus an active-owner regression subsequently fixed
and verified separately; one live eval excluded, two existing warnings. Follow-up evidence
covers the ownership correction, later budget tests, status blocks and persistence failures.

T10 adds atomic per-dispatch journals and cumulative ledger usage by slice/model/validation.
Retries, escalation, failed calls and validation all count. Shared mutation locking reserves
capacity before parallel dispatch; policy persists across resume. New flags: --budget-attempts,
--budget-tokens, --budget-cost, --attempt-tokens, --attempt-cost and --unknown-usage deny|reserve.
These are admission allowances, not provider hard caps. Unknown cost/tokens remain unknown;
Antigravity has no verified usage source. CLI version identity uses T09 content fingerprints.
Status reads ledger aggregates, not the growing event log; crash reconciliation happens on resume.
Budget blocks preserve candidates and do not escalate. Sink shutdown closes and flushes owned resources.
R12/A06 closed; A09 recovery remains covered. Schema 2 remains in use.

Next: **T11 — host-neutral CLI interface**, estimate 8–14k lead tokens. Read phase 4,
architecture A07, run_delivery.py, status.py, summary.py and T07/T09/T10 contracts. Implement
versioned JSON and consistent inspect/next-action output without prompts or banners on stdout;
retain human output and gate semantics. T11 is not started.

No live model calls or sub-agents this slice; executor usage zero; lead counters unavailable.
Kimi K3 via OpenCode remains the later dogfood choice. Verify exact model ID/account and choose
explicit canary allowances before first live call; no substitution or stale-price assumption.
If explicitly requested, sub-agents use gpt-5.6-luna at max. Generated plugins refresh in T12/T17.
Commit/push each slice, then stop for the user's token checkpoint. No release or merge.
