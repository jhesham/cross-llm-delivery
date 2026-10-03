# N03 — OpenCode inline validation context

Implemented 2026-10-03. Scope is the OpenCode finding in
[the re-review](REVIEW-2026-10-03.md); concurrent Claude fixes are owned separately.

`Provider.config_env` now collects `{env:NAME}` references from
`OPENCODE_CONFIG_CONTENT` as well as configuration files. The existing admission
context hashes those referenced values, so changing or removing a credential or
endpoint invalidates prior evidence even when inline JSON is unchanged. Values
are not recorded in diagnostics. Unrelated lead-session variables remain ignored.

This fixes inline references; it does not claim support for every other OpenCode
configuration/authentication source mentioned in the broader review checklist.

- [x] Reproduce the defect with failing credential, endpoint and merged-source tests
      (3 failed, 4 passed before the implementation).
- [x] Read inline and file references together, sorted and deduplicated.
- [x] Test credential/endpoint changes and removal, secret redaction, empty/unset
      inline configuration, and unrelated-session stability.
- [x] Test cached admission: a changed inline credential blocks under deny policy
      without executing a validation probe.
- [x] Relevant validation/admission/OpenCode suites: **67 passed in 2.41 seconds**.
- [x] Generate OpenCode bundles for Claude Code and Codex in `dist/n03-inline-env`;
      both generator smoke checks pass.
- [x] Refresh the committed OpenCode plugin through the generator, scoped to that
      provider to avoid overwriting concurrent Claude changes. Provider matches source.
- [x] Run isolated `python -I -S` inline-evidence smoke checks on both generated
      bundles; changing a synthetic key changes the fingerprint.
- [ ] Combined-source cross-platform CI and coherent all-provider regeneration
      before a corrective release, coordinated with the Claude changes.

Only OpenCode source/tests/plugin and this checkpoint are included in the scoped
commit. Shared handoff/re-review edits remain available for integration by the
concurrent build owner. No global installs, live model calls or release changes.
Lead token usage is unavailable. Stop after this fix; no next slice started.
