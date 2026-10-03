# N05 — Codex configuration evidence, implemented through CLD

Implemented 2026-10-03 with exact **`codex:gpt-6-luna@max+fast`**.
Luna's accepted source: `0294ab6ed3a9973b69c58ef6d066f798cc9ecfb6`.
CLD integration: `8ab002981b7cc462d2bccde929024417d0e1a0fa`.
Final runtime after independent review: `8320281c39a6fab7789a8f83fbf79e2e6578413c`.

## Result and boundaries

`Provider.config_inputs(repository)` supplies local configuration paths. The
core discovers and merges them on every admission context calculation, alongside
existing inputs and explicit `--validation-config` files. Canonical paths are
deduplicated; existing file bytes and missing states key evidence. Codex's helper
includes the selected home, conservative repository/ancestor project candidates,
Unix system files, and Windows home/ProgramData managed candidates. Its TOML hook
collects custom provider `env_key` and `env_http_headers` variable names for value
hashing. Neither configuration bytes nor credential values enter evidence.

Edits, creation/deletion, changed callback selections and referenced variables
invalidate saved evidence and the already-admitted factory before spend. Invalid
or unreadable TOML fails closed without parser content in diagnostics. Relative
`CODEX_HOME`, including unexpanded `~`, is refused: probe and executor cwd differ.

This is deliberately conservative about inactive/trust-skipped project layers.
Profile files not selected by CLD's fixed invocation, rotating auth files,
keychains, remote configuration and command-backed auth remain outside automatic
discovery. Account switching requires revalidation and a stable non-secret
`--validation-context`; other inputs can be supplied explicitly. The provider's
setup notes document these limits and official configuration sources.

## Dogfood trace

1. Committed red tests and a five-file allowlist/contract. The initial suite had
   17 failures and two passes. Red tests use assertion failures so CLD can
   distinguish intended red acceptance from pytest setup/collection failures.
2. Waited for all four N04 full-suite/generator/packaging CI jobs to pass before
   relying on its frozen acceptance gate. Used the checkout's generated
   Codex-provider driver containing N04; no installed stale driver or bypass.
3. Original run `7dd62c25b2c34d53acab578903aceef5`, ledger `.cld/n05/ledger.json`:
   `deny` first blocked mismatched old evidence without spend. One authorized
   `allow` canary then passed independent frozen acceptance using Luna/max/fast.
4. Codex itself added a trust entry for that temporary probe to its user config.
   The explicit home-config fingerprint correctly blocked production. Removed
   only the session-created stanza after proving its removal reproduced the
   entire original validation fingerprint; `deny` then reused the saved evidence
   without another canary. No evidence record was relabeled or forged.
5. Production preflight caught the original `pytest.raises` missing-exception
   reports as pytest `Failed`, rather than assertion-red tests. No implementation
   model call occurred. Corrected only the test reporting format in `3dd7c8a`
   and used checked `--reconcile-plan`, preserving the old run and ledger backup.
6. Reconciled run `c38d1cf32c504a1582eb8fedbc5de9fc` used the remaining one-call
   budget under `deny`. Luna's first implementation changed only five allowed
   files and passed CLD acceptance (gate 6). No paid retry or substitution.
7. Provider-free `--integrate` independently tested the combined source and
   passed gate 3; the working branch fast-forwarded to that verified commit.
   Seven additional lead review cases found one tilde-expansion edge. Tightened
   the literal absolute-home check, then independently verified final source.

The first run reserved 1,200,000 cumulative tokens / 600,000 per call and allowed
two calls maximum. After reconciliation the production run allowed only one call
and 828,855 remaining cumulative tokens. Dispatch deadline: 900 seconds.
Reservations are admission estimates, not provider-enforced token ceilings.

## Measured usage

| Call | Input | Output | Cached input (subset) | Derived total |
|---|---:|---:|---:|---:|
| Validation | 359,992 | 11,153 | 323,840 | 371,145 |
| Implementation | 2,031,701 | 54,748 | 1,896,704 | 2,086,449 |
| **Total** | **2,391,693** | **65,901** | **2,220,544** | **2,457,594** |

Actual usage exceeded the cumulative admission allowance by **1,257,594** tokens;
CLD recorded the production overrun and one per-attempt overrun. No additional
provider call followed. Uncached input was 171,149 tokens; cached input is not
added again. USD cost and lead token usage are unavailable.

Both calls requested exact Luna/max/fast and completed without a surfaced tier
failure. Actual service-tier telemetry was absent, so actual priority routing
is not independently proven. No fallback to standard service was requested.

## Verification and artifacts

- CLD production acceptance: 19 tests passed against captured source.
- CLD integration: **77 passed**, 1,193 deselected, in 20.01 seconds; included
  admission, Codex adapter/wiring, OpenCode config-env and inline regressions.
- Final source with seven independent review cases: **84 passed in 11.09 s**;
  the tilde case failed before the lead's small correction, then passed.
- Wheel/sdist, isolated bundles and parity checks: **18 passed in 40.68 s**.
- All five providers for both hosts regenerated from runtime `8320281`;
  40 core files match across all ten bundles, and both Codex bundles include the
  exact helper bytes. Five tracked Claude packages pass freshness checks;
  portable Codex plugins/catalog were also regenerated.
- Both standalone Codex-provider bundles, from outside-checkout cwd and with
  offline CLI/validation seams, block edited home config at factory use and
  block reuse of saved evidence under `deny`. No inference during artifact checks.
- Pushed source/artifact commit `0d2eb0895d82a4c35c8bcf6fc7ff0d2dea6aa0b5`
  to public `refactor/codex-support`. Exact-source
  [CI run 37119733253](https://github.com/jhesham/cross-llm-delivery/actions/runs/37119733253)
  is queued at the checkpoint; its four cross-platform results remain pending.
  The follow-up checkpoint commit changes documentation only.

## Observed Windows friction and next sitting

Codex 0.159.3 shell execution worked under the approved unelevated sandbox.
The canary's own pytest initially hit parent-directory access errors and then
passed with `--pyargs`. Implementation self-tests encountered restricted-token
pytest temporary-directory access and spent many turns on that environment
problem. CLD's unrestricted independent acceptance/integration remained decisive.
For subsequent briefs, explicitly stop self-test retries on this known permission
issue and report it to the lead; do not weaken tests or broaden filesystem grants.
This was a major contributor to the high cumulative usage.

Global Codex config exactly matches its pre-dispatch digest; no persistent global
setting change, install or release publication was performed. Local raw provider
logs remain private under the two run directories; they are not published.

Final automatic inputs intentionally differ from the old canary context (notably
the additional missing Windows system-config candidate), so a read-only context
comparison found that prior evidence is now stale. N06 must check current exact-
spec evidence and permit a bounded fresh canary only if needed, rather than
changing the old record's context. Capture config digests before any call to
identify Codex's own temporary trust-entry churn safely.

N06–N08 remain pending through exact Luna/max/fast. Confirm CI and user token
availability at the slice checkpoint; never auto-dispatch another slice.
