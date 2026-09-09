# Phase 6 — Packaging, compatibility, and release readiness

Outcome: conventional Python installs and both host bundles work from a clean environment; releases stop on failures and carry honest support claims. T17 deliberately occurs before T14 in the recommended sitting order.

## T17 — Wheel, bundles, and CI

Dependencies: T12. Estimate: 8–12k. Files: `pyproject.toml`, generators, `.github/workflows/ci.yml`, packaging tests, optional dependency tests.

- [ ] Include required provider resources in wheel/sdist package data and verify both distributions. Ensure the engine can load all installed providers without the source checkout on sys.path.
- [ ] Build wheel, install into a clean environment, and smoke import providers/CLI. Clear editable/source-path leakage. Test the supported core with only required dependencies, plus pytest for deterministic target tests; optional behavioral/OTel imports must remain optional.
- [ ] Build every required host/provider skill combination into a fresh output root, import it alone, and validate metadata/entrypoint paths. Include Codex plugin manifests for intended supported surfaces.
- [ ] Regenerate committed bundles from source and make CI fail on drift. Compare normalized banners intentionally; do not hand-edit generated engines.
- [ ] CI matrix: Python minimum 3.11 and a current supported version selected at implementation; Windows and Ubuntu required. Add macOS coverage if claiming it, otherwise state its unverified scope. Keep live models excluded from default CI.
- [ ] Add plan/result/state-schema compatibility fixtures, wheel import checks, bundle freshness checks, and the new real-Git regression suite. Remove all temporary xfails once fixed.

**Gate:** R07/A05 pass and all 13 fixes remain testable without paid calls. Record wheel filename/hash, build command, isolated import result, bundle matrix, and CI environments. A wheel that merely builds does not satisfy this gate.

## T18 — Checked release automation

Dependencies: T17. Estimate: 8–12k. Files: `release.ps1`, `sync-public.ps1`, `generator/publish.py`, new release-script tests/fixtures.

- [ ] Wrap or explicitly check every critical native command: generation, Git worktree/add/commit/tag/push, gh operations, and mirror/copy steps. Stop with the failing command/result before subsequent mutations.
- [ ] Select CI by expected repository, workflow, branch, and exact pushed SHA. Handle no run found, queue delay, cancelled/failing runs, and timeout explicitly; never substitute the latest unrelated run.
- [ ] Make dry-run fully reviewable with exact refs/artifacts/destinations. Ensure build/tag/version/manifest values agree and reject unintended existing tags or remotes.
- [ ] Preserve preexisting environment/identity settings, validate worktree paths before cleanup, and recover correctly from failures halfway through staging. Do not delete working changes on generic errors.
- [ ] Audit mirror publishing's forced history replacement: make target/ref and force semantics explicit, use a guarded expected remote state where appropriate, and do not infer authorization from a dry-run.
- [ ] Test failure paths with fake native commands and local bare remotes only. Verify a failed push/tag/release returns nonzero and cannot print a final successful release result.

**Gate:** R13 passes without publishing anything. A concrete release-candidate preview can be produced for later authorized publication.

## T19 — Migration and interruption rehearsal

Dependencies: T14/T18. Estimate: 10–18k; split platform rehearsal if needed. Files: integration fixtures, host compatibility evidence, migration documentation; fix only failures demonstrated by rehearsal.

- [ ] Rehearse legacy ledger with accepted/unmerged branches, partially failed build, missing ref, dirty original checkout, changed plan, corrupt state, and existing traces. Backups and reconciliation instructions must work.
- [ ] Interrupt after dispatch, verification, commit, ledger save, merge, and integration test. Resume each from a fresh process; assert no lost accepted code, duplicate acceptance, or skipped dependency.
- [ ] Run two CLI processes against the same build and separate builds; verify lock behavior, budget accounting, event isolation, and status readers under active writes.
- [ ] Verify hosts independently: Codex standalone skill in CLI/IDE, intended Codex plugin surface, and existing Claude plugin. Record actual installation/discovery evidence separately from automated bundle smoke checks.
- [ ] Use recorded provider fixtures for the full matrix; run only the smallest authorized live canaries needed to resolve remaining compatibility uncertainty. Never equate one platform/provider's live pass with all combinations.
- [ ] Record actual token use where available, retry overhead, initial skill size, and status response size. Compare against planning estimates and adjust defaults if overhead defeats delegation benefits.
- [ ] Verify downgrade/rollback instructions retain new-schema state without pretending old engines can read it. Make the final integration ref and merge instructions inspectable.

**Gate:** Every supported environment has a stated evidence level: offline contract tested, host-discovery tested, or live-provider tested. Missing environments remain explicit limitations. No P1 or required P2 defect remains open; rerun the full offline suite after final fixes.

## T20 — Documentation and release candidate

Dependencies: T19. Estimate: 6–10k. Files: `README.md`, `INSTALL.md`, `CONTRIBUTING.md`, `SECURITY.md`, `KNOWN-ISSUES.md`, shared/host skill references, changelog/version, tracker and defect register.

- [ ] Rewrite the product description around a lead agent (Codex or Claude Code) and deterministic acceptance. Keep host and implementation-provider choices distinct in examples.
- [ ] Document both install paths, generated bundle commands, real supported plan format, model validation/cost policy, JSON gates, integration, resume, repair, budgets, and migration. All displayed commands must exist at release time.
- [ ] Remove obsolete SUBSLICE/heavy-rung/automatic-probe/token/platform claims unless the implemented version now supports them. Explain unavailable provider usage and optional behavioral grading accurately.
- [ ] Describe actual sandbox/write boundaries and limitations; a Git worktree is not a security sandbox. Include recovery paths for denied permissions and failed collection without recommending blanket bypass.
- [ ] Add two short worked examples: Codex lead with an existing provider; Claude lead with the same engine. Include optional Codex executor only if T15/T16 are selected and gated.
- [ ] Close each R/A item with regression and commit evidence. Regenerate final artifacts after source/docs/version changes, verify freshness, and assemble a release candidate with hashes, migration notes, checks, remaining limitations, and target refs.
- [ ] Update milestones, tracker, and handoff. Keep optional deferred tasks visible. Record publication separately; preparing a candidate is complete even if remote release awaits authorization.

**Gate:** M5 complete: 18 required tasks verified, all review items addressed, host compatibility retained, release candidate reproducible. Public push/tag/release is a distinct operation and is not performed merely by checking this task off.
