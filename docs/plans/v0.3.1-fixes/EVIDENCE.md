# v0.3.1 evidence

## Sitting 1 — lead (2026-09-30)

Commits `0aefd76`..`d4940fd` on `refactor/codex-support`: fixes 1 and 2 with
red-first tests under `tests/v031/`, plus red acceptance tests and
[cld-plan.md](cld-plan.md) for three CLD slices. Every slice test failed by
AssertionError only (the engine's red-baseline rule). Two existing tests that
encoded the fixed defects were updated deliberately (admission context, judge
snapshot injected-file case).

## Sitting 2 — CLD dogfood (2026-09-30)

- Builder: installed Claude-host skill `cross-llm-codex`, generated from
  `49b1a3f` (v0.3.0 + picker); target: this repository's source.
- Executor: `codex:gpt-6-luna@max+fast`, one worker,
  `CLD_DISPATCH_TIMEOUT=1200`, `--validation-policy allow`,
  `--budget-attempts 5`. Separate ledger `.cld/v031-ledger.json`.
- Run `833bad7420b84cc9bb5748945d7e7110`:

| Dispatch | Kind | Outcome |
|---|---|---|
| 1 | validation | verified (the installed engine still re-validates per session — fix 1) |
| 2 | CODEX_LAUNCHER | accepted, attempt 1 (`51b729e`) |
| 3 | FINAL_ERRORS | accepted, attempt 1 (`87486ea`) |
| 4 | GC | interrupted: the lead harness killed the driver at its 30-minute background limit |
| — | GC rerun | refused before dispatch: attempt budget 5/5 exhausted (the interrupted attempt counts) |

- Usage (provider-reported): input 4,138,836 tokens (of which 3,865,344 cache
  read), output 90,460; one attempt's usage unknown (interrupted); USD cost
  unknown (the Codex CLI reports none). No attempt overran a reservation.
- Integration: `--integrate --integration-tests 'tests/v031 -k "not test_gc"'`
  passed; verified commit `4ad3506`
  (`refs/cld/integration/833bad7420b84cc9bb5748945d7e7110/f5ec62cfa8764b3199420196fc61e52f`),
  fast-forwarded onto the working branch.
- GC: built by the lead without spend (user decision) against its 17 committed
  red tests — `4ceb585`.
- Lead review found one regression the slice-scoped acceptance could not see:
  Codex picker discovery raised before its process runner when no CLI resolves
  (CI) and always passed `env={}`. Fixed red-first in `8150b1f`.

### Lessons

- Run long dogfood steps detached from the lead's shell (the second run used
  `Start-Process`); a harness time limit is indistinguishable from a crash to
  the engine and still consumes an attempt.
- Slice acceptance tests should include the neighbouring existing tests of the
  files a slice touches, or the lead must run them before integration; the
  integration selector alone covered only `tests/v031`.
