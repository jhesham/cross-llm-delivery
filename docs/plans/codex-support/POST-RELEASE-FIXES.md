# Post-release fixes

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
- [ ] Publish the source fix and updated troubleshooting docs to the online repo.
- [ ] Wait for Windows/Ubuntu x Python 3.11/3.14 CI and generator/plugin checks.
- [ ] Refresh the four owned Claude standalone installations coherently with
  backups, hash checks and no active delivery writer.
- [ ] Record final commit, CI and installation evidence in HANDOFF.md, then stop.

The elevated Codex helper's runtime-path problem remains external. Existing
v0.3.0 release assets are immutable and do not include P01; a new release is
a separate task. Exact `gpt-6-luna@max+fast` live validation remains subject to
explicit authorization and the build's existing admission/budget policy.
