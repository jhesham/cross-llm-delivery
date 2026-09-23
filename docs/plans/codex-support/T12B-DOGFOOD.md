# T12B executable dogfood slice

## SLICE: T12B
brief: Implement the bounded T12B contract in docs/plans/codex-support/T12B-CONTRACT.md.
  The lead committed red tests/test_t12b_parity.py before dispatch. Add Codex agent metadata,
  a host-neutral shared reference, portable Codex plugin generation, corrected Claude bundle
  commands and both-platform CI smoke. Preserve default Claude plugin behavior and IDs. Edit
  only the listed files; do not edit tests, contract, engine, provider code or tracked plugins.
  Do not commit, push, install globally or dispatch another provider. Run focused tests only.
executor: opencode:opencode/kimi-k3
complexity: standard
files: generator/build_skill.py, generator/build_plugins.py, skill/SKILL.template.md,
  skill/hosts/codex/SKILL.template.md, skill/hosts/codex/agents/openai.yaml.template,
  skill/references/delivery-core.md, .github/workflows/ci.yml
acceptance_test_path: tests/test_t12b_parity.py
deps:
