# Post-release fixes

## P02: Codex executor model picker

Authorized 2026-09-29. Scope: executor selection for both lead hosts, with
exact CLI-listed IDs and explicit cost-sensitive effort choices. Lead models
remain host selections. No model inference or validation dispatch is authorized
by this task. Use only the local bundled catalog, without a network refresh.

- [x] Add bounded advisory Codex discovery; reject malformed/hidden entries,
  duplicate IDs and unsupported efforts; preserve explicit-ID fallback.
- [x] Add Codex to the unified index and CLI browse/search path, without a
  static default model or a claim of account access/validation/price.
- [x] Default to explicit low where supported, otherwise medium; never
  implicitly select max/ultra. Higher effort and fast remain opt-in.
- [x] Add the read-only installed `scripts/list_models.py --json` entrypoint
  and instructions for Claude and Codex leads.
- [x] Cover exact ID/effort/tier preservation, invalid navigation, discovery
  failure, model-only evidence boundaries and CLI/JSON wiring offline.
- [ ] Complete full offline suite and regenerate all eight standalone bundles
  plus Claude/Codex plugins; verify provider isolation and plugin freshness.
- [ ] Publish the narrow source change; wait for all four cross-platform CI
  jobs, all 24 required test/generator/plugin steps and CodeQL.
- [ ] Refresh the four owned Claude standalone installations from one checked
  commit, with backups/hashes and no active delivery writer.
- [ ] Record source/CI/install evidence in HANDOFF.md and stop for token check.

## P01: Windows restricted-token workspace compatibility

Authorized 2026-09-29 after the published Windows sandbox troubleshooting
follow-up. Scope: current-user permissions on newly created, CLD-owned probe
repos and Git worktrees. Keep the private evidence parent and sandbox mode;
preserve existing denies. No paid provider dispatch or model substitution.

- [x] Reproduce pre-existing-file failures in private validation repos and
  managed worktrees with model-free Codex sandbox checks.
- [x] Add the exact current-user SID's inheritable Modify grant at the owned
  workspace root, without group grants, ACL resets or ownership changes.
- [x] Stop before dispatch if account lookup, SID validation or ACL setup fails;
  retain validation evidence / created worktree.
- [x] Preserve `CLD_PROBE_TIMEOUT` for permission commands.
- [x] Verify the real installed sandbox can edit existing files and blocks
  evidence/Git/source writes; no actual model admission is updated.
- [x] Finish focused failure/boundary/recovery checks, including junction safety:
  88 passed locally, including three opt-in native sandbox checks.
- [x] Regenerate all four Claude and four Codex host bundles from the same source;
  refresh committed Claude plugins through the generator.
- [x] Publish the source fix and updated troubleshooting docs to the online repo.
- [x] Wait for Windows/Ubuntu x Python 3.11/3.14 CI and generator/plugin checks.
- [x] Refresh the four owned Claude standalone installations coherently with
  backups, hash checks and no active delivery writer.
- [x] Record final commit, CI and installation evidence in HANDOFF.md, then stop.

Completed 2026-09-29. Runtime source: public/main `84dd85a`
(working-branch counterpart `c68c0c5`).
[Exact-source CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/36542440084)
passed all four jobs and all 24 required test/generator/plugin steps; CodeQL
also passed. All four installed Claude standalone skills now carry `@84dd85a`
and match the generated files byte-for-byte. Their isolated driver-help checks
and three native sandbox checks against the installed vendored engine passed.
Backups, source hashes and local evidence are recorded in [HANDOFF.md](HANDOFF.md).
Provider calls and model usage/cost: zero; lead counters unavailable. Stop at
this task boundary and obtain token-availability confirmation before more work.

The elevated Codex helper's runtime-path problem remains external. Existing
v0.3.0 release assets are immutable and do not include P01; a new release is
a separate task. Exact `gpt-6-luna@max+fast` live validation remains subject to
explicit authorization and the build's existing admission/budget policy.
