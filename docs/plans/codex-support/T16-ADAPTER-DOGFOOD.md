# T16 adapter executable dogfood slice

## SLICE: T16ADAPTER
brief: Implement exactly docs/plans/codex-support/T16-ADAPTER-CONTRACT.md in engine/cld_providers/codex/provider.py and pass the committed tests/test_t16_codex_adapter.py. Edit only that provider file. Offline fake runner only; do not call codex exec, register PROVIDER, edit tests/docs/config, commit/push, run a full suite, invoke CLD recursively, or dispatch another provider. Run only the focused acceptance test and finish promptly.
executor: opencode:opencode/kimi-k3
complexity: standard
files: engine/cld_providers/codex/provider.py
acceptance_test_path: tests/test_t16_codex_adapter.py
protected_inputs: docs/plans/codex-support/T16-ADAPTER-CONTRACT.md, engine/cld_providers/codex/contract.py, pyproject.toml
deps:
