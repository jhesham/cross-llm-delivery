# T19A test-only crash driver

Implement only `tests/integration/t19_driver.py`. Lead acceptance is
`tests/integration/test_t19_rehearsal.py`; do not edit tests, engine or docs.
This is an offline subprocess harness, not a production feature. No provider,
network, global configuration or external repository operations.

Arguments: `REPO ACTION STOP`. Actions `dispatch-a`, `dispatch-b`, `integrate`,
`resume`, `hold`. Read the committed repo plan with the production parser. Bind
its complete plan/path/text so real CLI calls can resume the same ledger. Use
real Git, production judge/orchestrator/integration and real offline pytest
(`tests.integration.test_review_regressions.acceptance` is available).
Select only A/B respectively; zero retries, one worker. The deterministic
executor writes only the selected task's allowed file with `VALUE = 42\n`,
appending a JSON line `{slice, pid}` to `<repo>/.cld/t19-executions.jsonl` when
actually invoked. No simulation. Dependencies must use the engine's verified
integration base. `resume` dispatches A, integrates with test_integration.py,
dispatches B and integrates, and is idempotent. Normal stdout is exactly one
JSON object with `completed`, `deferred` for dispatch, or `integrated_sha` for
resume/integrate. Diagnostics go to stderr.

STOP means abrupt `os._exit(91)` at a precise durable production boundary:

- `dispatch`: after dispatch evidence and pinned snapshot are durable.
- `verified`: after candidate verification journal and ref are durable.
- `commit`: immediately after successful slice `git commit`, before collection.
- `ledger`: after A's DONE ledger has been durably saved, before cleanup.
- `merge`: after integration candidate/merge journal is durable, before suite.
- `test`: after integration passed journal/ref are durable, before ledger publish.

Use test-only wrappers of RecoverySession.save, Ledger.save, Git runner and
integration.atomic_write; call originals before checking the boundary. Never
add production fault hooks. Before exit write `<repo>/.cld/t19-crash.json` with
`phase`, `pid`, and `head` (current candidate/worktree commit, especially commit).
No exception unwinding/finally cleanup at crash. Keep all evidence/worktrees.

`hold` takes the actual ledger writer, binds complete plan, installs run-scoped
CLI telemetry and emits one sentinel. Write `.cld/t19-ready` after lock/bind,
then wait on stdin until release. This allows separate real CLI status/write
checks. Clear telemetry after releasing; output one JSON object.

Relevant APIs/examples: test_integration_lifecycle.py dispatch/merge,
test_build_state.py telemetry test, test_attempt_resume.py child_env;
engine/cld/recovery.py RecoverySession; engine/cld/integration.py publication.
Run only lead acceptance. Finish this one small file promptly.
