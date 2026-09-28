# T19A bounded executable slice

## SLICE: T19A
brief: Implement docs/plans/codex-support/T19A-CONTRACT.md in the one allowed test-only driver file. Run only tests/integration/test_t19_rehearsal.py. Do not edit protected tests/docs/engine/config, call providers or CLD, commit, or run the full suite. Finish promptly.
executor: opencode:opencode/kimi-k3
complexity: standard
files: tests/integration/t19_driver.py
acceptance_test_path: tests/integration/test_t19_rehearsal.py
protected_inputs: docs/plans/codex-support/T19A-CONTRACT.md
deps:
