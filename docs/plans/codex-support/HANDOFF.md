# Current handoff

> **N06 implementation checkpoint (2026-10-03):** all five direct executors
> reject nested dispatch before processes/artifacts and mark production children
> with `CLD_EXECUTOR_DEPTH=1`. Legacy prompts prohibit recursive delegation;
> Cursor's environment adjustments and two-argument injected runners are preserved.
> Exact `codex:gpt-6-luna@max+fast` accepted source `102de90`, checked integration
> `c3e7486`; generated artifacts use committed runtime/documentation `7b1ab0e`.
> N05's four full-suite/platform CI jobs passed before live N06 calls.
> Verification: 53 frozen acceptance/integration cases, 232 adjacent checks,
> 18 packaging checks; counts overlap. Ten bundles have identical 40-file core
> and matching provider bytes; all ten pass standalone recursion checks. Both
> plugin formats regenerated and tracked packages pass freshness checks.
> [Evidence](../v0.4.0-review-fixes/N06-RECURSION-FIX.md),
> [checklist](../v0.4.0-review-fixes/REMEDIATION-N04-N08.md).
> Push and exact-source CI identification are pending at this edit.
> Two calls total: one fresh canary, one implementation; **862,345** executor
> tokens, including **759,040** cached input. Below the 1.2m cumulative estimate;
> the production call exceeded its 600k reservation by 142,247. Cost/lead usage
> unavailable; actual fast routing lacks independent tier telemetry. No retries,
> substitution, installation or release promotion. Global config matches baseline.
> Original run `7de01c823cb64fb1a1151de8fbb9f89c` has full usage; reconciliation
> preserved its backup and accepted commit. Integration-only run
> `cb38fa7314c94dc68f5e6c6ebe082114` derives production usage only, excluding the
> canary: do not report that ledger's 742,247 as the whole slice total.
> Broad red integration encountered a separate
> [F01 diagnostic false-positive](../v0.4.0-review-fixes/FOLLOWUP-PYTEST-DIAGNOSTICS.md);
> use each precise frozen slice suite for integration and independently run adjacent
> checks until F01 is fixed. N06's full adjacent group passed on integrated source.
> **Stop after N06.** N07/N08 remain authorized through exact Luna/max/fast,
> pending token availability and green N06 CI. Check current exact-spec evidence
> first and reuse if fresh. Keep the Windows temp-access stop instruction in briefs.
> Earlier checkpoints below are historical and superseded where they conflict.

