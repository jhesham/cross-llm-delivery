# T11 dogfood evidence — in progress

2026-09-23. User explicitly authorized T11 via Kimi K3/OpenCode.
OpenCode 1.18.29 discovers exact model opencode/kimi-k3. One pinned production slice, no fallback.
Acceptance baseline commits: 63f9744 and 754cef9 (assertion-style correction); see T11-CONTRACT.md.

Trusted canary passed: provider-reported total 49,915 tokens (input 10,654, output 593,
cache read 38,656, cache write 0; total may include additional categories), cost USD 0.0526338.
Initial 25,000-token allowance was exceeded; this is observable and not a provider hard cap.
Before implementation the lead explicitly revised the production reservation to 1,000,000 tokens
and USD 3, with one worker/one attempt. Canary remains a separate retained run; report both totals.

Project-local evidence store: .cld/t11-dogfood/validation-evidence.json. Machine-wide evidence
failed strict preflight with unsupported status records and was left untouched. The local store
uses the same trusted validation gate; no existing verdict was silently promoted.
Canary ledger: .cld/t11-dogfood/ledger.json (run b04f68126fb14599ae8c1b58d1261903).
Production ledger: .cld/t11-dogfood/production-ledger.json (run 360c78e28aee4c0baf0420df77169875).
Controller and raw logs are retained locally under .cld/t11-dogfood, not committed.

Pre-dispatch checks exposed two lead-runner issues: pytest.fail is not accepted as an assertion
baseline, and pytest's combined quiet/verbose options suppressed reasons for long test IDs.
Corrected to assertions and explicit -vvv for the real pytest runner; return codes, tests and
candidate protections remain unchanged. The blocked preparations dispatched no production model
calls. Their artifacts are retained. Zero-attempt needs_repair was explicitly reset for preflight
retry with a ledger history explanation. No candidate implementation existed at those points.

First production call timed out after 600 seconds without edits. Normalized usage remains unknown.
Its retained completed-step events report at least 851,411 tokens and USD 0.8358738; these are
partial lower bounds, not complete totals. The retained OpenCode session is
ses_f34995e9effemlfozA7dMP95D5, in worktree
.cld/worktrees/T11-360c78e2-738bee799c1142abb8e40a1681a291bb.

After the user's proceed instruction, the same session/model/worktree was continued with a
1200-second deadline. Admission policy explicitly allows two attempts, cumulative reservations
2,000,000 tokens/USD 6 and per-attempt 1,000,000 tokens/USD 3. Unknown prior usage is charged its
full reservation for admission; it is not treated as zero. No automatic further retry is queued.
The continuation uses existing accounting, admission, ownership, containment and verified repair.
Continuation also timed out, after writing only the five allowed files. The original tests and
contract were unchanged. It reported passing focused checks, then announced an unrequested full
suite; the process did not finish before the deadline. No third call was dispatched. Its 14 completed
step records contain 1,728,036 tokens and USD 1.6303392, again lower bounds only. Most tokens were
cached context (continuation cache reads: 1,538,304). Do not sum reasoning/cache fields again.

Both production journal entries retain unknown totals. Combined canary plus observed production
lower bounds: **2,629,362 tokens and USD 2.5188468**. This is not a complete bill. The timeout parser
currently discards partial usage in normalized results; keep this provider improvement as a follow-up,
not a claim that partial observations are final. Token reservations were exceeded observationally.
The user-authorized model remained pinned throughout; provider permission policy was not changed.

## Independent verification and review

The lead ran the existing verified-repair gate after process ownership ended: immutable baseline
assertion failures, original acceptance tests green on the captured candidate, allowlist/protected
inputs checked, checked collection. Collected commit 48411494b2165861478126c748f6adefa0decefa.
Integration with explicit tests/test_t11_cli_contract.py passed at
38e386dfd2108bb70df90ed4ff31a82114258183. Journal transaction:
.cld/runs/360c78e28aee4c0baf0420df77169875/integration/35d76aaebbb142078bec186a905356d9.
The candidate was cherry-picked onto refactor/codex-support as 2457380.

Lead review fixes (af5250f, bb0907d) cover conflicting actions, canonical ledger paths, repository
and selected-slice attempt identity, usage-journal containment, type-preserving output truncation,
blocked/deferred/unbound state, failure diagnostics, unknown totals alongside known subtotals and
budget reservations, bounded progress capture, and complete pytest assertion summary reasons.
The lead-owned additional regressions are tests/test_t11_review.py (21 cases); original acceptance
remains tests/test_t11_cli_contract.py (31 cases). The initial review run demonstrated 10 failures
before fixes. Focused review/compatibility checks passed, including a real JSON step on a simulated
TTY with admission blocked and no prompt/provider dispatch.

Additional real transcript: both entrypoints ran status, usage and preview from a different cwd,
with empty PATH and no ANTHROPIC_API_KEY. All six responses parsed, matched their exit gates and
resolved ledger paths, and stayed 606-2048 bytes. No provider/Claude executable could be resolved.
Transcript retained locally at .cld/t11-dogfood/transcript.json. User-facing schema: docs/CLI.md.

## Final validation

Final code/test head: bb0907d. Windows/Ubuntu CI and generator smoke are pending:
https://github.com/jhesham/cross-llm-delivery/actions/runs/35824058308.
Earlier run 35823874324 was deliberately cancelled after final review fixes; it is not closing evidence.

Engine CLI, module entrypoint and legacy shim share behavior. --host is telemetry-only. JSON status
and usage remain local; details are selected by slice/attempt. Generated host overlays and actual
Codex/Claude discovery are T12-T14, packaging is T17; T11 does not claim those gates.

For future dogfood slices, keep the dispatch brief smaller and explicitly bounded, budget cached
context separately when interpreting tokens, and inspect partial artifacts at a timeout rather than
blindly retrying. The local controller's nested repair lock was avoided by invoking the verifier only
after the dispatcher exited. No acceptance safety code was weakened.
Lead usage unavailable; no Codex sub-agents. Stop after T11 and request token confirmation for T12.
