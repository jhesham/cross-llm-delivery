# T13 execution slices

T13 is split to keep one Kimi K3/OpenCode production attempt bounded per checkpoint. Complete the user token checkpoint after each child slice. Parent T13 remains open until both children and its gate pass.

## T13A — Safe standalone installer

- [ ] Commit an executable contract and red acceptance before dogfood dispatch.
- [ ] Add an explicit, previewable installer for generated Codex bundles into `<scope-root>/.agents/skills/<skill-name>`; the scope root is always selected by the caller and may be a repository or user home.
- [ ] Preserve unrelated entries and local edits; reject collisions, unsafe symlinks/path escapes, invalid bundles, and read-only targets. Record ownership and file hashes to support safe update/uninstall.
- [ ] Test fresh install, preview, update, collision, local edit, uninstall, path spaces, nested repository paths, and read-only handling in disposable roots. Do not install into the real user home.
- [ ] Document the repo and user standalone routes in `INSTALL.md`, including explicit Codex invocation and generated script resolution.
- [ ] Lead review, full offline suite, Windows/Ubuntu CI and generator smoke; commit/push evidence and pause.

## T13B — Marketplace and host discovery

- [ ] Generate a Codex marketplace catalog alongside the portable plugin packages using current official schema and without changing the Claude plugin route.
- [ ] Add concise repository `AGENTS.md` maintainer guidance.
- [ ] Exercise isolated plugin catalog and standalone skill discovery with installed Codex, including a nested cwd and script path resolution; record host/version/paths and any surface limits.
- [ ] Finish the remaining T13 checkboxes and gate; full offline suite, Windows/Ubuntu CI/generator smoke, evidence, commit/push, and pause before T17.

Source: [T13 plan](04-CODEX-HOST.md#t13--codex-installation-and-discovery). Codex installation locations were refreshed from the [official Build skills guide](https://learn.chatgpt.com/docs/build-skills) on 2026-09-23: repository ancestors are scanned through Git root and user skills live at `$HOME/.agents/skills`. [Plugin packaging](https://developers.openai.com/plugins/build/plugins) and [surface support](https://learn.chatgpt.com/docs/plugins) were refreshed the same day; the IDE extension does not support plugins.
