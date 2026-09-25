# T16 Codex executor — implementation and proof

T16 registers a fourth, opt-in executor. It requires an exact model ID and has no
static catalog or guessed default. `CodexExecutor` uses the T15 contract, probes
installed CLI capabilities, sends the slice over stdin to a fresh
`codex exec --json --ephemeral` session with `workspace-write` sandbox and an
explicit worktree root, then captures the real Git diff only after valid JSONL
completion. CLD's independent allowed-files, baseline-red, candidate-green and
integration checks remain the acceptance authority. The ambient
`CLD_EXECUTOR_DEPTH` guard blocks recursive dispatch of *any* provider.

## Dogfood implementation

The exact `opencode:opencode/kimi-k3` model implemented the bounded adapter
subtask from a committed red nine-case baseline. CLD run
`1fed09d7d5964c019b679cb2a588a1c2` accepted its one-file candidate
`7354309d760ce8cfadec277138fa0dbd8db8afc2` and independently integrated
merge `203642dfa763aa28b3db5d3edb9b9038366d9877`. Validation and one
production attempt reported 401,147 tokens (56,288 input, 4,778 output,
328,576 cached input) and USD 0.5116818. Windows worktree cleanup reported a
permission lock after candidate acceptance; the ignored worktree remains for
diagnosis. The lead fixed a nonzero CLI-probe edge case and added provider
registration, generation, packaging, documentation, and tests. No Kimi model
substitution occurred.

## Live Windows canary and recovery

On Windows PowerShell with Python 3.13.13, installed `codex-cli 0.155.1`, and
the Codex host driver, the user-selected exact model was
`codex:gpt-6-luna@max`. A read-only refreshed `codex debug models` listing
showed that model and `max` reasoning effort; actual access was then proven by
the canary. The disposable Git repository was
`.cld/t16-live/repo with spaces`, with a committed failing `test_value.py` and
an allowlist containing only `value.py`. The one-slice dry run reported
`pending`, zero attempts, and layer `[["A"]]`.

Run `ab854858e0a34fadb131953d618e8594` passed live validation, then
deferred production because the validation's observed 386,212 tokens exceeded
the initial 400,000-token total budget and 200,000-token per-attempt
reservation. A first resume with only the total increased was correctly
blocked on the recorded per-attempt overrun; neither deferral made another
model call. Raising the allowance to 900,000 total / 400,000 per attempt
resumed the **same ledger** without revalidation. One production attempt
changed only `value.py` from `VALUE = 1` to `VALUE = 2`; the baseline test was
red and the candidate test green. CLD accepted commit
`2c29af3c3934b7d5f0ac55015cc3bb2dc24f072e` and stopped at gate 6,
`integration_required`. A fresh, provider-free `--integrate --integration-tests
test_value.py` process passed gate 3 and recorded integration commit
`9723575cc844b310cc3cda81e555f47409db1f75`. The final admitted resume
used:

```powershell
python skill/scripts/run_delivery.py .cld/t16-live/plan.md --repo '.cld/t16-live/repo with spaces' --ledger .cld/t16-live/ledger.json --step --executor codex:gpt-6-luna@max --validation-policy allow --budget-attempts 2 --budget-tokens 900000 --attempt-tokens 400000 --unknown-usage reserve --workers 1 --json --host codex
python skill/scripts/run_delivery.py .cld/t16-live/plan.md --repo '.cld/t16-live/repo with spaces' --ledger .cld/t16-live/ledger.json --integrate --integration-tests test_value.py --json --host codex
```

This proves a controlled
admission stop/resume and the acceptance-to-integration restart; a live
mid-process kill/resume was **not** exercised.

| Live call | Input | Output | Cached input (subset of input) | Derived total |
|---|---:|---:|---:|---:|
| Validation | 380,303 | 5,909 | 345,344 | 386,212 |
| Implementation | 548,052 | 10,697 | 496,640 | 558,749 |
| **Total** | **928,355** | **16,606** | **841,984** | **944,961** |

Raw JSONL `turn.completed` also reported reasoning-output tokens, which are a
subset of output and were not added again. CLD retained raw usage and derived
total from input plus output. The CLI supplied no USD charge, so **cost is
unknown**; no subscription entitlement or price is inferred. Actual total
exceeded the final 900,000-token admission allowance by 44,961 tokens,
recorded by CLD as an overrun. Reservations are admission estimates, not
provider hard caps. No additional live call was made to conceal or reconcile
that overrun.

## Offline coverage and scope

The T16 fake-process tests cover long Unicode prompts, paths with spaces,
auth stderr, malformed/incomplete JSONL, timeout and cancellation results,
unsupported/nonzero CLI probes, usage fields, real Git diff capture, and
recursive-dispatch blocking. The provider wiring tests check exact-model
selection, absence of a Codex default, unknown cost, both isolated host
bundles, and an ambient recursion guard. Wheel/sdist resources, the generated
Claude plugin, four-entry Codex catalog, and tracked-plugin freshness are
covered by the extended T17 tests and CI smoke. The source/test commit is
`e64d12f`; its [four-job Windows/Ubuntu Python 3.11/3.14 CI run](https://github.com/jhesham/cross-llm-delivery/actions/runs/36156180253)
passed the full offline suite, both host generators, tracked plugin freshness,
and Codex plugin/catalog smoke in every job. The local full suite exposed one
obsolete three-provider assertion; after correcting it, the 45-case focused
provider and contract group passed. The four-job CI is the closing offline gate.

This is one verified Windows live canary, not evidence of live Ubuntu/macOS
Codex dispatch. Ubuntu CLI flag inspection and a live process-level
interruption remain unverified. T19 should include the fourth provider in its
release/recovery rehearsal without treating this canary as cross-platform
proof. Lead-token counters were unavailable.
