## SLICE: CONTRACT
brief: Implement engine/cld_providers/claude/contract.py exactly as specified in docs/plans/claude-executor/PLAN.md Task 4 "Interfaces > CONTRACT" and docs/plans/claude-executor/SPEC.md: ClaudeContractError, EFFORTS, TOOLS, UNSET_ENV, REQUIRED_FLAGS, check_capabilities, ClaudeInvocation, build_invocation and ClaudeOutcome/parse_result, stdlib only, no process calls, modelled on engine/cld_providers/codex/contract.py; run only tests/v040/test_claude_contract.py and do not edit tests.
files: engine/cld_providers/claude/contract.py
acceptance_test_path: tests/v040/test_claude_contract.py
deps:

## SLICE: CATALOG
brief: Implement the curated Claude menu exactly as specified in docs/plans/claude-executor/PLAN.md Task 4 "Interfaces > CATALOG": create engine/cld_providers/claude/catalog.py (EFFORTS, ClaudeModel, CLAUDE_MODELS, list_models), add a claude_models parameter to build_model_index in engine/cld/models.py, make spec_with_effort pin Claude effort like Codex, and have discover_model_index in engine/cld/picker.py pass CLAUDE_MODELS only when a provider named claude is registered; no process calls; run only tests/v040/test_claude_catalog.py and do not edit tests.
files: engine/cld_providers/claude/catalog.py, engine/cld/models.py, engine/cld/picker.py
acceptance_test_path: tests/v040/test_claude_catalog.py
deps:

## SLICE: PREFLIGHT
brief: Implement engine/cld_providers/claude/preflight.py exactly as specified in docs/plans/claude-executor/PLAN.md Task 4 "Interfaces > PREFLIGHT": AuthStatus, parse_auth_status, auth_problem, account_context and run_auth_preflight using an injected two-tuple runner, stdlib only, never printing or storing credentials; run only tests/v040/test_claude_preflight.py and do not edit tests.
files: engine/cld_providers/claude/preflight.py
acceptance_test_path: tests/v040/test_claude_preflight.py
deps:
