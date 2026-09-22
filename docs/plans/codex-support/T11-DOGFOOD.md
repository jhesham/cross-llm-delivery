# T11 executable delivery

## SLICE: T11
brief: Implement the complete contract in docs/plans/codex-support/T11-CONTRACT.md. Read that file first, then tests/test_t11_cli_contract.py and the existing driver. Move reusable command handling to cld.cli; provide python -m cld and a thin backward-compatible script. Implement robust bounded JSON responses and host provenance. Existing importlib-based driver test monkeypatches must keep working; inspect tests/test_run_delivery.py and tests/test_t09_admission.py. Do not edit tests/config/docs/providers or broaden permissions. Run the acceptance test plus existing CLI, telemetry, status, admission and generator tests locally. No live model calls, no recursive CLD dispatch and no commits/pushes from the executor. Complete all allowed implementation before replying.
files: engine/cld/cli.py, engine/cld/__main__.py, engine/cld/cli_response.py, engine/cld/telemetry.py, skill/scripts/run_delivery.py
acceptance_test_path: tests/test_t11_cli_contract.py
protected_inputs: docs/plans/codex-support/T11-CONTRACT.md
deps:
executor: opencode:opencode/kimi-k3
complexity: complex
