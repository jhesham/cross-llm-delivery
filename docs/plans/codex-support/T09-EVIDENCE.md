# T09 — Verification evidence

2026-09-18. **T09 complete. R09 and defect A07 closed.**
See [contract](T09-CONTRACT.md).

Focused checks: 70 passed (validation/resolution/evidence/preflight/T07), 47 passed
(admission, real-Git validation boundary, telemetry and repair), and 74 passed
(latest admission/CLI/resolution/provider/Git preflight). These runs overlap.
Final evidence/admission follow-up: 38 passed, including four malformed-status cases.
Local logs are ignored under .cld/t09-verification. Ubuntu CI on `3caf863`: 682 passed,
three Windows-only skips; generator smoke passed. Local Python 3.13 full run: 681 passed, one live evaluation deselected, two existing
DeprecationWarnings, 990.18s. Four subsequently added malformed-status cases passed in
the follow-up, covering 685 distinct passing tests locally. Windows CI on `3caf863`: 685 passed, no skips. Both CI platforms passed generator smoke.
CI: https://github.com/jhesham/cross-llm-delivery/actions/runs/35287083313
Implementation commits: `22b55dc`, `3caf863`, pushed to public/refactor/codex-support. No external model calls or sub-agents.
Lead token counters unavailable; executor token usage zero.

T09 also corrects ordinary pytest nonzero_exit classification from T08: an assertion-failing
baseline must remain valid input to candidate preflight, not be rejected as infrastructure failure.

The initial CI on `22b55dc` was cancelled after the malformed-status follow-up superseded it.
Final CI above passed on both platforms. Closing documentation commit subject: `docs: close T09`
(use `git log -1 --format=%h --grep="^docs: close T09"`). No merge or release.
Next slice remains T10, requiring the user's token-availability confirmation.

## Regression evidence and limits

- tests/test_t09_admission.py: policy/expiry/force/context/default/tag/escalation/unknown-model
  checks, zero-probe preflight blocks, CLI gate 5 and validation-before-production ordering.
- tests/integration/test_validation_boundary.py: real Git and pytest, protected/committed test
  tampering, auth failure, cancellation, retained usage/patches and fresh failing probe baselines.
- tests/test_evidence.py plus admission tests: corrupt/unreadable records fail closed, atomic
  replacement failure preserves old bytes, two real processes retain all 16 distinct writes.
- Existing provider, candidate, recovery and integration contracts pass in the full suites.

Compatibility limits are in T09-CONTRACT.md. External provider/account identity beyond tracked
files requires explicit context/config flags. Catalog cost labels are not billing guarantees.
Per-probe usage is retained; cumulative accounting/budget reservation remains T10. Generated
plugin copies remain T12/T17, and full versioned CLI JSON remains T11. No live-provider claim
is made by this offline checkpoint. Kimi K3 model identity remains unverified.
