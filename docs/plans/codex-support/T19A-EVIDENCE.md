# T19A — fresh-process state and interruption rehearsal

Local acceptance is complete. Closing source must pass four-job CI before delivery signoff. Parent T19 remains open until T19B: host/provider evidence, rollback rehearsal and size measurements. This child makes no new host-discovery or live-provider platform claim.

## Acceptance and review

Baseline `ac7320a` committed the one-file brief and lead acceptance before dispatch: eight expected failures, one passing corruption check. Disposable real Git repositories have spaces, a dirty original checkout and historical traces. The test-only driver abruptly exits with code 91 after dispatch, verification, slice commit, DONE ledger save, integration merge and passed integration-test evidence. Every retry/resume uses a fresh interpreter.

The gate requires B's dependency to be integrated before dispatch, accepted commits reachable from the final integration SHA, one accepted ref per slice, idempotent repeated resume, and preserved original HEAD/files/traces. Migration uses fresh real CLI processes for byte-exact backup, verified unmerged acceptance, partially failed/missing-ref state, changed-plan reconciliation and corruption. Separate processes exercise exhausted cumulative budgets, ledger lock exclusion, event isolation and CLI status reads during repeated atomic ledger writes.

Lead review corrected two acceptance assumptions, without production changes:
- Unaccepted dispatch/verified/commit crashes retry from a fresh base and preserve the old worktree/ref/commit. Redispatch is valid there. Ledger/merge/passed-test crashes recover without another A invocation.
- State-only CLI preparation emits no dispatch telemetry. The separate-build test opens a second run-scoped sink in a fresh process and verifies that it cannot alter the first run's events.

## Dogfood and usage

Exact executor `opencode:opencode/kimi-k3`, installed OpenCode 1.18.29; the exact model was listed before dispatch. Run `ce0dceafa02641c9b76690ac57121867`, ledger `.cld/t19a/ledger.json`. Only `tests/integration/t19_driver.py` was delegated. Recorded valid admission was reused; no new validation probe. One worker, at most two cumulative dispatches, 300,000-token admission budget, 150,000 reservation per call, unknown usage denied.

The single admitted production call timed out after **600.005195 seconds**, with no file changes or accepted candidate. Unknown prior total blocked another invocation before launch. No substitute or extra live call. The lead completed the driver directly; the dogfood ledger remains blocked and was not rewritten to claim acceptance.

CLD's interrupted call has unknown full usage/cost. A **read-only local** export of OpenCode session `ses_f181bd373ffeqd1afehrZnbAyK` recovered 16 completed assistant messages: **825,553 tokens** (139,232 input, 3,386 output, 15,485 reasoning, 667,450 cache-read), **USD 0.900996**. These are lower bounds; the unfinished response is excluded. Export did not call a provider or replace ledger accounting. The lower bound exceeds the 300k admission budget within one in-flight call; reservations cannot enforce a provider token cap. Cached validation added no new probe spend.

Retained ignored artifacts:
- `.cld/worktrees/T19A-ce0dceaf-d6abf5a1ca224c28ad4258e5be60ebf5`
- `.cld/runs/ce0dceafa02641c9b76690ac57121867/T19A/d6abf5a1ca224c28ad4258e5be60ebf5/attempt-1/processes/cld-process-2skhkdtn/result.json`
- `.cld/t19a/dispatch.json`, `status-during-dispatch.json`, `opencode-session.json`, `opencode-usage-lower-bound.json`

Lead usage is unavailable. The 7–11k estimate was a planning allowance, not measured spend; restart reads, review corrections and direct fallback increased overhead. T19B remains estimated at 4–7k plus contingency. Review future delegation scope/defaults after two no-candidate timeouts (T18 and T19A), rather than repeating this driver dispatch for another live result.

## Verification

- [x] Committed red acceptance before dispatch.
- [x] Eight fresh-process crash/migration/corruption cases passed locally.
- [x] Corrected lock/event test and two budget/active-writer cases passed locally.
- [x] Existing state/recovery/integration/concurrency/process/accounting regressions: **78 passed**, 408.13 seconds, `.cld/t19a/existing-checks.txt`.
- Closing source requires the **full offline suite in all four** Windows/Ubuntu Python 3.11/3.14 CI jobs, plus both-host generator/plugin/freshness checks. Save exact-SHA job metadata at `.cld/t19a/ci-final-jobs.json` before signoff. Query with `gh run list --repo jhesham/cross-llm-delivery --workflow CI --branch refactor/codex-support --commit <SHA>`.

There are **11 unique new passing local cases**. The first focused run reached eight passing state cases before stopping at the telemetry assumption; the corrected three-case subset passed. CI must run the final collection together. This child changes tests/tracking only: no production engine/provider/generated source changed and no production defect was demonstrated.

```text
python -m pytest tests/integration/test_t19_rehearsal.py tests/integration/test_t19_budget_resume.py -o addopts= -q
python -m pytest tests/integration/test_t19_rehearsal.py::test_status_under_writer_and_separate_cli_build_isolation tests/integration/test_t19_budget_resume.py -o addopts= -q
```

T18 prerequisite was verified live: `593174a` passed all four jobs and artifact checks in [CI run 36397220485](https://github.com/jhesham/cross-llm-delivery/actions/runs/36397220485).
