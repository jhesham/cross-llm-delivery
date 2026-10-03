# N06 — five-provider recursion contract

The lead owns frozen acceptance, review, integration and generated artifacts.
Use only the exact selected executor and stop after this slice.

## SLICE: N06
brief: Read N06-CLD-CONTRACT.md and tests/test_n06_recursion_contract.py. Make all five direct executor run entrypoints fail closed before any process or artifact when ambient CLD_EXECUTOR_DEPTH is anything except absent or literal 0. Set CLD_EXECUTOR_DEPTH=1 on all production executor children, preserve other provider environment adjustments and the legacy two-argument injected runner contract. Merge Cursor env overlays safely with its invocation and bundled-Node TLS settings. Add the one-slice executor and recursive-delegation prohibition to the three older prompts, preserving feedback. Keep newer contract isolation, probes, timeouts, cancellation and diff capture unchanged. Run only the focused offline acceptance test with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1. Known Windows restricted-token pytest temp-access failures must be reported promptly; stop retries and let the lead independently verify. No tests, generated files, Git mutations, global settings, package installs or other model calls. No resolver or cwd fixes from later slices.
files: engine/cld/process.py, engine/cld_providers/opencode/provider.py, engine/cld_providers/cursor/provider.py, engine/cld_providers/antigravity/provider.py, engine/cld_providers/codex/provider.py, engine/cld_providers/claude/provider.py
acceptance_test_path: tests/test_n06_recursion_contract.py
protected_inputs: docs/plans/v0.4.0-review-fixes/N06-CLD-CONTRACT.md
deps:
executor: codex:gpt-6-luna@max+fast

## Independent integration

Use the provider-free checked CLD integration path after source review and
adjacent recursion/process/provider tests; regenerate from committed runtime.
