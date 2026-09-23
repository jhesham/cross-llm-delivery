# T12A: Codex standalone generator contract

One executable child slice. Lead-owned committed acceptance is `tests/test_t12a_generator.py`.
Exact pinned executor is `opencode:opencode/kimi-k3`; no fallback or parallel calls.

Implement only:
- `generator/build_skill.py`
- `skill/hosts/codex/SKILL.template.md`
- `skill/hosts/codex/references/codex-workflow.md`

`build_one(provider, out_root=..., host="claude-code")` and CLI `--host claude-code|codex`.
Omitted host remains Claude's current output directory, text, banner, IDs, README and vendored files.
An explicit Claude host must produce the same bytes as the omitted default. Unknown host fails before
creating/deleting output. Codex output goes to `<out_root>/codex/cross-llm-<provider>` and never wipes
an adjacent Claude skill. `--all --host codex` builds all three providers there.

For Codex, `SKILL.md` starts with YAML frontmatter on the first line: a short unique
`cross-llm-<provider>` name and concise description that states when to use it. The provenance
comment follows the closing `---`. Keep the entry skill under 130 lines and 9,000 characters;
provider setup, CLI details and broader workflow should be linked from references. Codex is named
as the lead; the provider is the implementation executor. Use bundle-relative
`python scripts/run_delivery.py` examples, `--json` gates and explicit authorization. Respect the
user's existing project instructions; do not install or overwrite them. Never instruct `pip install
-e .`, use source-checkout paths, require an Anthropic key, claim provider cost is free, or claim
host discovery has been verified. Do not silently choose or switch models.

Generate `references/codex-workflow.md` from the Codex host source. Copy the selected provider's
`setup.md` and `SKILL.fragment.md` into `references/provider-setup.md` and
`references/provider.md`; do not inline long provider catalogs in the entry skill. The existing
vendored driver and engine must run a JSON preview from another cwd with empty `PYTHONPATH`, no
source checkout import and no provider/API calls. Default bundle smoke still runs.

Existing tests, Claude plugins, publish metadata, dependency files and generated tracked bundles are
protected. Do not change `skill/SKILL.template.md`; shared extraction/Claude editorial parity belongs
to T12B. Kimi must not alter tests, contract, provider modules, permissions or dependencies, invoke a
live provider recursively, commit, or push. The lead reviews and integrates the candidate. Run only
focused acceptance and existing generator tests; do not run the full suite inside the OpenCode turn.

Gate: the nine new acceptance cases and existing generator/Claude parity checks pass. The full
T12 parent stays open for T12B's metadata, plugin and final 2-host × 3-provider matrix review.
