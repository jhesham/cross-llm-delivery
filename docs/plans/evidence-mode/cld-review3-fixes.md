## SLICE: SQLCLASS3
brief: In engine/cld/evidence_mode/sqlclass.py make the lexer used for side-effect detection (and statement splitting/comment stripping) follow PostgreSQL lexical rules for the remaining quoting forms; the policy stays a denylist. (1) Escape strings E'...' / e'...': a backslash escapes the next character (so \' does not end the string) and '' is also a literal quote; ordinary '...' strings keep standard-conforming rules where backslash is literal and only '' escapes. (2) Unicode identifiers U&"..." (any case of U&): decode \XXXX and \+XXXXXX escapes, and an optional following UESCAPE 'c' clause that changes the escape character, then treat the decoded text as a quoted identifier for denylist matching (so U&"n\0065xtval"('s') is a call to nextval). (3) Fail closed: if a U& identifier or U&'...' string cannot be decoded, or an unterminated string/identifier/dollar quote is met, classify the statement as "write". Text inside any string literal is never treated as a call.
files: engine/cld/evidence_mode/sqlclass.py
acceptance_test_path: tests/evidence/test_review3_sqlclass.py
deps:
complexity: standard

## SLICE: REDACT3
brief: In engine/cld/evidence_mode/sqlrun.py replace the separate secret regexes in _redact with one rule applied per line, so redaction never crosses a line boundary. A secret key is any key name containing authorization, password, passwd, pwd, token, secret, api_key or api-key (case-insensitive), written bare, single- or double-quoted (JSON), followed by optional spaces, = or :, optional spaces, then a value. If the value is quoted ("..." with backslash escapes, or '...'), replace the whole quoted value with "[REDACTED]" keeping the quotes; otherwise, for authorization keys replace everything to the end of that line, and for other keys replace up to the next whitespace, comma, semicolon, ampersand or closing brace. Keep the key text and separator so diagnostics stay readable, keep Bearer/scheme words visible only when unquoted (e.g. "Authorization: Basic [REDACTED]"), and keep URL-credential redaction (//user:pass@). _redact is also what scrubs files left behind when raw-output clean-up fails, so the JSON {"authorization":"Basic x"} form must be removed there too. Only change sqlrun.py.
files: engine/cld/evidence_mode/sqlrun.py
acceptance_test_path: tests/evidence/test_review3_redact.py
deps:
complexity: standard

## SLICE: PROVENANCE3
brief: In engine/cld/evidence_mode/bundle.py reconcile reported sql_runs against all retained runner attempts by run identity. (1) Identity first: match each sql_run to the runner record whose resolved result_path equals the sql_run's resolved result_path (both inside evidence_dir); only then check that record's statement hash equals the sql_run's SQL, its env is in task_env (when given) and in the bundle's env list, and its status: "ok" requires the result file to exist; "needs_approval" makes the bundle needs_approval; any other status, or no identity match, is a problem for that sql_run. Never match a sql_run to a different attempt with the same SQL. (2) Coverage: every runner record with status "ok" or "needs_approval" must be matched by some sql_run, except a needs_approval record superseded by a later-numbered "ok" record (by runs/N.json number) with the same statement hash and env; an unreported attempt is a problem naming it (e.g. "runner attempt runs/2.json is not reported in sql_runs"). Records with status failed or refused need not be reported. (3) Keep the MCP-only exception (task_env all mcp_only: no runner records required), the existing kind/task_id/env/created_objects checks, the "runner result file is missing" wording, the status precedence (problems -> incomplete, then needs_approval, then complete) and the (status, problems, runner_used) return.
files: engine/cld/evidence_mode/bundle.py
acceptance_test_path: tests/evidence/test_review3_provenance.py
deps:
complexity: complex
