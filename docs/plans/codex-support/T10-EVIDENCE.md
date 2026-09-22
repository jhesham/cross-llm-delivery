# T10 — Verification evidence

Implemented 2026-09-22; closed 2026-09-23. **T10/M3 complete; R12/A06 closed.**
See [contract](T10-CONTRACT.md).

Focused suites: 98 passed (accounting, CLI, usage, T09, ledger); 70 passed
(accounting, telemetry/status, parsers, admission); 113 passed (real budget/retry/validation
boundaries, accounting, status, telemetry and all executor contracts). Runs overlap.
An existing active-owner regression exposed eager accounting initialization; initialization now
occurs after ownership acquisition, and its targeted follow-up passes (16 tests).
A new recovery-patch assertion initially searched the wrong directory depth; corrected to inspect
actual patch content. All three new real-Git budget scenarios then passed.

Local full suite: 699 passed, one active-owner regression failed (then fixed and verified
in the 16-test follow-up), one live evaluation excluded, two existing deprecation warnings;
784.20s. Later focused runs: 75 passed, 80 passed after preserving blocked status in the ledger,
and 21 passed including malformed usage persistence. These runs overlap.
Final code/test head `8f3c5db` (initial implementation `c73209d`) is pushed.
CI: https://github.com/jhesham/cross-llm-delivery/actions/runs/35712951008
Ubuntu CI passed: 706 tests, three Windows-only skips, generator smoke passed.
Windows CI passed: 709 tests, no skips, generator smoke passed.
The earlier run was superseded/cancelled. Final rendering follow-up: six passed. Local ignored logs:
.cld/t10-verification. No live provider calls or sub-agents. Executor usage zero; lead counters
unavailable. T11 remains unstarted and requires the next token-availability checkpoint.

Regression locations: tests/test_t10_accounting.py; tests/integration/test_usage_budgets.py;
T09 CLI blocked-status regression in tests/test_t09_admission.py. Existing candidate/recovery,
provider, status and telemetry contracts remain in the full offline suite. The README now removes
its historical assumption that flat-rate usage should display zero cost.

Closing documentation commit subject: `docs: close T10` (resolve with
`git log -1 --format=%h --grep="^docs: close T10"`). Both implementation commits and the
closing documentation are pushed to public/refactor/codex-support. No merge or release.

Remaining limitations are explicit in the contract: reservations cannot kill a provider at a
billing boundary; unreported usage stays unknown; legacy pre-T10 totals are incomplete; crashed
summaries reconcile on resume; generated plugins refresh in T12/T17. No live canary budget was
chosen without verifying Kimi K3's exact installed model/account. T11 is the next checkpoint and requires explicit token-availability confirmation; it is not
part of this completed slice.
