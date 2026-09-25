# T15 executable dogfood slice

## SLICE: T15
brief: Implement exactly docs/plans/codex-support/T15-CONTRACT.md in the two allowed Python files and pass committed tests/test_t15_codex_contract.py. Read the contract and synthetic fixture README first. This is an offline contract only: do not call codex exec, register a provider, edit tests/docs/config, commit/push, install globally, invoke CLD recursively, or dispatch another provider. Run the focused acceptance test and finish promptly.
executor: opencode:opencode/kimi-k3
complexity: standard
files: engine/cld_providers/codex/__init__.py, engine/cld_providers/codex/contract.py
acceptance_test_path: tests/test_t15_codex_contract.py
protected_inputs: docs/plans/codex-support/T15-CONTRACT.md, tests/fixtures/codex/README.md, pyproject.toml
deps:
