# F01 — pytest diagnostic policy

Use the exact executor; the lead owns tests, historical repro, review and artifacts.

## SLICE: F01
brief: Read docs/plans/v0.4.0-review-fixes/F01-CLD-CONTRACT.md and tests/test_f01_pytest_diagnostics.py. Add default-on keyword-only classify_output to run_process so pytest can select return-code-only output classification without altering lifecycle errors, retained metadata or provider defaults. Both cli.pytest_test_runner and validate._pytest must pass classify_output=False. Preserve frozen import/candidate gates, actual return codes and fail-closed collection/config/no-tests/missing-RC/timeout/cancellation behavior. Provider authentication must remain final and dispatch once. Run only focused offline acceptance and stop promptly on Windows restricted-token test-access errors. No tests/generated files/Git mutations/installs/global settings/other model calls/provider changes/saved evidence edits.
files: engine/cld/process.py, engine/cld/cli.py, engine/cld/validate.py
acceptance_test_path: tests/test_f01_pytest_diagnostics.py
protected_inputs: docs/plans/v0.4.0-review-fixes/F01-CLD-CONTRACT.md
deps:
executor: codex:gpt-6-luna@max+fast

## Integration

Use the precise frozen F01 selector for checked provider-free integration, then
independently run the historical broad N06 reproduction and adjacent final suite.
