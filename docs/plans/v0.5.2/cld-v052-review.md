## SLICE: SPECOPTS
brief: In engine/cld/models.py resolve_spec: (1) reject any executor spec containing a control character (ord < 32 or 127, including CR, LF, TAB and NUL) anywhere in the original value, before any strip/trim, with a ValueError naming control characters; only then trim surrounding spaces. (2) For the codex provider, validate options model-free with the same rules the Codex invocation builder applies, so a spec that dispatch would reject is rejected here: effort must be one of cld_providers.codex.contract._EFFORTS (ValueError mentioning "effort" and listing the allowed values) and service_tier must be absent or "fast". Keep today's canonical spec, kwargs and Claude handling. --dry-run already resolves every spec through resolve_spec, so it then rejects these specs too (text and --json, exit/gate 5, no model calls).
files: engine/cld/models.py
acceptance_test_path: tests/v052/test_review_spec.py
deps:
complexity: easy

## SLICE: CODEXSCRATCH
brief: Give each Codex dispatch a private scratch folder for command output, outside the worktree. In engine/cld_providers/codex/contract.py: build_invocation gains scratch_dir: Path | None = None; when set, append "--config", "sandbox_workspace_write.writable_roots=[<TOML string of the folder path, forward slashes>]" before the final "-", add CLD_SCRATCH_DIR=<str(scratch_dir)> to env, and add a role line naming that exact folder: when a command's output is missing or the shell reports a console or access error after the command ran, redirect the output to a new file inside that scratch folder (never inside the working directory), read it, and leave it there (CLD removes the folder). Without scratch_dir the role line says to use the folder in the CLD_SCRATCH_DIR environment variable and never the working directory. Remove the old example that writes cld-test-output.txt into the working directory, and keep "cmd /c" out of both roles. In engine/cld_providers/codex/provider.py CodexExecutor.run (code and evidence dispatch) creates the folder with tempfile.mkdtemp(prefix="cld-codex-out-") under the artifact directory when one is set and it is outside the worktree, else under the system temp directory, passes it as scratch_dir, and removes it (shutil.rmtree, ignore errors) after the process ends, on success and failure. The folder must never be inside the worktree.
files: engine/cld_providers/codex/contract.py, engine/cld_providers/codex/provider.py
acceptance_test_path: tests/v052/test_review_scratch.py
deps:
executor: codex:gpt-6.1-sol@high
complexity: standard
