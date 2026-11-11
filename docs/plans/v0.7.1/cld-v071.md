# CLD v0.7.1 build plan: job cancellation

Design: docs/plans/v0.7.1/DESIGN.md. Executor for every slice: codex:gpt-6.1-sol@high. Integration selector, frozen for the build: tests -k "(v070 or v071) and not test_cancel_server" (CLD accepts one path plus -k; MCPCANCEL is layer 2; the lead runs all of tests/v070 and tests/v071 and the full suite after it). The lead migrates the v0.7.0 eight-tool assertions to nine before the build.

## SLICE: CANCELENGINE
brief: Per DESIGN.md "Engine: one external cancel flag with interrupt semantics": add cld.process.EXTERNAL_CANCEL and an idempotent start_cancel_watcher() (polls CLD_CANCEL_FILE every 100 ms; nothing when unset); run_process and dispatch_slot honour the flag, and when the external flag stopped a run_process it raises KeyboardInterrupt after containment cleanup instead of returning error cancelled, so no caller records a cancel as a failure; cld.cli.main starts the watcher for --new-build, --step, --integrate and --mark-repaired; run_plan_parallel also starts it and checks the flag before each dispatch and immediately before a slice's collection (once collection began the slice completes collection and its ledger write); Git commands are not interrupted mid-command. link_external_cancel lets run_plan_parallel's run-level event (and so the worktree registry-lock wait) observe the cancel, and cld.cli.main runs --integrate and --mark-repaired inside process_scope with a linked event so their registry-lock waits wake too; under an external cancel the BaseException handlers in orchestrator.py, validate.py and recovery.py re-raise without persisting failure records (recovery may mark interrupted, never failed), and run_ask checks the flag before its ask-ledger write. A blocked parallel --step must end with KeyboardInterrupt within 3 s on Windows and POSIX with every child stopped; plain Ctrl+C and scoped cancels keep their behaviour.
files: engine/cld/process.py, engine/cld/dispatch_limits.py, engine/cld/orchestrator.py, engine/cld/cli.py, engine/cld/validate.py, engine/cld/recovery.py, engine/cld/evidence_mode/ask.py
acceptance_test_path: tests/v071/test_cancel_engine.py
protected_inputs: docs/plans/v0.7.1/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py, tests/v071/conftest.py
complexity: complex
deps:

## SLICE: JOBCANCEL
brief: Per DESIGN.md "Jobs: cancel requests, grace, escalation, states": add cancel_job(job_id, *, jobs_root=None) -> {job_id, state, requested, reason} to engine/cld/mcp_jobs.py with a per-job state.lock shared with the runner's exit.json publication (no lost or late requests), requested false for terminal or lost jobs, reason legacy_runner when runner.json lacks "cancel": 1, and repeated requests keeping the first grace deadline; the runner records "cancel": 1, passes CLD_CANCEL_FILE, allows CLD_MCP_CANCEL_GRACE (default 30 s), then terminates and runs the containment check; exit.json state cancelled or cancel_unconfirmed with reason cancel_requested or cancel_escalated, or finished with reason cancel_too_late when the driver had already printed a Schema-1 response whose gate_code equals its exit code; update every state rule in the module (exit-record validation, status mapping, long polls waiting while running or cancelling, conflict naming, fence on cancel_unconfirmed, retention of cancelled); test fault CLD_MCP_FAULT=ignore_cancel only under CLD_MCP_TESTING=1, and CLD_MCP_FAULT may now list several faults comma-separated (for example ignore_cancel,kill_fails).
files: engine/cld/mcp_jobs.py
acceptance_test_path: tests/v071/test_cancel_jobs.py
protected_inputs: docs/plans/v0.7.1/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py, tests/v071/conftest.py
complexity: complex
deps:

## SLICE: INSTCANCEL
brief: Per DESIGN.md "Registration": append cld_cancel as the last entry of MCP_TOOLS in generator/install_codex.py (Antigravity reuses that list for its allow rules), not pre-approved under --mcp-approve read-only; re-registering over an intact v0.7.0 entry owned by the same bundle must produce the nine-tool entry; hand-edited, foreign and unowned entries are still refused byte-identical.
files: generator/install_codex.py
acceptance_test_path: tests/v071/test_cancel_install.py
protected_inputs: docs/plans/v0.7.1/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py, tests/v070/test_mcp_install.py, tests/v071/conftest.py
complexity: standard
deps:

## SLICE: GENCANCEL
brief: Per DESIGN.md "Skills and docs": add one ASCII line about cld_cancel (call it, then keep polling cld_job while running or cancelling; any other state is final; unconfirmed or lost jobs block the repository until the named processes are gone) to the six skill templates and the two host workflow references, keeping the CLI instructions and the rendered Codex SKILL.md within 130 lines and 9000 characters.
files: skill/SKILL.template.md, skill/SKILL.unified.template.md, skill/hosts/codex/SKILL.template.md, skill/hosts/codex/SKILL.unified.template.md, skill/hosts/antigravity/SKILL.template.md, skill/hosts/antigravity/SKILL.unified.template.md, skill/hosts/codex/references/codex-workflow.md, skill/hosts/antigravity/references/antigravity-workflow.md
acceptance_test_path: tests/v071/test_cancel_gen.py
protected_inputs: docs/plans/v0.7.1/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py, tests/v060/_golden.py, tests/v071/conftest.py
complexity: easy
deps:

## SLICE: MCPCANCEL
brief: Per DESIGN.md "Server: the cld_cancel tool": add cld_cancel (job_id) to engine/cld/mcp_server.py calling cld.mcp_jobs.cancel_job and returning its dict at once; isError for unknown ids, -32602 for malformed ids; refused by the executor guard; tools/list lists nine tools; keep concurrency, busy admission and all v0.7.0 behaviour.
files: engine/cld/mcp_server.py
acceptance_test_path: tests/v071/test_cancel_server.py
protected_inputs: docs/plans/v0.7.1/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py, tests/v071/conftest.py
complexity: standard
deps: JOBCANCEL