> **N05 implementation checkpoint (2026-10-03):** Codex local configuration
> and custom-provider credential references now key validation evidence, including
> missing-file states. Discovery is recomputed before factory use; invalid TOML
> and non-literal absolute homes fail closed. Exact `codex:gpt-6-luna@max+fast`
> implemented the five-file contract through CLD: accepted `0294ab6`, independent
> integration `8ab0029`, final reviewed runtime `8320281`. N04 CI is green on all
> four jobs. Final N05 focused checks: 84 passed; packaging/bundle checks: 18
> passed. All ten bundles regenerated from committed runtime, 40 core files match,
> tracked plugins are fresh, and both Codex bundles pass standalone offline guards.
> [Evidence and usage](../v0.4.0-review-fixes/N05-CODEX-CONFIG-FIX.md),
> [checklist](../v0.4.0-review-fixes/REMEDIATION-N04-N08.md).
> Pushed source/artifacts `0d2eb08` to public `refactor/codex-support`.
> [Exact-source CI run 37119733253](https://github.com/jhesham/cross-llm-delivery/actions/runs/37119733253)
> is queued; all four cross-platform results remain pending. The follow-up
> checkpoint commit changes documentation only.
> Two live calls total: one validation, one implementation; **2,457,594** executor
> tokens, including **2,220,544** cached input. This exceeded the 1,200,000 admission
> estimate; cost and lead usage unavailable. No paid retry or substitution.
> Actual priority routing lacked independent tier telemetry. Global Codex config
> matches its pre-dispatch digest; no install, release or persistent setting change.
> N06–N08 remain pending. **Stop for token availability before N06**, and require
> green N05 CI. The earlier canary context is stale under final automatic inputs;
> check current exact-spec evidence and use a bounded fresh canary only if needed.
> Brief the executor to report Windows pytest temp-access errors promptly instead
> of repeated self-test retries; independent CLD acceptance remains the gate.
> Earlier checkpoints below are historical and superseded where they conflict.

> **N04 implementation checkpoint (2026-10-03):** runtime `6b9cc7c` fixes frozen
> acceptance import isolation; failing tests were committed first (`a3ca85b`).
> Final regressions: 20 passed; broader adjacent group: 201 passed; packaging,
> bundle and parity checks: 18 passed. Counts overlap. All five providers for
> both hosts were regenerated from that committed runtime; 40 core files match
> across all ten bundles, tracked plugins are fresh, and the standalone Codex
> bundle judges disagreeing live/frozen sources correctly outside the checkout.
> [Evidence](../v0.4.0-review-fixes/N04-IMPORT-ISOLATION-FIX.md) and
> [implementation checklist](../v0.4.0-review-fixes/REMEDIATION-N04-N08.md).
> Pushed `215bae1` to public `refactor/codex-support`.
> [Exact-source CI run 37115459230](https://github.com/jhesham/cross-llm-delivery/actions/runs/37115459230)
> is queued; its four full-suite/platform results remain pending. No live executor
> calls or global installs; executor tokens 0, lead token usage unavailable.
> N05–N08 are authorized through CLD with exact `codex:gpt-6-luna@max+fast`.
> Stop at N04 for the user's token-availability check; require green N04 CI
> before dispatching N05. v0.4.1 is already published; these fixes are unreleased.
> Earlier checkpoints below are historical and superseded where they conflict.

> **Full-build review checkpoint (2026-10-03):** reviewed `f019689` (0.4.1
> preparation). Previous N01–N03 fixes are present. Five additional findings,
> reproductions and corrective checklists are recorded in
> [the full review](../v0.4.0-review-fixes/FULL-REVIEW-2026-10-03.md): N04 **P1**
> acceptance imports can escape the frozen candidate; N05–N08 **P2** cover
> Codex configuration identity, three-provider recursion prevention, native-only
> Windows OpenCode discovery, and Antigravity's POSIX cwd.
> Exact-source [CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/37095765709)
> passed all four full-suite/generator/packaging jobs. Local isolated probes
> reproduced the new cases; the redundant local full run was deliberately stopped
> after 17% progress (no final pass claimed), once exact-source CI was verified.
> Claude's separate pytest run was left untouched. Review documents only changed;
> no runtime edits, inference, installation, commit or push. Public `main` was
> still `429b9d0` at the remote check; promotion remains Claude's work. Next:
> implement N04 first when authorized. Review token usage unavailable.
> Earlier checkpoints below are historical and superseded where they conflict.

> **OpenCode N03 checkpoint (2026-10-03):** inline-referenced credentials/routes
> now key validation evidence. Eight new regression cases and the relevant
> suites pass (67 total); isolated OpenCode bundles pass for both hosts.
> [Fix evidence](../v0.4.0-review-fixes/N03-OPENCODE-INLINE-FIX.md).
> OpenCode-only plugin regenerated; concurrent Claude work untouched. Combined
> CI/release integration pending; no live calls or global installs.

> **Re-review checkpoint (2026-10-03):** reviewed updates through `96e7479`
> (published v0.4.0 runtime `429b9d0`). Original R01/R02/R04–R07 cases now pass;
> file-based R03 is fixed but its inline-config variant remains open. Three
> findings and corrective tasks are in [the re-review](../v0.4.0-review-fixes/REVIEW-2026-10-03.md).
> Local verification: 250 focused checks passed; published Windows/Ubuntu CI,
> packaging and CodeQL checks are green. Engine/release unchanged; no paid
> provider inference. Fix implementation not started; review token usage unavailable.
> Current publication: [v0.4.0 record](../v0.4.0-review-fixes/PUBLICATION-0.4.0.md).

> **Review checkpoint (2026-10-01):** Claude Code's v0.3.1 updates were reviewed
> through `453e31e`. Seven open findings, including two high-priority GC safety
> defects, are recorded in [the review](../v0.3.1-fixes/REVIEW-2026-10-01.md).
> Focused checks: 148 passed; published four-platform jobs and packaging checks
> are green. Engine and release unchanged; no provider inference performed.
> Fix implementation has not started. Token usage for this review is unavailable.

> **Superseded (2026-10-01):** v0.3.1 is published. Current work lives in
> [docs/plans/v0.3.1-fixes/](../v0.3.1-fixes/) — see its
> [publication record](../v0.3.1-fixes/PUBLICATION-0.3.1.md). Next: the Claude
> Code executor (v0.4.0). The history below is retained unchanged.

## Completed follow-up: P02 executor picker (2026-09-29)

Codex executor model-picker support is complete. The implementation discovers
only the local bundled CLI catalog, adds exact IDs/efforts to the shared index
and CLI browse/search, and vendors a read-only `scripts/list_models.py --json`
entrypoint for both lead hosts. Codex defaults explicitly to low where listed,
otherwise medium; max/ultra and fast are opt-in. Catalog rows are advisory,
untested and metered-unknown; model-only evidence never admits a new effort/tier.
Lead selection remains outside CLD. No inference/validation calls authorized.

Runtime source: public/main `49b1a3fdf22de99eca8158d1989d9ff6c878dc09`
(working-branch counterpart `7fb101a`). All 146 focused checks passed. The full
local offline suite exited 0 (1,006 collected tests; four skips). All eight
bundles share 40 core files, retain provider isolation and pass 16 isolated help
checks. Both Codex bundles list exact visible CLI IDs without installation or
inference. The installed local catalog includes GPT-6 Astra/Sol/Luna and
GPT-5.6 Sol/Terra/Luna, with explicit low defaults; no other combinations guessed.

[Exact-source CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/36571779679)
passed all four Windows/Ubuntu x Python 3.11/3.14 jobs and all 24 required
test/generator/plugin steps; [CodeQL](https://github.com/jhesham/cross-llm-delivery/actions/runs/36571779516)
passed. Two initial existing timing failures (Ubuntu release-wrapper startup
timeout and Windows concurrent-reader progress assertion) cleared on the
targeted failed-job retry with no source changes. Both also passed local
focused rechecks and the full suite. CI proof checks each job's latest attempt.

All four owned global Claude standalone skills match generated `@49b1a3f`
bundles byte-for-byte. Eight installed isolated help checks and the read-only
Codex picker check passed (seven advisory rows). Installation found no active
delivery writer. Former `@84dd85a` installations are preserved at:
`C:\Users\Administrator\.claude\skill-backups\p02-20260929-230108-898da3374e9d40efb874adf554af8cae`.
Restart Claude Code to load the updated entry instructions. No new global
Codex skill installation or release-asset replacement was requested.

Local evidence: `.cld/environment/p02-local-results.json`, `p02-bundle-proof.json`,
`p02-ci-final.json`, `p02-install.json` and `p02-installed-proof.json`. No model
inference, admission update or production dispatch; executor usage/cost zero,
lead counters unavailable. Live menu UI and newly selected models require their
own evidence; discovery is not admission or an entitlement/pricing claim.
See the [completed P02 checklist](POST-RELEASE-FIXES.md#p02-codex-executor-model-picker).
**Stop here and obtain token-availability confirmation before another task.**

Updated 2026-09-29. **T01–T20 and M1–M6 complete; v0.3.0 published and promoted;
post-release P01 and P02 complete.**
[Release](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.3.0) · [publication evidence](PUBLICATION-0.3.0.md).

Immutable tag/source: `81327cc90271bd6126e85e20533e1d9bb874ed08`.
[All four exact-source Windows/Ubuntu Python 3.11/3.14 CI jobs and all 24
required steps passed](https://github.com/jhesham/cross-llm-delivery/actions/runs/36531725348). Seven release artifacts plus manifest/checksums
were uploaded; all nine downloads match local SHA-256 hashes. Local files:
`dist/release-v0.3.0/`; operational evidence: `.cld/publication/`.
The release publication signoff changed planning documents only. Main now also
carries the separately checked P01 runtime fix below; the immutable v0.3.0
release source and assets are unchanged.

The initial promotion exposed wrapper removal from the public tree. Fix
`7c7abba` retains checked release/sync wrappers; the real local-remote regression
was red before the fix, and all 64 focused release checks pass afterward.
The corrected promoted/tagged commit passed the full four-job suite. No force
push, provider-mirror publication, global installation change or model call.
Lead counters unavailable; provider usage/cost zero.

All four installed Claude standalone skills now come coherently from P02
source `49b1a3f`, with their former `84dd85a` copies backed up and hashes
verified. Downloadable v0.3.0 bundles still come from the tagged revision and
predate P01/P02. Restart the host to load the updated skills. Preserve active state
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
Verified all other parsed settings unchanged. Shell execution and
sandbox-created-file create/edit/read/delete pass in an ordinary workspace.
All checks used `codex sandbox`, without model calls.

**Pre-P01 operational blocker (resolved below):** Python 3.13.13 creates
private `tempfile.mkdtemp` ACLs. CLD's validation `probe-*/repo` layout starts
in the unelevated sandbox but cannot edit `calc.py` (`PermissionError`).
Normal-workspace success is not a successful CLD validation canary.
See [known issues](../../../KNOWN-ISSUES.md#codex-windows-sandbox-setup).

The next authorized slice was temporary-repo/sandbox compatibility, completed
as P01 below with a model-free regression before any paid retry. A model-free
Codex shell/edit preflight remains a possible follow-up. The initial environment
follow-up changed no engine, bundle, skill, release or validation ledger;
no provider calls. Provider usage/cost zero;
lead counters unavailable.

User-requested documentation was published to `public/main` in `2e4d7f7`
(working-branch counterpart `ed99f09`). The public-facing guide is
[Codex Windows sandbox troubleshooting](../../../docs/CODEX-WINDOWS-TROUBLESHOOTING.md),
linked from README and known issues. The original guide included config backup,
scoped fallback, model-free shell/edit checks, rollback and the then-unresolved
workspace blocker. P01 updates it with the source fix. At original publication,
GitHub API downloads of all four documentation files matched committed
local content; relative links resolve and both documented smoke checks pass.
[Exact documentation-source CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/36538431225)
and [CodeQL](https://github.com/jhesham/cross-llm-delivery/actions/runs/36538429129)
provide automated results. Publication verification is retained under
`.cld/environment/docs-publication-verification.json`.

## P01 Windows workspace compatibility fix (complete)

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

Published runtime source: public/main
`84dd85acefd8f64a1d1e26dfd991ca2848f5a0eb`; working-branch counterpart
`c68c0c5b30768c215fca819510fc9914bdbb13fe`.
[Exact-source CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/36542440084)
passed Windows/Ubuntu x Python 3.11/3.14: all four jobs and all 24 required
test/generator/plugin steps. [CodeQL](https://github.com/jhesham/cross-llm-delivery/actions/runs/36542439735)
passed. The closure commit changes planning documents only.

All eight host/provider bundles were rebuilt from `84dd85a`; 39 shared core
Python files match across them, and committed Claude plugin freshness passed.
After CI passed and confirming no active delivery writer, installed all four
global Claude standalone skills coherently from that source. Installed files
match generated hashes; all four isolated driver-help checks passed. Three
model-free sandbox checks against the installed Codex skill's vendored engine
also passed: private-probe edits/evidence protection, managed-worktree edits/
source preservation, and exclusion of external junction targets from ACL changes.

The four previous `59722b5` installations are backed up at
`C:\Users\Administrator\.claude\skill-backups\p01-20260929-183119-51a8549158404fca9d87db6c1fc10f41`.
Retained local proofs: `.cld/environment/p01-ci-final.json`,
`p01-bundle-coherence.json`, `p01-install.json`, `p01-installed-smoke.json`,
`p01-config-check.json` and `p01-final.json` under the same directory. Restart
Claude Code to load the new skills. No real model call or admission-store
update; provider usage/cost zero, lead counters unavailable. Global Codex config
still uses the approved `unelevated` setting, with all other settings preserved.

The elevated-helper setup problem remains external; this engine fix does not
repair it. At P01 closure, exact Luna/max/fast live delivery remained unverified;
later downstream evidence is recorded below. v0.3.0 release assets remain
unchanged. A new release remains separate work.
Stop here; obtain token-availability confirmation before starting another task.

## Public issue audit and later live-use evidence (2026-09-29)

[Issue audit](ISSUE-AUDIT-2026-09-29.md) reviewed all seven open issues.
Closed #11 (per-run telemetry) as completed after 14 focused status/history/
build-isolation checks passed. #8–#10 and #12 still have unmet requirements;
#13's Codex portion is complete but the broader adapter invitation remains;
#14 is a living roadmap. Six issues remain open.

A later downstream Windows build recorded three successful first-attempt
production slices with `codex:gpt-6-luna@max+fast`, all 15 slice acceptance tests
passing and verified integration complete. Live use with that requested
combination is now observed. CLI logs provide no actual-tier acknowledgement,
so backend fast service remains unproven; platform/discovery/interruption
limitations are not inferred away. The audit publishes only aggregate evidence,
not downstream code, prompts or raw logs. No provider dispatch was made for
this audit. Provider usage/cost zero; lead counters unavailable. Stop at the
token checkpoint before another task.

## Codex availability metadata update (2026-09-29)

At the user's request, updated the GitHub About description to list Codex among
the four executor providers and Claude Code or Codex as architect/judge lead.
Added a [maintainer comment to #13](https://github.com/jhesham/cross-llm-delivery/issues/13#issuecomment-5889824988)
confirming the Codex adapter is available, its exact executor syntax and the
recorded Windows live build. The comment distinguishes requested fast service
from actual-tier acknowledgement, links installation/troubleshooting, and notes
that v0.3.0 downloads predate P01. #13 stays open for other provider contributions.
GitHub API readback verified the exact description and comment body; proof is
`.cld/environment/issue13-metadata-verification.json`. No runtime changes or
provider calls; lead counters unavailable. Stop at the token checkpoint.

## PR #15: CI Python setup maintenance (complete, 2026-09-29)

With explicit user authorization, refreshed the Dependabot PR against current
main `1cdbdab` through GitHub's branch-update API. Its only diff remained
`actions/setup-python@v6` to `@v7`; the current Windows/Ubuntu x Python 3.11/3.14
matrix and all test/generator/plugin checks were preserved.
[Fresh PR CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/36565957054)
passed all four jobs and all 24 required steps on head
`915314830a7dbbdf2202c5dcb9d31fc083e261df`; CodeQL also passed. Merge guards
required unchanged main/head and completed successful checks; no policy bypass.

[PR #15](https://github.com/jhesham/cross-llm-delivery/pull/15) was squash-merged
at `2026-09-29T12:29:52Z` as `1d929c1abdc5eea2af1c2b2e4505170d59081eba`.
The merged tree matches the refreshed, tested head exactly. Synced the one-line
workflow change to the local working branch (`1980ca8`) and the owned main
worktree. The subsequent signoff changes this handoff only. Local proofs:
`.cld/environment/pr15-refresh.json`, `pr15-ci-final.json` and `pr15-final.json`
under the same directory. No CLD runtime or installed bundle update was needed;
no provider calls, provider usage/cost zero, lead counters unavailable. Stop
here and confirm token availability before another task.
