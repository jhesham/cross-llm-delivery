# N07 — native Windows OpenCode discovery

Use the exact selected executor. The lead owns tests, review and generated files.

## SLICE: N07
brief: Read docs/plans/v0.4.0-review-fixes/N07-CLD-CONTRACT.md and tests/test_n07_opencode_native.py. Add a provider-owned native OpenCode launcher using the shared resolve_native/NativeCommand/NativeCliError API, with explicit override, Windows native PATH, then verified npm postinstall binary priority. Refuse Windows cmd/bat shim overrides and incomplete installations with native override guidance. Make production default_runner resolve only the logical opencode argv prefix; use that path for dispatch, model listing and stats, expose the same resolver to preflight, and retain two-argument injected runner compatibility without an installed CLI. Preserve environment overlays, recursion marker, exact model/variant, deadlines, cancellation, artifact options and long/multiline Unicode argv. No shell fallback. Update OpenCode setup notes. Run only focused offline acceptance with pytest plugins disabled; stop promptly on the known Windows test-access error and report it to the lead. Do not edit tests/generated files, run Git mutations, install packages, change global settings or call other models. No F01 or N08 changes.
files: engine/cld/native_cli.py, engine/cld_providers/opencode/launcher.py, engine/cld_providers/opencode/provider.py, engine/cld_providers/opencode/setup.md
acceptance_test_path: tests/test_n07_opencode_native.py
protected_inputs: docs/plans/v0.4.0-review-fixes/N07-CLD-CONTRACT.md
deps:
executor: codex:gpt-6-luna@max+fast

## Integration

Use the precise frozen N07 selector for checked provider-free integration;
independently run adjacent suites on integrated source (F01 remains pending).
