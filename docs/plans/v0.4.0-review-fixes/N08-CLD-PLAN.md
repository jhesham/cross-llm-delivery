# N08 — Antigravity native POSIX cwd

Use the exact selected executor; the lead owns tests, review and generated output.

## SLICE: N08
brief: Read docs/plans/v0.4.0-review-fixes/N08-CLD-CONTRACT.md and tests/test_n08_antigravity_cwd.py. Restrict _dispatch_cwd SystemDrive transformation to Windows, returning the native Path.home on POSIX. Preserve Windows transcript-drive handling, explicit home, selected-home dispatch/transcript lookup, --add-dir worktree, exact model, lifecycle options, recursion marker and injected runners. Make the missing-transcript hint platform-aware and update setup notes without claiming live POSIX/macOS provider verification. Run only the focused offline acceptance; stop promptly and report the known Windows restricted-token test-access error. No tests/generated files/Git mutations/installs/global changes/other model calls/F01 work.
files: engine/cld_providers/antigravity/provider.py, engine/cld_providers/antigravity/setup.md
acceptance_test_path: tests/test_n08_antigravity_cwd.py
protected_inputs: docs/plans/v0.4.0-review-fixes/N08-CLD-CONTRACT.md
deps:
executor: codex:gpt-6-luna@max+fast

## Integration

Use the precise frozen N08 selector for checked provider-free integration;
independently run adjacent suites on integrated source while F01 remains pending.
