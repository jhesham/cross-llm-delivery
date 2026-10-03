# F01 — pytest process classification contract

Fix the diagnostic false rejection in both production pytest adapters without
weakening provider diagnostics or the frozen-candidate gate.

- Add an explicit keyword-only `classify_output=True` option to `run_process`.
  Default behavior stays unchanged: executor output still uses `exit_error` and
  authentic provider authentication failures remain final, without retry.
- With `classify_output=False`, completed processes get only return-code-based
  classification (zero -> no error, nonzero -> nonzero_exit). Do not reinterpret
  stdout/stderr as provider diagnostics. Retained result.json must reflect the
  selected policy. Never overwrite existing timeout, cancellation, missing binary,
  access or launch errors. Preserve process-tree cleanup, partial logs, environment,
  deadlines, argv/stdin transport, injected runners and exception behavior.
- `cli.pytest_test_runner` and `validate._pytest` must explicitly pass False.
  Preserve return codes and lifecycle errors; only ordinary nonzero_exit is
  normalized for TestRun. Keep collection/configuration/no-tests exits and missing
  return codes fail-closed through the existing candidate/judge boundary.
- Do not globally suppress authentication heuristics, discard arbitrary errors,
  parse pytest item names, accept output prose as success, or change CandidateVerifier.
- Allowed files: engine/cld/process.py, engine/cld/cli.py, engine/cld/validate.py.
  No tests/generated files, Git mutations, installs, global settings, other model
  calls, providers, selectors, saved evidence or unrelated refactoring.

Run only tests/test_f01_pytest_diagnostics.py with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
Report Windows restricted-token pytest/temp access errors promptly and stop retries.
Do not change temp roots, broaden grants or weaken tests; the lead independently
verifies captured source. The lead also reproduces the historical broad N06
baseline and verifies packaging/artifacts after checked integration.
