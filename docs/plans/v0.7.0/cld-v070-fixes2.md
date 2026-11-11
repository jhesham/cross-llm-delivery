# CLD v0.7.0 release-review fixes, round 2

Design: docs/plans/v0.7.0/DESIGN.md. Executor: codex:gpt-6.1-sol@high. Integration selector: tests/v070.

## SLICE: JOBSKEY
brief: In engine/cld/mcp_jobs.py, compute the canonical repository identity (the resolved Git worktree root when the repo is inside a worktree, else the resolved path) once when a job starts, persist it in the job's request.json, and make the fence and every reservation or spawn-lock lookup for an existing job use that persisted identity instead of re-deriving it from the original repo path; jobs written before this change (no persisted identity) fall back to the current derivation. A job started from a subdirectory that is later removed must still fence its worktree root. Keep all existing tests/v070 behaviour.
files: engine/cld/mcp_jobs.py
acceptance_test_path: tests/v070/test_fix_jobs.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: standard
deps:

## SLICE: SERVERBUSY
brief: In engine/cld/mcp_server.py, never queue a tools/call behind other in-flight calls: admit a call only when a worker is free (for example a semaphore sized to the pool, acquired without blocking) and answer any excess call at once with an isError tool result saying the server is busy and to retry, so no call waits longer than its own deadline. Responses stay whole lines under the write lock, main() still drains in-flight calls at EOF, and non-tools/call requests keep being answered. Keep all existing tests/v070 behaviour.
files: engine/cld/mcp_server.py
acceptance_test_path: tests/v070/test_fix_server.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: standard
deps:
