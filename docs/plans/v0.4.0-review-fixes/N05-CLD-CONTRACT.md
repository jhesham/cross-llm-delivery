# N05 executor contract

The missing Codex config bytes allow old validation evidence to admit a different
route or sandbox under the same home path. Acceptance tests use actual Admission
and prepare_dispatch, with offline CLI/executor seams. Do not weaken those tests.

## Design and scope

- Extend the Provider descriptor with an optional, backward-compatible callback
  accepting the repository directory and returning configuration paths. The
  core must merge discovered paths with existing inputs and --validation-config.
- Discovery must happen in context_of each time, not once at prepare_dispatch:
  saved evidence, post-probe checks and the already-admitted factory must detect
  edits, creation, deletion and changes in selected paths. Deduplicate paths.
- Codex owns discovery: CODEX_HOME (relative values resolved consistently from
  repository cwd) or Path.home()/.codex, with config.toml even when missing.
  Ignore the unused default home when CODEX_HOME is selected.
- Conservatively include repo and ancestor .codex/config.toml candidates up to
  the filesystem root. This intentionally over-invalidates some inactive/trust-
  skipped layers; it avoids guessing Codex trust or custom project_root_markers.
  CLD invokes Codex at an isolated Git worktree root; committed project settings
  are copied into that worktree. Untracked config/local executor overrides are
  outside this proof and must be supplied explicitly or pinned via context.
- On POSIX include /etc/codex/config.toml, /etc/codex/requirements.toml and legacy
  /etc/codex/managed_config.toml candidates even when missing. Other managed,
  remote/workspace, command-backed auth and keychain inputs require explicit
  --validation-config / --validation-context. Do not pretend to discover them.
- Parse Codex TOML to collect custom model provider env_key and env_http_headers
  variable names. Cover all declared providers conservatively; preserve the
  existing OPENAI_* patterns. Fail closed on unreadable/invalid config without
  exposing its bytes in errors. Reuse validation_context for hashing and privacy.
- No auth.json/keyring/session/cache/history fingerprint: file token refreshes
  would invalidate evidence unpredictably. Document account switching requires
  --revalidate-models and stable non-secret --validation-context identity.
- CLD's fixed Codex invocation does not select --profile. Profile files not
  selected by that invocation are excluded. If supporting CLI profiles later,
  fingerprint the selected profile and its inputs in the same provider hook.
- Document conservative/excluded inputs in the provider setup notes, with
  current official configuration links. No unrelated provider/release refactor.

## Sources inspected by the lead (2026-10-03)

Installed CLI is codex-cli 0.159.3; exec help advertises --profile as a home-local
profile file, while CLD's invocation currently has no profile argument.
Official configuration guidance:

- [Configuration basics](https://learn.chatgpt.com/docs/config-file/config-basic)
  describes trusted project layers and Unix system config precedence.
- [Advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)
  describes CODEX_HOME and custom project-root markers.
- [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
  defines model_providers env_key and env_http_headers inputs.

These justify input discovery; the implementation need not clone the entire
Codex configuration loader. No new runtime dependencies; Python 3.11+ stdlib.
