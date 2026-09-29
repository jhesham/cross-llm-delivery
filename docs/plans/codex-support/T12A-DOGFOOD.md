# T12A executable delivery

## SLICE: T12A
brief: Implement exactly docs/plans/codex-support/T12A-CONTRACT.md. Read that contract and tests/test_t12a_generator.py first, then generator/build_skill.py. Add a Codex standalone generator variant with concise YAML-first SKILL template and host references, preserving byte-identical default Claude output. Only modify the three allowed implementation files; do not edit tests, contracts, pyproject, Claude template/plugins or generated outputs. Run tests/test_t12a_generator.py and tests/test_generator.py only. Do not run the full suite, invoke another live model, recurse through CLD, commit or push. Finish the allowed files promptly; stop once focused checks pass.
files: generator/build_skill.py, skill/hosts/codex/SKILL.template.md, skill/hosts/codex/references/codex-workflow.md
acceptance_test_path: tests/test_t12a_generator.py
protected_inputs: docs/plans/codex-support/T12A-CONTRACT.md, pyproject.toml, skill/SKILL.template.md
deps:
executor: opencode:opencode/kimi-k3
complexity: standard
