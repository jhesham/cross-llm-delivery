## SLICE: ROUTING
brief: Route evidence slices in plan mode: add LedgerEntry.evidence_dir: str | None = None (engine/cld/ledger.py); in engine/cld/orchestrator.py (run_plan_parallel _run_one/_process_owned) keep code slices unchanged, build investigate slices' executor with executor_factory(spec, evidence=True) after checking the provider (cld.models.resolve_spec + cld.providers_api.get_provider) supports_evidence (else raise AdmissionBlocked so the slice is deferred) and otherwise use the normal worktree/judge path, and run query/materialise slices without a worktree via cld.evidence_mode.ask.run_ask(repo_dir, {"id": task.id, "kind": task.kind, "env": task.environments, "form": "question", "brief": task.brief}, executor_spec=spec, make_executor=lambda s: executor_factory(s, evidence=True), admit=lambda s: None) mapping status complete -> ledger status "integrated", commit None, evidence_dir and result.completed; needs_approval or blocked -> status "pending", result.deferred and result.blocked with the problems as failing_tests; incomplete -> "needs_repair" and result.needs_repair; failed -> "failed" (or deferred/pending when the error is in cld.executors.base.FINAL_EXECUTOR_ERRORS); in engine/cld/integration.py treat a dependency whose entry is "integrated" with commit None as satisfied without the merge-base check (dependency_block and integrate's dependency check) while integration still merges only commit-bearing DONE slices; in engine/cld/cli.py let both executor factories accept evidence: bool = False and pass evidence=True to get_executor only when True.
files: engine/cld/ledger.py, engine/cld/orchestrator.py, engine/cld/integration.py, engine/cld/cli.py
acceptance_test_path: tests/evidence/test_plan_routing.py
deps:
complexity: complex

## SLICE: CODEXFULL
brief: In engine/cld_providers/codex/contract.py add build_invocation(..., full_access: bool = False): when True (and evidence is False) use --sandbox danger-full-access while keeping the code-slice _ROLE prompt and the Git worktree root requirement; evidence=True behaviour unchanged; both False unchanged (danger-full-access via sandbox= still rejected); in engine/cld_providers/codex/provider.py make CodexExecutor.run() pass full_access=self._evidence so an evidence executor runs code/investigate slices with full access, leaving run_evidence and the default executor unchanged.
files: engine/cld_providers/codex/contract.py, engine/cld_providers/codex/provider.py
acceptance_test_path: tests/evidence/test_codex_full_access.py
deps:
complexity: easy
