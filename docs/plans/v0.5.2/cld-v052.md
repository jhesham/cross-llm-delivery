## SLICE: GATEWAYSPEC
brief: Make Claude gateway model IDs work end to end, not only in the invocation builder. (1) In engine/cld_providers/claude/contract.py export one validator, validate_claude_model(model: str, *, gateway: bool) -> str, used by build_invocation: subscription mode keeps the exact claude-[a-z0-9][a-z0-9.-]* fullmatch and today's message naming claude-sonnet-5; gateway mode requires a single-line ID with no CR/LF/NUL that fullmatches [A-Za-z0-9][A-Za-z0-9._:/-]* and contains "claude" case-insensitively, with a message that names the gateway rule (for example "gateway mode requires a gateway model ID containing 'claude'") and never mentions claude-sonnet-5. Raise ClaudeContractError (a ValueError) from it. (2) In engine/cld/models.py resolve_spec, for the claude provider determine the mode with cld_providers.claude.preflight.claude_mode(os.environ) (an invalid CLD_CLAUDE_MODE keeps raising its ValueError) and validate the model with validate_claude_model(model, gateway=(mode == "gateway")), re-raised as ValueError; keep the effort checks and keep the full model ID in the canonical spec and kwargs (claude:global.anthropic.claude-opus-5-5@low stays exactly that). (3) In engine/cld/cli.py make --dry-run (text and --json preview) resolve every executor spec it would use (args.executor or the default, plus each slice's executor) with resolve_spec, and fail with exit/gate 5 and the error message when any spec is invalid, so a dry run cannot pass a spec that --step rejects; it must still make no model calls. (4) Make sure nothing else in admission rejects a gateway ID in gateway mode (for example availability/catalog checks for the claude provider must not block an ID that is not in the curated menu).
files: engine/cld/models.py, engine/cld_providers/claude/contract.py, engine/cld/cli.py
acceptance_test_path: tests/v052/test_gateway_spec.py
deps:
complexity: standard

## SLICE: PROBE
brief: In engine/cld/validate.py _init_repo, give the validation probe repository its own pytest configuration so pytest's rootdir/ini discovery stops at the probe and never uses a parent project's pytest.ini, addopts or conftest.py: write a pytest.ini containing "[pytest]" and "addopts =" (empty) at the probe repo root, and commit it with the other baseline files. Keep the acceptance test and calc.py unchanged.
files: engine/cld/validate.py
acceptance_test_path: tests/v052/test_probe_isolation.py
deps:
complexity: easy

## SLICE: CODEXHINT
brief: In engine/cld_providers/codex/contract.py replace the Windows line in both _ROLE and _EVIDENCE_ROLE that tells the executor to run commands through `cmd /c` (Codex wraps every command in PowerShell anyway, so it does not help). The new line: on Windows, if a command's output is missing or the shell reports a console or access error after the command ran, redirect the command's output to a file inside the working directory (for example `python -m pytest -q > cld-test-output.txt 2>&1`), then read that file, and delete it before finishing. The words "cmd /c" must not appear in either role.
files: engine/cld_providers/codex/contract.py
acceptance_test_path: tests/v052/test_codex_windows_hint.py
deps:
executor: codex:gpt-6.1-sol@high
complexity: easy
