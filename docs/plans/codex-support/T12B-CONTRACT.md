# T12B: host metadata and two-host parity contract

The user authorized this child slice after T12A. One exact executor:
`opencode:opencode/kimi-k3`. The lead owns the committed acceptance
`tests/test_t12b_parity.py`. No other model, automatic retry, live provider recursion, or Codex
subagent. Do not start T13 after this slice.

Implement only these source paths:

- `generator/build_skill.py`
- `generator/build_plugins.py`
- `skill/SKILL.template.md`
- `skill/hosts/codex/SKILL.template.md`
- `skill/hosts/codex/agents/openai.yaml.template`
- `skill/references/delivery-core.md`
- `.github/workflows/ci.yml`

The existing `build_one` default/`--host claude-code` still generates the same Claude path,
plugin names and runnable driver. The Claude template may change wording/links to correct its
false `pip install -e .` prerequisite and nonexistent generated-bundle
`python skill/scripts/run_delivery.py` commands, but preserve its functional workflow, model
picker, gates and provider setup. Run commands from the generated skill directory with absolute
plan/repo paths, or use an absolute driver path from another cwd. Both host bundles link one
identical `references/delivery-core.md` with shared, host-neutral gate and authorization guidance.
The Claude generator already copies `skill/references/`; the Codex generator must copy the new
shared reference. Keep detailed host-specific instructions in their existing templates.

Generate Codex-only `agents/openai.yaml` from the verified OpenAI fields: `interface` mapping with
`display_name`, `short_description`, `default_prompt`, and `policy` mapping with `products: [CODEX]`
and `allow_implicit_invocation: false`. The display/default prompt identify the exact provider;
the short description identifies Codex as lead. Do not invent keys, tool dependencies or icons.
This metadata is optional for a standalone skill but included for this Codex variant. Claude
bundles do not receive it.

Add `build_plugins.py --host codex --dist-root <root> --out-root <root>` to package each Codex
bundle under `<out-root>/codex/cross-llm-<provider>/`, with portable root `plugin.json` and
`skills/cross-llm-<provider>/` copied from generated Codex output. Its manifest has the official
schema URL, existing plugin name, VERSION semantic version, description and author; do not claim
submission/readiness without actual validation. Normalize the generated SHA banner so repeated
packaging is byte-stable. The default no-argument Claude plugin generation retains its current
committed layout, names and behavior. Codex mode must not touch any adjacent Claude plugin tree.
No installation, marketplace edits or generated tracked plugin changes in T12B; T13 owns discovery
and installation, T17 owns release artifact refresh.

The two-host × three-provider matrix runs JSON preview through each vendored driver from a
different cwd with empty PYTHONPATH, no source-checkout import and no provider call. No unresolved
template markers remain. Add offline CI steps for `--all --host codex` and Codex plugin packaging
in addition to the existing default smoke. Preserve Windows and Ubuntu test jobs.

Protected: lead acceptance tests, T12B contract/plan, provider code, engine, dependency files,
tracked `plugins/`, `.claude-plugin/`, generated `dist/`, user/global skills and AGENTS.md.
Kimi must not commit/push. Run only focused generator/T12B tests inside the model turn; the lead
will review, integrate and run full cross-platform CI. The parent T12 closes only after all T12B
checks pass. Stop for the user's token confirmation before T13.

Official schema: https://developers.openai.com/plugins/deploy/submission-errors and
https://developers.openai.com/plugins/build/plugins .
