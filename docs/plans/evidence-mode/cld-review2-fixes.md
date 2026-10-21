## SLICE: SQLCLASS
brief: In engine/cld/evidence_mode/sqlclass.py make side-effect function detection in SELECT statements robust to spelling (policy stays a denylist; do not add an allowlist). Function names must match case-insensitively whether written bare or as a double-quoted identifier ("nextval"), with any schema/catalog qualifier stripped (pg_catalog.nextval, pg_catalog."setval", "pg_catalog"."nextval"), and with optional whitespace or comments between the name and "(". A quoted identifier not followed by "(" is a column, not a call; string literals, dollar quotes and comments stay ignored. Extend _SIDE_EFFECT_FUNCTIONS with LO_CREATE, LO_CREAT, LO_FROM_BYTEA, LO_PUT, LO_TRUNCATE, LO_TRUNCATE64, LOWRITE, LO_OPEN, DBLINK, DBLINK_SEND_QUERY, DBLINK_OPEN, PG_NOTIFY, PG_SWITCH_WAL, PG_SWITCH_XLOG, PG_CREATE_RESTORE_POINT, PG_CREATE_LOGICAL_REPLICATION_SLOT, PG_CREATE_PHYSICAL_REPLICATION_SLOT, PG_DROP_REPLICATION_SLOT, PG_REPLICATION_SLOT_ADVANCE, PG_LOGICAL_EMIT_MESSAGE, PG_FILE_WRITE, PG_FILE_RENAME, PG_FILE_UNLINK, PG_FILE_SYNC, PG_ROTATE_LOGFILE, PG_PROMOTE, PG_IMPORT_SYSTEM_COLLATIONS, and treat any function whose name starts with PG_STAT_RESET as a write. currval, ordinary aggregates and date/string functions stay reads.
files: engine/cld/evidence_mode/sqlclass.py
acceptance_test_path: tests/evidence/test_review2_sqlclass.py
deps:
complexity: standard

## SLICE: REDACT
brief: In engine/cld/evidence_mode/sqlrun.py: (1) extend _redact so "Authorization: Basic <credentials>" (and any "Authorization: <scheme> <credentials>") keeps the scheme word and redacts the credentials, and so quoted secret values with spaces (password="a b c", pwd='a b') are redacted in full, keeping the existing bearer, JSON, key=value and URL-credential forms. (2) When the run status is not "ok", write _redact(stdout) to the result file instead of raw stdout (successful stdout stays unchanged; it is the query result). (3) Move raw-output clean-up into a module-level helper _remove_raw_output(path: Path) -> None that removes the runner's artifact directory (retrying shutil.rmtree once after clearing read-only bits, and raising OSError if it cannot); after calling it, check whether the directory still exists; if it does (or the helper raised), overwrite every remaining file under it with _redact of its contents (best effort, ignore errors), set status to "failed" and error to a message containing "raw output" and the directory path, so a clean-up failure is never reported as ok.
files: engine/cld/evidence_mode/sqlrun.py
acceptance_test_path: tests/evidence/test_review2_redact.py
deps:
complexity: standard

## SLICE: PROVENANCE
brief: In engine/cld/evidence_mode/bundle.py tie each reported sql_run to its own runner record instead of matching on a SQL hash alone. Make _runner_records return the readable records (status, statement hash from "sql" or "sql_path", env, resolved result_path) rather than a set of hashes. In check_bundle: (1) if bundle "kind" differs from the submitted kind, add a problem naming kind; (2) for each sql_run (unless the MCP-only exception applies to task_env), its sql_path and result_path must resolve inside evidence_dir (Path.resolve and is_relative_to; outside is a problem), and there must be a runner record with the same statement hash, whose env is in task_env when task_env is given, and which is either status "ok" with a result_path that resolves to the same file as the sql_run's result_path and exists inside evidence_dir, or status "needs_approval" (a held statement; its result need not exist); otherwise add a problem for that sql_run; (3) a materialise bundle whose created_objects is an empty list is acceptable when the bundle resolves to needs_approval (a held first CREATE created nothing); an empty list is still a problem otherwise, and a missing or non-list created_objects is always a problem. Keep the existing status precedence (problems -> incomplete, then needs_approval, then complete) and the (status, problems, runner_used) return.
files: engine/cld/evidence_mode/bundle.py
acceptance_test_path: tests/evidence/test_review2_provenance.py
deps:
complexity: complex

## SLICE: ASKWIRE
brief: (1) In engine/cld/evidence_mode/ask.py make _default_admit return the executor factory that cli.prepare_dispatch returns (its first element), and in run_ask, when admit is None and make_executor is None, build the executor with that factory(spec, evidence=True) instead of _default_executor, so the API path uses the admitted, configuration-checked factory. (2) In engine/cld/cli.py _ask_cli must not call prepare_dispatch before run_ask's provider evidence-capability check: pass run_ask an admit callable that calls prepare_dispatch(args, [slice_task], ledger) and stores the returned factory, and make_executor=lambda spec: stored_factory(spec, evidence=True); an unsupported provider (e.g. opencode) must exit 5 without prepare_dispatch being called. (3) In ask.py record ledger_entry["created"] = created_objects for every materialise task whose bundle lists created_objects, whatever the final status including needs_approval (earlier statements may have created objects before a later one was held).
files: engine/cld/evidence_mode/ask.py, engine/cld/cli.py
acceptance_test_path: tests/evidence/test_review2_askwire.py
deps:
complexity: standard
