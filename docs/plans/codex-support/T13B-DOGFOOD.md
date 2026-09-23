# T13B executable dogfood slice

## SLICE: T13B
brief: Implement exactly docs/plans/codex-support/T13B-CONTRACT.md and make the committed tests/test_t13b_marketplace.py pass. Generate a deterministic Codex local marketplace catalog alongside the portable plugin packages; add short repo AGENTS.md maintainer guidance; document the local plugin route and CI catalog checks. Edit only the four listed files. Do not edit tests, contract, engine, standalone installer, tracked Claude plugins or user-home files. Do not commit, push, install plugins, invoke a Codex model, recurse through CLD or dispatch another provider. Run focused tests only and finish promptly.
executor: opencode:opencode/kimi-k3
complexity: standard
files: generator/build_plugins.py, INSTALL.md, .github/workflows/ci.yml, AGENTS.md
acceptance_test_path: tests/test_t13b_marketplace.py
protected_inputs: docs/plans/codex-support/T13B-CONTRACT.md, pyproject.toml
deps:
