## SLICE: ENVIRONMENTS
brief: In engine/cld/evidence_mode/environments.py implement frozen dataclass Environment(name, cls: "sandbox"|"real", platform, command: tuple[str, ...], read_only_expected: bool, mcp_only: bool = False, job_id_pattern: str | None = None), class EnvironmentError(ValueError), and load_environments(repo, path=None) -> dict[str, Environment] reading JSON {"environments":[{"name","class","platform","command","read_only_expected","mcp_only"?,"job_id_pattern"?}]} from path or <repo>/cld-environments.json (missing file -> {}); errors name the offending field (class not sandbox/real; empty command unless mcp_only; real without read_only_expected true) and duplicate names; stdlib only.
files: engine/cld/evidence_mode/environments.py
acceptance_test_path: tests/evidence/test_environments.py
deps:
complexity: easy

## SLICE: SQLCLASS
brief: In engine/cld/evidence_mode/sqlclass.py implement classify_sql(sql) -> "read"|"write" failing closed (strip -- and /* */ comments outside string literals; split on ; outside quotes; every statement must start with SELECT, WITH (and contain no INSERT/UPDATE/DELETE/MERGE/CREATE/DROP/ALTER/TRUNCATE/REPLACE/GRANT/REVOKE/CALL/EXPORT/LOAD/COPY keyword outside literals), SHOW, DESCRIBE, DESC or EXPLAIN, case-insensitive; empty, comment-only or unbalanced quotes -> "write") and statement_hash(sql) -> sha256 hex of the comment-stripped, whitespace-collapsed SQL; stdlib only.
files: engine/cld/evidence_mode/sqlclass.py
acceptance_test_path: tests/evidence/test_sqlclass.py
deps:
complexity: standard

## SLICE: APPROVALS
brief: In engine/cld/evidence_mode/approvals.py implement record_approval(repo, *, env, sql_hash, approved_by, reason) -> dict appending one JSON line {env, sql_hash, approved_by, reason, approved_at (UTC ISO)} to <repo>/.cld/approvals.jsonl while holding cld.locking.file_owner(<repo>/.cld/approvals.lock, wait_seconds=10) (ValueError if approved_by or reason is blank), and is_approved(repo, *, env, sql_hash) -> bool that returns False when the file is missing and fails closed (False) if any line is malformed; stdlib only.
files: engine/cld/evidence_mode/approvals.py
acceptance_test_path: tests/evidence/test_approvals.py
deps:
complexity: easy
