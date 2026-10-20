## SLICE: MATERIALISE
brief: In engine/cld/evidence_mode/bundle.py make check_bundle validate every materialise created_objects entry (dict with non-empty str "name", "rows" an int >= 0 or None, "schema" a list) adding a problem containing "created_objects" for any malformed entry; in engine/cld/evidence_mode/ask.py add "created": the bundle's created_objects to the ask ledger line only when kind is materialise and status is complete (otherwise omit or []), and add list_created(repo) -> list[dict] reading <repo>/.cld/runs/ask/ledger.jsonl (missing -> []) and returning one dict per created object {**object, "task_id", "evidence_dir", "ts"} newest first (later ledger lines first, preserving object order within a line); never delete the evidence sql/ files.
files: engine/cld/evidence_mode/bundle.py, engine/cld/evidence_mode/ask.py
acceptance_test_path: tests/evidence/test_materialise.py
deps:
complexity: standard

## SLICE: APPROVE
brief: In engine/cld/cli.py add --approve TASK_ID with --env NAME, --statement HASH (64 lowercase hex, else blocked), --reason TEXT and optional --approved-by NAME (default "lead"), routed early in both text and JSON modes like --sql (no plan, no dispatch): the env must be declared in cld.evidence_mode.environments.load_environments(repo) (else blocked), then call cld.evidence_mode.approvals.record_approval(repo, env=, sql_hash=, approved_by=, reason=) (ValueError for blank reason -> blocked) and print JSON {"command": "approve", "task_id": TASK_ID, **record} with exit 0; every refusal prints JSON with "command": "approve", "status": "blocked" and an "error", exit 5, and records nothing.
files: engine/cld/cli.py
acceptance_test_path: tests/evidence/test_approve_cli.py
deps:
complexity: easy
