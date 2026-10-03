# N05 — Codex configuration admission identity

Implement only this slice using the exact selected executor. The lead owns tests,
review, integration and generated artifacts. Do not invoke another model, run
Git mutations, edit tests or generated files, or change global Codex settings.

## SLICE: N05
brief: Fix Codex admission configuration identity. Read the acceptance tests and N05-CLD-CONTRACT.md; add a provider-owned configuration-input callback and discover inputs dynamically inside every context_of call, then merge with existing and explicit --validation-config paths without breaking OpenCode config_env. Hash file bytes/missing states through existing validation_context. Use selected CODEX_HOME/config.toml or default ~/.codex/config.toml exclusively; conservatively include .codex/config.toml at the repository and its ancestors because custom project-root markers exist. Add Codex config_env extraction of env_key and env_http_headers values from TOML; hash referenced environment values without persisting secrets. Preserve explicit exact model/effort/tier and the existing before/after validation and admitted-factory checks. See contract for Unix system inputs and deliberate authentication/profile boundaries. Run only focused offline tests and stop after implementation; do not generate artifacts or commit.
files: engine/cld/providers_api.py, engine/cld/cli.py, engine/cld_providers/codex/provider.py, engine/cld_providers/codex/config.py, engine/cld_providers/codex/setup.md
acceptance_test_path: tests/test_n05_codex_config_identity.py
protected_inputs: docs/plans/v0.4.0-review-fixes/N05-CLD-CONTRACT.md
deps:
executor: codex:gpt-6-luna@max+fast

## Independent integration

The lead reviews the diff, runs N05 and adjacent admission/provider tests, then
integrates through CLD's provider-free --integrate path before regenerating.
