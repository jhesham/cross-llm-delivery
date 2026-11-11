# CLD v0.7.0 build plan: optional MCP adapter and the same lead experience on every host

Design: docs/plans/v0.7.0/DESIGN.md (revision 7; no cancellation in v0.7.0). Executor for every slice: codex:gpt-6.1-sol@high, passed with --executor. Integration selector, frozen for the build: tests/v070 -k "not test_mcp_tools". The lead runs all of tests/v070 and the full suite after layer 2.

## SLICE: MCPJOBS
brief: Implement engine/cld/mcp_jobs.py exactly per DESIGN.md "Jobs" (not from the spike scripts), with the pinned public API (start_job, job_status, check_fence, resolve_job, purge, run_job, JobConflict, JobFenced; jobs_root defaults to CLD_MCP_JOBS or ~/.cld/mcp-jobs) and pinned return and record keys and pinned record formats: the runner with reservation lock and runner.json, gated driver start recorded in runner.json before it runs (Windows own Job Object with the stdin-gated bootstrap, POSIX own session with a pass_fds pipe-gated launcher that execs in place), CLD_PROCESS_REGISTRY in the driver environment, the containment check on exit with termination of leftovers and a 5 s confirmation poll, atomic exit.json with containment clean or unconfirmed, the spawn-lock handshake, the fence checking recorded identities and every recorded POSIX process group (reaped or leaderless) with resolution.json and identities_incomplete, state rules (running, finished, died, exit_unconfirmed, lost), pid plus start_time identity, CLD_MCP_FAULT=kill_fails (no-op termination and no kill-on-close) and record_fails only under CLD_MCP_TESTING=1, no cancellation (v0.7.1), 32-hex job ids, resolved lock paths, and conservative retention; explicit Windows ctypes types; no third-party dependencies.
files: engine/cld/mcp_jobs.py
acceptance_test_path: tests/v070/test_mcp_jobs.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: complex
deps:

## SLICE: ENGINEMCP
brief: Engine support per DESIGN.md "Jobs" (Engine support, Pinned record formats) and "Engine change": (1) --new-build --json adds artifacts.ledger_backup when a previous ledger was backed up (artifacts come from _artifacts_field in cli.py and _DEFAULT_ARTIFACTS in cli_response.py; the path is ledger.build["backup"]); (2) with CLD_PROCESS_REGISTRY set, run_process records each child in the pinned format before it does any work (Windows: the bootstrap process, after job.assign and before its payload; POSIX: the target itself, through a pass_fds pipe-gated launcher that execs in place), kills it unrun if the record cannot be written, and appends a reap line on exit; behaviour with these variables unset is unchanged.
files: engine/cld/cli.py, engine/cld/cli_response.py, engine/cld/process.py
acceptance_test_path: tests/v070/test_engine_mcp.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: complex
deps:

## SLICE: MCPPROTO
brief: Implement engine/cld/mcp_server.py per DESIGN.md "Executables and the driver contract", "Protocol" and the sync rows of "Tools": main(stdin=None, stdout=None, scripts_dir=None) and handle(message) -> dict | None; version negotiation over 2025-06-18, 2025-03-26 and 2024-11-05; error codes -32700/-32600/-32601/-32602 without terminating; cld_preview, cld_status and cld_new_build via run_delivery.py (cld_new_build runs directly here; MCPTOOLS moves it onto the job runner) and cld_list_models via list_models.py (advisory JSON, no --host), resolved from scripts_dir with CLD_DRIVER/CLD_MODELS test overrides; --host from CLD_HOST; absolute-path checks; sync timeout CLD_MCP_SYNC_TIMEOUT default 45 s; the executor guard refusing mutating tools when CLD_EXECUTOR_DEPTH is set; serverInfo.version from the bundle SKILL.md banner, then VERSION, then 0.0.0; results as content text plus structuredContent; no third-party dependencies.
files: engine/cld/mcp_server.py
acceptance_test_path: tests/v070/test_mcp_protocol.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: standard
deps:

