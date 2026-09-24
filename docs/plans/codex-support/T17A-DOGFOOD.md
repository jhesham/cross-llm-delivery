# T17A executable dogfood slice

## SLICE: T17A
brief: Implement exactly docs/plans/codex-support/T17A-CONTRACT.md and make the committed tests/test_t17a_packaging.py pass. Add package data for six provider Markdown resources in wheel/sdist, with isolated installed provider and CLI smoke. Edit only the named packaging files; no runtime, generator, test, tracked plugin, CI or plan edits. Do not commit, push, install globally, invoke a Codex model, recurse into CLD or dispatch another provider. Run focused tests only and finish promptly.
executor: opencode:opencode/kimi-k3
complexity: standard
files: pyproject.toml, MANIFEST.in
acceptance_test_path: tests/test_t17a_packaging.py
protected_inputs: docs/plans/codex-support/T17A-CONTRACT.md, tests/test_t17a_packaging.py
deps:
