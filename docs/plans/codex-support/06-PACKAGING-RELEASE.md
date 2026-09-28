# Phase 6 — Packaging, compatibility, and release readiness

Outcome: conventional Python installs and both host bundles work from a clean environment; releases stop on failures and carry honest support claims. T17 deliberately occurs before T14 in the recommended sitting order.

## T17 — Wheel, bundles, and CI

Dependencies: T12. Estimate: 8–12k. Files: `pyproject.toml`, generators, `.github/workflows/ci.yml`, packaging tests, optional dependency tests.

- [x] Include required provider resources in wheel/sdist package data and verify both distributions. Ensure the engine can load all installed providers without the source checkout on sys.path. [T17A evidence](T17A-EVIDENCE.md).
- [x] Build wheel, install into a clean environment, and smoke import providers/CLI. Clear editable/source-path leakage. Test the supported core with only required dependencies, plus pytest for deterministic target tests; optional behavioral/OTel imports must remain optional. [T17A](T17A-EVIDENCE.md) and [T17C](T17C-EVIDENCE.md) evidence.
- [x] Build every required host/provider skill combination into a fresh output root, import it alone, and validate metadata/entrypoint paths. Include Codex plugin manifests for intended supported surfaces. [T17B evidence](T17B-EVIDENCE.md).
- [x] Regenerate committed bundles from source and make CI fail on drift. Compare normalized banners intentionally; do not hand-edit generated engines. [T17B evidence](T17B-EVIDENCE.md).
- [x] CI matrix: Python minimum 3.11 and a current supported version selected at implementation; Windows and Ubuntu required. Add macOS coverage if claiming it, otherwise state its unverified scope. Keep live models excluded from default CI. Python 3.11/3.14 × Windows/Ubuntu; [T17C evidence](T17C-EVIDENCE.md).
- [x] Add plan/result/state-schema compatibility fixtures, wheel import checks, bundle freshness checks, and the new real-Git regression suite. Remove all temporary xfails once fixed. [T17C evidence](T17C-EVIDENCE.md); T01–T13 real-Git suite remains active, and no T17 xfails remain.

**Gate:** R07/A05 pass and the defects closed through T17 remain testable without paid calls; R13 belongs to T18 and remains open until its release-command gate. Record wheel filename/hash, build command, isolated import result, bundle matrix, and CI environments. A wheel that merely builds does not satisfy this gate.

## T18 — Checked release automation

Dependencies: T17. Estimate: 8–12k. Files: `release.ps1`, `sync-public.ps1`, `generator/publish.py`, new release-script tests/fixtures.

- [x] Wrap or explicitly check every critical native command: generation, Git worktree/add/commit/tag/push, gh operations, and mirror/copy steps. Stop with the failing command/result before subsequent mutations.
- [x] Select CI by expected repository, workflow, branch, and exact pushed SHA. Handle no run found, queue delay, cancelled/failing runs, and timeout explicitly; never substitute the latest unrelated run.
- [x] Make dry-run fully reviewable with exact refs/artifacts/destinations. Ensure build/tag/version/manifest values agree and reject unintended existing tags or remotes.
- [x] Preserve preexisting environment/identity settings, validate worktree paths before cleanup, and recover correctly from failures halfway through staging. Do not delete working changes on generic errors.
- [x] Audit mirror publishing's forced history replacement: make target/ref and force semantics explicit, use a guarded expected remote state where appropriate, and do not infer authorization from a dry-run.
- [x] Test failure paths with fake native commands and local bare remotes only. Verify a failed push/tag/release returns nonzero and cannot print a final successful release result.

**Gate:** R13 passes without publishing anything. [59 local checks and four-job source CI](T18-EVIDENCE.md) pass; a [concrete read-only preview](T18-PREVIEW.md) is ready for later authorized publication. The closing push must pass its own exact-SHA four-job CI before handoff.

## T19 — Migration and interruption rehearsal

Executable children: [T19A evidence](T19A-EVIDENCE.md) covers the first three
checklists and passed four-job CI at `24ae8f4`. [T19B evidence](T19B-EVIDENCE.md)
covers the remaining matrix/measurement/rollback work; 11 new local cases pass,
with final four-job closing-source CI required before signoff. Missing live and
host-discovery surfaces remain explicit limitations. Stop before T20.

Dependencies: T14/T18. Estimate: 10–18k; split platform rehearsal if needed. Files: integration fixtures, host compatibility evidence, migration documentation; fix only failures demonstrated by rehearsal.

- [x] Rehearse legacy ledger with accepted/unmerged branches, partially failed build, missing ref, dirty original checkout, changed plan, corrupt state, and existing traces. Backups and reconciliation instructions must work.
- [x] Interrupt after dispatch, verification, commit, ledger save, merge, and integration test. Resume each from a fresh process; assert no lost accepted code, duplicate acceptance, or skipped dependency.
- [x] Run two CLI processes against the same build and separate builds; verify lock behavior, budget accounting, event isolation, and status readers under active writes.
- [x] Verify hosts independently: Codex standalone skill in CLI/IDE, intended Codex plugin surface, and existing Claude plugin. Record actual installation/discovery evidence separately from automated bundle smoke checks.
- [x] Use recorded provider fixtures for all four executors (`antigravity`, `opencode`, `cursor`, `codex`) across both host bundles; run only the smallest authorized live canaries needed to resolve remaining compatibility uncertainty. For Codex as executor, cover an actual interrupted process and fresh-process recovery if authorized, and inspect target-host CLI flags on Ubuntu before claiming live POSIX support. Never equate one platform/provider's live pass with all combinations.
- [x] Record actual token use where available, retry overhead, initial skill size, and status response size. Compare against planning estimates and adjust defaults if overhead defeats delegation benefits.
- [x] Verify downgrade/rollback instructions retain new-schema state without pretending old engines can read it. Make the final integration ref and merge instructions inspectable.

**Gate:** Every supported environment has a stated evidence level: offline contract tested, host-discovery tested, or live-provider tested. Missing environments remain explicit limitations. No P1 or required P2 defect remains open; rerun the full offline suite after final fixes.

## T20 — Documentation and release candidate

The 2026-09-28 user feedback adds a runtime/installation child before the final
documentation candidate. Stop for token confirmation after each child.

- [ ] **T20A — Explicit Codex fast tier and coherent Claude installs** (8–12k
  estimated lead tokens): shared `@effort+fast` parsing; separate validation
  identity; explicit Codex config; reject warning/fallback completion; verify
  configurable max-effort deadlines; regenerate both hosts/plugins; install all
  four Claude skills from one committed engine with backups and hashes.
  Offline tests and exact-source four-job CI required. No new live call is
  implied; leave fast entitlement and actual host discovery unverified.
- [ ] **T20B — Concise entry skills, final documentation and release candidate**
  (10–16k estimated lead tokens): the original checklists below, including
  commands, worked examples, version/changelog, candidate hashes/refs and
  support limitations. Refresh all four installed Claude skills together again
  if source changes. A static Luna picker entry is optional; never label an
  unvalidated model as verified or available based on its name.

Dependencies: T19. Estimate: 6–10k. Files: `README.md`, `INSTALL.md`, `CONTRIBUTING.md`, `SECURITY.md`, `KNOWN-ISSUES.md`, shared/host skill references, changelog/version, tracker and defect register.

- [ ] Rewrite the product description around a lead agent (Codex or Claude Code) and deterministic acceptance. Keep host and implementation-provider choices distinct in examples.
  Reduce older Claude entry skills from roughly 5.6–6.3k estimated tokens to
  around 1–2k by moving long provider/setup material to references. Preserve
  discovery and vendored-driver behavior; regenerate and check all artifacts.
- [ ] Document both install paths, generated bundle commands, real supported plan format, model validation/cost policy, JSON gates, integration, resume, repair, budgets, and migration. All displayed commands must exist at release time.
- [ ] Remove obsolete SUBSLICE/heavy-rung/automatic-probe/token/platform claims unless the implemented version now supports them. Explain unavailable provider usage and optional behavioral grading accurately.
- [ ] Describe actual sandbox/write boundaries and limitations; a Git worktree is not a security sandbox. Include recovery paths for denied permissions and failed collection without recommending blanket bypass.
- [ ] Add two short worked examples: Codex lead with an existing provider; Claude lead with the same engine. Include optional Codex executor only if T15/T16 are selected and gated.
- [ ] Close each R/A item with regression and commit evidence. Regenerate final artifacts after source/docs/version changes, verify freshness, and assemble a release candidate with hashes, migration notes, checks, remaining limitations, and target refs.
- [ ] Update milestones, tracker, and handoff. Keep optional deferred tasks visible. Record publication separately; preparing a candidate is complete even if remote release awaits authorization.

**Gate:** M5 complete: 18 required tasks verified, all review items addressed, host compatibility retained, release candidate reproducible. Public push/tag/release is a distinct operation and is not performed merely by checking this task off.
