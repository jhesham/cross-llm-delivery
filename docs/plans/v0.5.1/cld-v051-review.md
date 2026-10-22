## SLICE: GATEWAY2
brief: Make Claude gateway detection match what a `claude -p --restricted` dispatch actually loads (restricted sessions ignore the user's settings.json but do load managed settings). In engine/cld_providers/claude/preflight.py add managed_settings_file() -> Path returning the platform managed-settings path (Windows: Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "ClaudeCode" / "managed-settings.json"; macOS: /Library/Application Support/ClaudeCode/managed-settings.json; other: /etc/claude-code/managed-settings.json) and resolve_gateway(mode, environ, *, user_settings: Path, managed_settings: Path) -> tuple[str | None, str | None] returning (gateway_host, problem): subscription mode returns (hostname of ANTHROPIC_BASE_URL in the managed settings "env", None) or (None, None), never using user settings or environ (environ gateway variables are removed from subscription dispatch); gateway mode returns (env host, None) when environ has ANTHROPIC_BASE_URL and a non-empty ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY, (env host, problem naming ANTHROPIC_AUTH_TOKEN) when the URL is set without a credential, (managed host, None) when only managed settings route, (None, problem) when only the user settings.json routes, with a problem saying restricted executor sessions ignore user settings.json and to set ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN in the environment, and (None, None) otherwise. Problems must never contain setting values. Reuse gateway_host/_hostname for parsing. In engine/cld_providers/claude/provider.py _preflight uses resolve_gateway with the user settings file (CLAUDE_CONFIG_DIR/settings.json or ~/.claude/settings.json) and managed_settings_file(); a returned problem becomes the launch problem, otherwise the host goes to auth_problem(status, mode=..., gateway=host); _context_extra uses the same resolved host for account_context, so changing a managed gateway host changes validation identity. Keep auth_problem/account_context signatures.
files: engine/cld_providers/claude/preflight.py, engine/cld_providers/claude/provider.py
acceptance_test_path: tests/v051/test_review_gateway.py
deps:
complexity: standard

## SLICE: CODEX2
brief: Codex MCP isolation fixes in engine/cld_providers/codex/contract.py and provider.py. (1) isolation_args(mcp_names) must emit "--config", "mcp_servers.<name>.enabled=false" only for names matching [A-Za-z0-9_-]+ (Codex 0.163 rejects quoted dotted keys in overrides, and an invalid override breaks the run); other names are skipped. Add skipped_mcp_names(mcp_names) -> list[str] returning the skipped names. (2) CodexExecutor.run collects MCP names from both the Codex home config (as today) and the worktree's own project config, configured_mcp_servers(Path(workdir) / ".codex"), de-duplicated in order, for both code and evidence dispatch. (3) When any names are skipped, prepend one line to the ExecutorResult raw_log (success and failure results) naming them, e.g. "CLD could not disable MCP server(s) for this run: team.docs (names Codex overrides cannot express)". Do not change the feature switches or the essential features.
files: engine/cld_providers/codex/contract.py, engine/cld_providers/codex/provider.py
acceptance_test_path: tests/v051/test_review_codex.py
deps:
executor: codex:gpt-6.1-sol@high
complexity: standard

## SLICE: INSTALLER2
brief: In generator/install_codex.py _install, make the rename-denied fallback own only what it creates and always restore the previous install. (1) Create the target exclusively first (target.mkdir() without exist_ok; FileExistsError means another process owns it: re-raise without touching it), only then mark it as created by this run, and copy the stage contents into it (shutil.copytree(stage, target, symlinks=False, dirs_exist_ok=True)), then _verify_owned(target) and remove the stage. (2) On failure after this run created the target: try shutil.rmtree(target); if that fails (for example a locked file), rename the failed target aside to a unique sibling ".<name>.cld-failed-<pid>" so the path is free; then, when updating, restore the backup to the target. Always re-raise the ORIGINAL error (the copy/verification error), attaching any cleanup or restore failure with exc.add_note naming the retained paths, never replacing it. (3) Never remove or rename a target this run did not create.
files: generator/install_codex.py
acceptance_test_path: tests/v051/test_review_installer.py
deps:
executor: codex:gpt-6.1-sol@high
complexity: standard

## SLICE: VALSTATE
brief: In engine/cld/validate.py validate_model, after deliver_slice returns normally, make the recovery session terminal when it is still "running" or "reserved" (session.record.get("state")): save state="failed" with the failure note when the dispatch failed or acceptance did not pass, and state="verified" when the probe was accepted, unless the session already recorded a terminal state such as "verified" or "collected". The exception path keeps today's handling.
files: engine/cld/validate.py
acceptance_test_path: tests/v051/test_review_validate.py
deps:
complexity: easy
