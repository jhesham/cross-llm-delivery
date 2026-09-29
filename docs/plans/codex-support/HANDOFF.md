# Current handoff

Updated 2026-09-29. **T01–T20 and M1–M6 complete; v0.3.0 published and promoted.**
[Release](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.3.0) · [publication evidence](PUBLICATION-0.3.0.md).

Immutable tag/source: `81327cc90271bd6126e85e20533e1d9bb874ed08`.
[All four exact-source Windows/Ubuntu Python 3.11/3.14 CI jobs and all 24
required steps passed](https://github.com/jhesham/cross-llm-delivery/actions/runs/36531725348). Seven release artifacts plus manifest/checksums
were uploaded; all nine downloads match local SHA-256 hashes. Local files:
`dist/release-v0.3.0/`; operational evidence: `.cld/publication/`.
The publication signoff commit changes planning documents only; current main
may carry those docs after the immutable release source.

The initial promotion exposed wrapper removal from the public tree. Fix
`7c7abba` retains checked release/sync wrappers; the real local-remote regression
was red before the fix, and all 64 focused release checks pass afterward.
The corrected promoted/tagged commit passed the full four-job suite. No force
push, provider-mirror publication, global installation change or model call.
Lead counters unavailable; provider usage/cost zero.

All four previously installed Claude standalone skills remain coherently from
`59722b5` with their T20B backups/hashes; release engine/skill sources match that
candidate. New downloadable bundles all come from the tagged revision. Restart
the host after replacing a complete coherent skill set. Preserve active state
before rollback; old engines cannot read schema-2 ledgers. Installed-copy edits
and mixed engine versions remain unsupported.

Exact `codex:gpt-6-luna@max+fast` parsing/validation identity and warning/mismatch
failure behavior are covered offline. Fast-tier live delivery, refreshed Claude
picker/fourth Codex-plugin discovery, live Claude-lead execution, live provider
mid-process interruption, Ubuntu Codex flags/live POSIX and macOS remain
unverified. [Support matrix](T19B-MATRIX.md) and
[migration/recovery](../../MIGRATION.md) retain those boundaries. Dispatch remains
600 seconds with explicit timeout configuration; no automatic usage/deadline
increase or silent model/tier substitution.

## Post-release Windows environment follow-up (2026-09-29)

The completed T01–T20 release remains unchanged. A subsequent user build
reported failed Codex shell startup outside CLD; CLD correctly blocks admission.
Local model-free checks reproduce elevated-helper failure on standalone CLI
0.158.0 / Windows Server 2025. Logs point to runtime access validation of a
291-character path; the specific CLI-version regression remains unproven.

With explicit user approval, backed up the global Codex config and changed
only `windows.sandbox` from `elevated` to `unelevated`. Backup:
`C:\Users\Administrator\.codex\config.toml.before-unelevated-20260929T073523Z.bak`.
Verified all other parsed settings unchanged. Shell execution and file
create/edit/read/delete pass with a workspace directory's inherited ACLs.
All checks used `codex sandbox`, without model calls.

**Remaining operational blocker:** the installed Python 3.13.13 creates
private `tempfile.mkdtemp` ACLs. CLD's validation `probe-*/repo` layout starts
in the unelevated sandbox but cannot edit `calc.py` (`PermissionError`).
Normal-workspace success is not a successful CLD validation canary.
See [known issues](../../../KNOWN-ISSUES.md#codex-windows-sandbox-setup).

Next authorized slice should address temporary-repo/sandbox compatibility
with a model-free regression before any paid retry. Also consider a model-free
Codex shell/edit preflight to avoid spending on a broken local setup. No
engine, generated bundle, installed skill, release or validation ledger was
changed in this follow-up; no provider calls. Provider usage/cost zero;
lead counters unavailable.

User-requested documentation is published to `public/main` in `2e4d7f7`
(working-branch counterpart `ed99f09`). The public-facing guide is
[Codex Windows sandbox troubleshooting](../../../docs/CODEX-WINDOWS-TROUBLESHOOTING.md),
linked from README and known issues. It includes config backup, scoped fallback,
model-free shell/edit checks, rollback and the unresolved private-directory
blocker. GitHub API downloads of all four documentation files match committed
local content; relative links resolve and both documented smoke checks pass.
[Exact documentation-source CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/36538431225)
and [CodeQL](https://github.com/jhesham/cross-llm-delivery/actions/runs/36538429129)
provide automated results. Publication verification is retained under
`.cld/environment/docs-publication-verification.json`.

## P01 Windows workspace compatibility fix (in progress)

User explicitly authorized the compatibility fix after documentation publication.
See [post-release checklist](POST-RELEASE-FIXES.md). Further diagnosis shows that
administrator-created pre-existing files, including normal Git worktrees, also
depend on an Administrators grant disabled by the restricted token. Merely
creating ordinary inherited-permission directories is not sufficient.

`cld._windows_workspace.prepare_windows_workspace` resolves the exact current
user SID and adds only inheritable Modify access to a newly owned workspace.
Validation and Git worktree creation call it before dispatch. Probe parents,
evidence, other users, existing denies and global sandbox configuration are
preserved. Setup failures block before a provider call and retain diagnostics.
The helper respects the configured probe timeout.

The two installed-Codex, model-free regressions were red before the change and
green afterward. All 88 focused checks passed, including the three native
sandbox checks for private probes, managed worktrees and junction safety.
Account/SID/ACL errors prevent dispatch and retain diagnostics/candidates.
Evidence: `.cld/environment/windows-workspace-focused.xml` and retained probes
under `.cld/sandbox-regressions/`.

All eight host/provider bundles were rebuilt; the four committed Claude plugin
copies passed generator freshness. The four global Claude standalone engine
copies still match their owned `59722b5` source (provider-pruned file counts
38/39); no active installed delivery driver was observed. Await exact-source
cross-platform CI before coherent installation with backups. No real model
call or admission-store update. Do not start a live canary or another task
at closure; v0.3.0 release assets remain unchanged.
