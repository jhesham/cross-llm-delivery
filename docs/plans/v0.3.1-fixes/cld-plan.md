## SLICE: FINAL_ERRORS
brief: Implement v0.3.1 fixes 3, 5-runtime and 7a/7b exactly as specified in docs/plans/v0.3.1-fixes/PLAN.md Task 5 "Interfaces > FINAL_ERRORS" and docs/plans/v0.3.1-fixes/SPEC.md; add FINAL_EXECUTOR_ERRORS and final_error_message to base.py, network_error and network_block_reason to process.py (do not change exit_error), and in orchestrator.py stop the retry loop and rung escalation on a final or network-classified error, record the slice as resumable blocked, add slice_source and default_source, and make deliver_slice's model default None; run only tests/v031/test_final_errors.py and do not edit tests.
files: engine/cld/executors/base.py, engine/cld/process.py, engine/cld/orchestrator.py
acceptance_test_path: tests/v031/test_final_errors.py
deps:

## SLICE: CODEX_LAUNCHER
brief: Implement v0.3.1 fixes 4 and 7c exactly as specified in docs/plans/v0.3.1-fixes/PLAN.md Task 5 "Interfaces > CODEX_LAUNCHER" and docs/plans/v0.3.1-fixes/SPEC.md; create launcher.py with CodexCommand, CodexLauncherError and resolve_codex_command, add resolved_runner plus a module-global resolve_codex_command import to provider.py and use them for probes and dispatch only when the default run_process runners are in use, return missing_binary before any process when resolution fails, set PROVIDER.launch_problem and a resolving cli_invocation, and make catalog.py resolve the binary and stop re-encoding labels through cp1252; keep argv[0] as "codex" in contract.py; run only tests/v031/test_codex_launcher.py and do not edit tests.
files: engine/cld_providers/codex/launcher.py, engine/cld_providers/codex/provider.py, engine/cld_providers/codex/catalog.py
acceptance_test_path: tests/v031/test_codex_launcher.py
deps:

## SLICE: GC
brief: Implement v0.3.1 fix 6 as a new stdlib-only module engine/cld/gc.py exactly as specified in docs/plans/v0.3.1-fixes/PLAN.md Task 5 "Interfaces > GC" and docs/plans/v0.3.1-fixes/SPEC.md; provide ManagedWorktree, GcDecision, slug_for, list_managed_worktrees, worktree_dirty, plan_gc and apply_gc, reuse cld.worktree.remove_worktree and validate_location for removal, never touch refs/cld or .cld/runs, and add no CLI flags; run only tests/v031/test_gc.py and do not edit tests.
files: engine/cld/gc.py
acceptance_test_path: tests/v031/test_gc.py
deps:
