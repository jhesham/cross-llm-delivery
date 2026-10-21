## SLICE: SQLSAFE
brief: Fix three SQL-runner review findings. (1) In engine/cld/evidence_mode/sqlclass.py classify_sql must return "write" for SELECT statements with side effects: calls to nextval, setval, pg_advisory_lock/pg_advisory_xact_lock (and the try_ variants), lo_import, lo_export, lo_unlink, dblink_exec, dblink_connect, pg_terminate_backend, pg_cancel_backend, pg_reload_conf, set_config, and row-locking clauses FOR UPDATE / FOR NO KEY UPDATE / FOR SHARE / FOR KEY SHARE; match these as function-call tokens (name followed by "(") or clause keywords outside string literals and comments, so that "SELECT 'nextval' AS label" and ordinary aggregates stay "read". (2) In engine/cld/evidence_mode/sqlrun.py extend _redact to cover "Bearer <token>" (keep the word Bearer, redact the token), JSON-style keys whose name contains token, secret, password or api_key with quoted values ("access_token": "x" -> "access_token": "[REDACTED]"), and keep the existing key=value and URL-credential forms; also run run_process with artifact_dir pointing at a private directory under out_dir and remove that directory (shutil.rmtree, ignore errors) after the result is read, so no unredacted raw stdout/stderr copy remains anywhere (not under out_dir and not in the system temp directory). (3) Pass timeout=deadline_seconds(dispatch=True) (cld.process.deadline_seconds, already imported via "from cld import process") to the runner call, so SQL is bounded by CLD_DISPATCH_TIMEOUT rather than the 30 s probe default; a timeout must become a "failed" record with the redacted error, as other runner failures do.
files: engine/cld/evidence_mode/sqlclass.py, engine/cld/evidence_mode/sqlrun.py
acceptance_test_path: tests/evidence/test_review_sqlsafe.py
deps:
complexity: standard

## SLICE: EVIDENCE
brief: Fix five evidence-bundle and CLI review findings. (1) In engine/cld/evidence_mode/bundle.py _runner_records must only count records whose status is "ok" and whose result_path resolves (via _path_from) to an existing file; a record with any other status or a missing result contributes no hash, and check_bundle reports a problem containing "result" when a runner record's result file is missing. (2) check_bundle gains keyword arguments task_env: list[str] | None = None and task_id: str | None = None; when task_id is given the bundle's task_id must equal it (else incomplete with a problem naming task_id); when task_env is given the bundle's env must be a subset of task_env (else incomplete), and the MCP-only exception (_mcp_only_environments) is evaluated against task_env, never against names taken from the bundle; engine/cld/evidence_mode/ask.py run_ask passes task["env"] and task["id"]. (3) In engine/cld/cli.py refuse --sql and --approve combined with --dry-run (or with --status, --usage, --watch, --plan or --ask) before anything is read, executed or recorded: print a JSON-capable error and return exit code 5. (4) _ask_cli must admit the task with the caller's actual args: call prepare_dispatch(args, tasks, ledger) (so --validation-policy and --revalidate-models are honoured), take the executor factory it returns as the first element, and pass run_ask make_executor=lambda spec: factory(spec, evidence=True) and an admit callable that does nothing more (admission already ran); remove the args rebuild via build_parser().parse_args([]) in ask.py _default_admit's CLI path. (5) In ask.py record ledger_entry["created"] for every materialise task whose bundle lists created_objects, whatever the final status (failed, incomplete, needs_approval or complete), so list_created reports objects created before a timeout or failure.
files: engine/cld/evidence_mode/bundle.py, engine/cld/evidence_mode/ask.py, engine/cld/cli.py
acceptance_test_path: tests/evidence/test_review_evidence.py
deps:
complexity: complex

## SLICE: ROUTE2
brief: Fix two plan-mode routing review findings. (1) In engine/cld/orchestrator.py (the evidence outcome mapping inside run_plan_parallel, where evidence_status == "incomplete" currently becomes "needs_repair") map an incomplete evidence slice to FAILED with result.failed and its problems recorded, so a later --step retries it with a fresh evidence directory instead of leaving a dead-end needs_repair slice (evidence slices have no worktree or commit to repair). (2) In engine/cld/build_state.py, where reconcile converts an "integrated" entry to DONE, keep "integrated" for commit-free evidence entries (entry.commit is None and entry.evidence_dir is set), because they have no commit to re-integrate; downstream dependency checks in engine/cld/integration.py must keep treating them as satisfied, and integration of a dependent code slice after reconcile must pass.
files: engine/cld/orchestrator.py, engine/cld/build_state.py
acceptance_test_path: tests/evidence/test_review_route.py
deps:
complexity: standard

## SLICE: CODEXGIT
brief: In engine/cld_providers/codex/contract.py build_invocation add --skip-git-repo-check to the codex exec argv when evidence=True (evidence runs use a scratch directory that is not a Git repository), keeping the prompt on stdin as the final "-" argument; code invocations (evidence=False, with or without full_access) must never include --skip-git-repo-check.
files: engine/cld_providers/codex/contract.py
acceptance_test_path: tests/evidence/test_review_codexgit.py
deps:
complexity: easy