## SLICE: AGYISOLATE
brief: Per DESIGN.md "Executor isolation (Antigravity)", make Antigravity executor dispatches pass a session-only --settings value equal to {"permissions":{"deny":["mcp(cld/*)"]}} (pinned in DESIGN.md), leaving every other dispatch argument and behaviour unchanged; Antigravity evidence support stays unsupported.
files: engine/cld_providers/antigravity/provider.py
acceptance_test_path: tests/v070/test_executor_isolation.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: easy
deps:

## SLICE: INSTMCP
brief: Add the register/unregister actions to generator/install_codex.py and generator/install_antigravity.py exactly per DESIGN.md "Registration": --register-mcp and --unregister-mcp, combinable with --preview (not added to the existing mutually exclusive group), for the owned all-executors installation in the same scope root only (the bundle must contain scripts/cld_mcp.py); ownership as bundle path plus entry hash; the Codex [mcp_servers.cld] snippet recorded in DESIGN.md under --mcp-approve read-only|all; Antigravity user-scope mcp_config.json merge (workspace refused, allow rules reported as fields); one scope-level lock shared by register, unregister and skill --uninstall, taken through cld.locking.file_owner(..., wait_seconds=10) after adding the repository's engine/ directory to sys.path, and created only after link, preview and target-existence checks; validated atomic replace; link refusal; resolved lock paths; skill --uninstall refused while an owned registration points at the bundle; a single JSON object of output.
files: generator/install_codex.py, generator/install_antigravity.py
acceptance_test_path: tests/v070/test_mcp_install.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: complex
deps:

## SLICE: GENMCP
brief: Per DESIGN.md, add skill/scripts/cld_mcp.py (same sys.path shim as run_delivery.py; --run-job <job-dir> calls cld.mcp_jobs.run_job, --resolve-job <id> --confirm calls cld.mcp_jobs.resolve_job, otherwise cld.mcp_server.main(scripts_dir=<its own directory>)), vendor it to scripts/cld_mcp.py in every generated bundle, write .mcp.json only into the cross-llm-delivery Claude Code plugin (the unified block of _main_claude in build_plugins.py, never the per-provider loop or _main_codex) with the documented command, args and env, and add the short "MCP tools" section to the six skill templates and two host workflow references: ASCII only, keeping the CLI instructions, linking only to files inside the bundle, and keeping the rendered Codex SKILL.md within 130 lines and 9000 characters.
files: skill/scripts/cld_mcp.py, generator/build_skill.py, generator/build_plugins.py, skill/SKILL.template.md, skill/SKILL.unified.template.md, skill/hosts/codex/SKILL.template.md, skill/hosts/codex/SKILL.unified.template.md, skill/hosts/antigravity/SKILL.template.md, skill/hosts/antigravity/SKILL.unified.template.md, skill/hosts/codex/references/codex-workflow.md, skill/hosts/antigravity/references/antigravity-workflow.md
acceptance_test_path: tests/v070/test_gen_mcp.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py, tests/v060/_golden.py
complexity: standard
deps:

## SLICE: MCPTOOLS
brief: Extend engine/cld/mcp_server.py with the job tools per DESIGN.md "Tools" and "Jobs" using the cld.mcp_jobs public API: cld_step, cld_integrate, cld_mark_repaired (exact argv, required arguments with no defaults, workers 1..4 default 1), and cld_job (wait 0..45 default 30), with no cancel tool in v0.7.0; cld_new_build now runs through the job runner and waits up to the sync deadline; the entry script for jobs is <scripts_dir>/cld_mcp.py, falling back to <repo>/skill/scripts/cld_mcp.py when run from a source checkout; JobConflict, JobFenced, unknown or malformed job ids and invalid arguments become isError results or -32602 as the design says; the executor guard covers all mutating tools; retention runs on server start; tools/list lists all eight tools.
files: engine/cld/mcp_server.py
acceptance_test_path: tests/v070/test_mcp_tools.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: standard
deps: MCPJOBS, MCPPROTO, ENGINEMCP, GENMCP
