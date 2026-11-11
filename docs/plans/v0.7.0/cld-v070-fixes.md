# CLD v0.7.0 release-review fixes

Design: docs/plans/v0.7.0/DESIGN.md. Executor: codex:gpt-6.1-sol@high. Integration selector: tests/v070.

## SLICE: JOBSFIX
brief: In engine/cld/mcp_jobs.py (1) key the repository reservation, spawn lock and fence lookups on the Git worktree root (git -C <repo> rev-parse --show-toplevel, resolved) when the repo is inside a worktree, falling back to the resolved path otherwise, so a subdirectory of a worktree conflicts with a job running on its root and the conflict names the running job; (2) have the runner create processes.jsonl (empty, fsynced) before the driver starts, and treat a job whose runner.json records a driver but whose processes.jsonl is missing as identities_incomplete (fence blocks, no resolution.json written). Keep all existing tests/v070 behaviour.
files: engine/cld/mcp_jobs.py
acceptance_test_path: tests/v070/test_fix_jobs.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: standard
deps:

## SLICE: SERVERFIX
brief: In engine/cld/mcp_server.py (1) handle tools/call requests concurrently (for example a thread per call or a small pool) so two simultaneous cld_job long polls each return within their own wait_seconds, with every response line written whole under a lock and main() returning only after all in-flight calls have answered at EOF; (2) treat a request whose id is a non-finite number (for example 1e999 parsing to infinity) as an invalid request: reply -32600 with id null and keep serving. Never emit non-standard JSON (allow_nan=False). Keep all existing tests/v070 behaviour.
files: engine/cld/mcp_server.py
acceptance_test_path: tests/v070/test_fix_server.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py
complexity: standard
deps:

## SLICE: UNREGFIX
brief: In generator/install_codex.py and generator/install_antigravity.py, --unregister-mcp must not require an intact installed bundle: authorize removal when --bundle names the expected owned install location for the scope (Codex <scope-root>/.agents/skills/cross-llm-delivery, Antigravity <home>/.gemini/config/skills/cross-llm-delivery-agy), the configuration entry's recorded owner equals that path and its hash matches, even if files in the bundle are modified or the bundle directory is gone. Register keeps full bundle validation. Unregister by a different owner path still refuses with the file byte-identical; link, preview, lock and atomic-write rules are unchanged.
files: generator/install_codex.py, generator/install_antigravity.py
acceptance_test_path: tests/v070/test_fix_install.py
protected_inputs: docs/plans/v0.7.0/DESIGN.md, tests/v070/conftest.py, tests/v070/_stubs.py, tests/v070/test_mcp_install.py
complexity: standard
deps:
