# T12B executable dogfood slice

## SLICE: T12B
brief: Implement exactly docs/plans/codex-support/T12B-CONTRACT.md and make the committed tests/test_t12b_parity.py pass. Add verified Codex agent metadata, one shared reference, portable Codex plugin generation, corrected Claude bundle commands and CI smoke. Preserve default Claude plugin behavior and IDs. Edit only the seven listed files; do not edit tests, contract, engine, providers or tracked plugins. Do not commit, push, install globally, recurse through CLD or dispatch another provider. Run focused tests only and finish promptly.
executor: opencode:opencode/kimi-k3
complexity: standard
files: generator/build_skill.py, generator/build_plugins.py, skill/SKILL.template.md, skill/hosts/codex/SKILL.template.md, skill/hosts/codex/agents/openai.yaml.template, skill/references/delivery-core.md, .github/workflows/ci.yml
acceptance_test_path: tests/test_t12b_parity.py
protected_inputs: docs/plans/codex-support/T12B-CONTRACT.md, pyproject.toml
deps:
