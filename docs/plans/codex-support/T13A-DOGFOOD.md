# T13A executable dogfood slice

## SLICE: T13A
brief: Implement exactly docs/plans/codex-support/T13A-CONTRACT.md and make the committed tests/test_t13a_install.py pass. Add a safe, previewable standalone Codex skill installer and concise Codex installation documentation. Edit only the two listed files. Do not edit tests, contract, generators, tracked plugins or engine. Do not commit, push, install globally, recurse through CLD or dispatch another provider. Run focused tests only and finish promptly.
executor: opencode:opencode/kimi-k3
complexity: standard
files: generator/install_codex.py, INSTALL.md
acceptance_test_path: tests/test_t13a_install.py
protected_inputs: docs/plans/codex-support/T13A-CONTRACT.md, pyproject.toml
deps:
__pycache__/
*.egg-info/
*.pyc
.pytest_cache/
.cld-ledger.json
.cld/
publish-targets.toml
dist/
