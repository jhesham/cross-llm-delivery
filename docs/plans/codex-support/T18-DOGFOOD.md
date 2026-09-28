# T18 executable dogfood

## SLICE: T18
brief: Implement docs/plans/codex-support/T18-CONTRACT.md in exactly the four allowed files. Run only tests/test_t18_release.py and tests/test_publish.py; all command fixtures use fakes or local bare remotes. Do not publish/tag/push a real remote, invoke another provider or CLD, edit tests/docs/config, commit, or run a full suite. Finish promptly.
executor: opencode:opencode/kimi-k3
complexity: standard
files: generator/release.py, generator/publish.py, release.ps1, sync-public.ps1
acceptance_test_path: tests/test_t18_release.py
protected_inputs: docs/plans/codex-support/T18-CONTRACT.md, tests/test_publish.py
deps:
