# Codex sources and compatibility baseline

Checked 2026-09-09. Official URLs below were opened during planning; some older developers.openai.com Codex URLs redirect to learn.chatgpt.com. Recheck version-sensitive details at T13 and T15. Design choices in ARCHITECTURE.md are project proposals, not claims that OpenAI supplies those CLD features.

| Source | Verified point relevant to this plan |
|---|---|
| [Build skills](https://learn.chatgpt.com/docs/build-skills) | Skills contain SKILL.md with name/description, optional scripts/references and `agents/openai.yaml`. Codex supports standalone skills, progressive loading, explicit invocation, and repository/user `.agents/skills` discovery. |
| [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | Codex loads layered repository instructions. This supports a small maintainer entrypoint; it does not justify replacing a user's instructions. |
| [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) | `codex exec` supports JSONL events and explicit sandbox settings. Successful turn events may include usage. This is the optional provider boundary, not a requirement for Codex as lead. |
| [Plugins](https://learn.chatgpt.com/docs/plugins) | Plugin support differs by surface; current documentation excludes the IDE extension. Standalone skill support is therefore required for the IDE route. |
| [Package your plugin](https://developers.openai.com/plugins/build/plugins) | Current docs describe portable root `plugin.json`, OpenAI-specific extensions, and supported `.codex-plugin/plugin.json` compatibility manifests. Marketplace resolution/layout is distinct from Claude's existing package. |

**Local read-only evidence**

`Get-Command codex` resolves to the installed Codex desktop bundle's `codex.exe`. `codex --version` reported **codex-cli 0.153.4**. The environment printed a home/PATH-alias warning under the sandbox; version/help were still available. Authentication and live execution were not tested, so installed does not mean ready for a paid or authenticated canary.

The observed `codex exec --help` supports stdin via `-`, `--json`, `--cd`, `--model`, `--sandbox workspace-write`, `--ephemeral`, and `--output-last-message`. It also exposes dangerous bypass/config-skipping flags; their existence is not permission or a reason to use them. T15 must reconcile actual installed behavior with the current official contract rather than freeze all flags from this machine.

**Compatibility decisions to verify in implementation**

- Host scope: Codex CLI and IDE standalone skills are required. App/plugin support gets explicit surface/version evidence. Do not claim all ChatGPT surfaces can execute local shell scripts simply because a plugin is discoverable there.
- Installer: repository `.agents/skills` is the primary documented path; user-scoped location and plugin marketplace schema must be verified on selected versions. Internal plugin caches are implementation details, not install targets.
- Plugin format: select a validated portable or supported compatibility manifest at T13; record why. Do not create two conflicting sources of metadata or translate a Claude manifest by filename substitution alone.
- Provider scope: Codex executor is optional. Exact model/effort availability and cost depend on installed CLI/config/account and require evidence; no model/pricing recommendation is embedded in this plan.
- Permissions: local CLI help and docs establish flags, not whether a host policy permits them. Test restricted write roots and denied subprocess/network access explicitly.

**Refresh record template**

```text
Date / task:
CLI and host version / platform:
Official page checked:
Observed capability or changed field:
Fixture / test / installer impact:
Decision and limitation:
```
