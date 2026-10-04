# N04–N08 implementation checkpoints

Authorized 2026-10-03. Work one committed slice at a time; stop after each slice
for the user's token-availability check. N04 is implemented directly by Codex.
N05–N08 use CLD with **`codex:gpt-6-luna@max+fast`**, as explicitly selected by
the user. Do not substitute a model, effort, or tier; an unsupported fast tier
must stop dispatch rather than silently using standard service.

| Slice | Scope | Method | Status |
|---|---|---|---|
| N04 | Frozen candidate project imports | Direct implementation and real-Git regressions | Complete; four-job CI green |
| N05 | Codex configuration identity | CLD / exact Luna max + fast | Complete; four-job CI green |
| N06 | Five-provider recursion contract | CLD / exact Luna max + fast | Complete; four-job CI green |
| N07 | Native Windows OpenCode discovery | CLD / exact Luna max + fast | Complete; four-job CI green |
| N08 | Antigravity native POSIX cwd | CLD / exact Luna max + fast | Complete; four-job CI green |
| F01 | Pytest output diagnostic policy | CLD / exact Luna max + fast | Complete; four-job release CI green; published v0.4.2 |

Detailed requirements and corrective checklists:
[full review](FULL-REVIEW-2026-10-03.md).

## N04 closure

- [x] Commit failing real-Git import regressions before implementation (`a3ca85b`;
      all eight initial cases failed).
- [x] Cover false approval and false rejection through inherited `PYTHONPATH`,
      legacy editable paths, modern editable finders and installed-package shadowing.
- [x] Preserve independent dependencies and cover namespace-package locations.
- [x] Block live project modules imported at startup or by a late finder.
- [x] Use the same policy for the CLI acceptance runner and model validation,
      under the candidate scope also used by repair/integration.
- [x] Send checkout inventory through stdin to avoid Windows argv limits.
- [x] Finish final focused checks and record counts against final source.
- [x] Commit runtime changes, then generate both hosts' five bundles/plugins
      from that committed runtime source.
- [x] Verify artifact parity, standalone operation and packaging.
- [x] Push the working branch and record exact-source CI status (`215bae1`,
      [run 37115459230](https://github.com/jhesham/cross-llm-delivery/actions/runs/37115459230),
      all four jobs passed).
- [x] Confirm all four cross-platform CI jobs pass; resolve failures before N05.
- [x] Update handoff and stop for token availability before N05.

## Each CLD slice (N05–N08)

- [x] Confirm N04's independent gate and cross-platform CI are green before
      relying on CLD for the next implementation.
- [x] Commit scoped failing acceptance tests and a precise file allowlist/contract.
- [x] Use the current generated Codex-provider driver containing N04, with a
      separate bound ledger/plan and preserved worktree/evidence.
- [x] Pin `codex:gpt-6-luna@max+fast`; verify local CLI capability/account setup.
      Protect Codex config identity explicitly with `--validation-config` while
      N05's automatic discovery remains unfixed.
- [x] Permit a bounded validation canary only if current exact-spec evidence is
      absent. Set explicit token/attempt caps and record unknown cost honestly.
- [x] Run one implementation dispatch; inspect failures before any further spend.
      Do not silently retry with another model/tier or escalate.
- [x] Review the candidate, independently run acceptance/adjacent tests, integrate
      through the checked CLD gate, and bring only the reviewed commit into the
      working branch.
- [x] Regenerate affected artifacts from committed source; update checklist,
      handoff and measured executor usage; stop at the slice checkpoint.

No live executor calls or global installs are part of the N04 checkpoint.
Existing ledgers are not retroactively re-judged by the import fix. Start a fresh
build if earlier acceptance relied on source outside its frozen candidate.

N04 verification and runtime provenance:
[import isolation evidence](N04-IMPORT-ISOLATION-FIX.md).

## N05 closure

- [x] Commit red acceptance tests, the [delivery plan](N05-CLD-PLAN.md) and
      [five-file implementation contract](N05-CLD-CONTRACT.md).
- [x] Validate and dispatch exact Luna/max/fast through the N04 driver. One
      canary and one implementation call; no paid retry or model substitution.
- [x] Independently accept and integrate the candidate through CLD gates 6/3;
      preserve both run histories and the reconciled ledger backup.
- [x] Review the implementation and close the literal absolute-home edge case.
- [x] Verify final focused checks (84 passed), packaging/bundle checks (18 passed),
      ten-bundle core parity and both standalone Codex configuration guards.
- [x] Regenerate all five providers for both hosts from runtime `8320281`.
- [x] Push the working branch and record exact-source CI (`0d2eb08`,
      [run 37119733253](https://github.com/jhesham/cross-llm-delivery/actions/runs/37119733253),
      queued at checkpoint).
- [x] Confirm all four cross-platform jobs before the next live slice.
- [x] Record measured executor usage and stop for the user's token checkpoint.

[N05 evidence](N05-CODEX-CONFIG-FIX.md) records validation run
`7dd62c25b2c34d53acab578903aceef5` and reconciled production run
`c38d1cf32c504a1582eb8fedbc5de9fc`, ledger `.cld/n05/ledger.json`.
Final runtime is `8320281`; implementation accepted at `0294ab6`, integrated at
`8ab0029`. Total measured executor tokens: **2,457,594**, including **2,220,544**
cached input tokens. This exceeded the 1,200,000 admission estimate; cost and
lead usage are unavailable. No additional provider call followed the overrun.

N06 checked final automatic inputs and performed one fresh canary after token
availability was confirmed; see its checkpoint below.

## N06 closure

- [x] Confirm N05's four CI jobs passed before live calls.
- [x] Commit scoped assertion-red tests, a six-file contract and exact-model plan.
- [x] Verify the baseline with real frozen CLD preflight (29 failed, 24 passed).
- [x] Make one canary and one exact Luna/max/fast implementation call; preserve
      config identity and resume production under `deny` without another probe.
- [x] Review the accepted six-file diff and integrate via checked CLD gate 3.
- [x] Record the broad-baseline diagnostic false-positive and checked ledger
      reconciliation, retaining the accepted commit and all prior evidence.
- [x] Pass 53 frozen N06 tests, 232 adjacent checks and 18 packaging/bundle checks.
- [x] Regenerate ten bundles and both plugin formats from source `7b1ab0e`;
      verify core/provider parity and ten standalone recursion checks.
- [x] Push the working branch and record exact-source CI (`7212bca`,
      [run 37122319883](https://github.com/jhesham/cross-llm-delivery/actions/runs/37122319883),
      all four jobs passed before N07).
- [x] Confirm all four cross-platform jobs before the next live slice.
- [x] Record full measured usage, update handoff and stop after N06.

[N06 evidence](N06-RECURSION-FIX.md): accepted `102de90`, integrated `c3e7486`.
Measured executor total **862,345**, including **759,040** cached input tokens;
within the 1.2m cumulative estimate, with one per-attempt reservation overrun.
No further N06 provider calls. N07 continued after the user's token checkpoint;
N08 subsequently completed with all four CI jobs green.
The separate [F01 pytest diagnostic follow-up](FOLLOWUP-PYTEST-DIAGNOSTICS.md)
is now implemented; see the checkpoint below.

## N07 closure

- [x] Confirm N06's four exact-source CI jobs passed before dispatch.
- [x] Commit 17 assertion-red cases, a four-file contract and exact-model plan.
- [x] Validate the red baseline through provider-free frozen CLD preflight.
- [x] Reuse fresh exact-spec evidence under `deny`; make one implementation call,
      without a canary, retry or model/tier substitution.
- [x] Review all four allowed changes and integrate via checked CLD gate 3.
- [x] Pass 17 frozen cases, 261 adjacent checks and the final 49-check fixture
      pair; counts overlap. Packaging/bundle checks: 18 passed.
- [x] Regenerate ten bundles and both plugin formats from committed `ba4482d`;
      verify 40-file core parity, provider/launcher bytes, ten standalone recursion
      guards and all 17 N07 cases in both standalone OpenCode bundles.
- [x] Verify all five tracked plugin packages are fresh.
- [x] Push the working branch and record exact-source CI (`54b41d0`,
      [run 37136806667](https://github.com/jhesham/cross-llm-delivery/actions/runs/37136806667),
      all four jobs passed before N08).
- [x] Confirm all four cross-platform jobs before N08.
- [x] Record measured usage, update handoff and stop after N07.

[N07 evidence](N07-OPENCODE-NATIVE-FIX.md): baseline `504da9c`, accepted `45a52f7`,
integrated `80acbf9`, generation source `ba4482d`. One live call used **434,929**
tokens, including **361,728** cached input; no reservation overruns. Cost/lead
usage unavailable; actual fast routing lacks independent telemetry. Global config
is unchanged. N08 and F01 continued after the user's subsequent checkpoints.
No release promotion or global install.

## N08 closure

- [x] Confirm N07's four exact-source CI jobs passed before dispatch.
- [x] Commit scoped tests, a two-file contract and exact-model plan (`44fdc2e`).
- [x] Verify frozen assertion-red baseline: five failed, four passed, one native
      POSIX case skipped on Windows; existing Windows path behavior passes.
- [x] Reuse current exact-spec validation evidence under `deny`, with one
      implementation call allowed; no canary, retry or substitution.
- [x] Review the two-file accepted diff and fast-forward the working branch to
      the checked integration commit, after the precise frozen selector passed.
- [x] Preserve the Windows SystemDrive workaround and explicit home overrides;
      return native home on POSIX and give platform-aware transcript guidance.
- [x] Pass nine frozen cases plus one platform skip, then 270 adjacent checks
      plus that skip on final source; counts overlap.
- [x] Regenerate ten bundles and both plugin formats from committed `d5cd59d`;
      verify 40-file core/provider parity, ten standalone recursion guards and
      both standalone Antigravity N08 suites (nine passed, one skip each).
- [x] Verify both standalone OpenCode suites and five tracked plugin packages.
- [x] Pass final packaging/bundle checks: 18 passed.
- [x] Push the working branch and record exact-source CI (`a5337f9`,
      [run 37138995723](https://github.com/jhesham/cross-llm-delivery/actions/runs/37138995723),
      all four jobs passed before the F01 live call).
- [x] Verify the native POSIX default-home child on Ubuntu Python 3.11/3.14 CI.
- [x] Confirm all four cross-platform jobs before further implementation/promotion.
- [x] Record measured usage, update handoff and stop after N08.

[N08 evidence](N08-ANTIGRAVITY-CWD-FIX.md): accepted `f51b1d9`, integrated
`79031cf`, final generation source `d5cd59d`. One implementation call used
**144,751** tokens, including **121,344** cached input; no reservation overrun.
Cost/lead usage unavailable; actual fast routing lacks independent telemetry.
Global config is unchanged. F01 is implemented below. N04–N08 are working-branch
fixes; no release promotion, install or live POSIX/macOS provider verification.


## F01 closure

- [x] Confirm all four N08 CI jobs passed before the live call.
- [x] Commit 30 scoped cases, a three-file contract and exact-model plan.
- [x] Verify the original frozen baseline: nine failed, 21 passed.
- [x] Reuse current exact-spec evidence under `deny`; make one Luna/max/fast
      implementation call with no canary, paid retry or substitution.
- [x] Preserve the original 28-pass/two-failure receipt; correct the lead's
      green-path fixture in a committed baseline and reconcile explicitly.
- [x] Stage unchanged model runtime blobs through owned recovery APIs; accept
      through real `--mark-repaired` and integrate through checked gates 6/3.
- [x] Pass 30 frozen cases, 277 focused cases plus one skip, the original broad
      selector's 232 cases and 18 packaging checks; counts overlap.
- [x] Replay the historical broad baseline: 29 failures, 203 passes, no process
      error, valid assertion-red preflight; original evidence remains untouched.
- [x] Regenerate ten bundles and both plugin formats from committed `6170865`;
      verify core/provider/launcher parity, standalone recursion and red/green
      pytest behavior, retained N07/N08 checks and five-package freshness.
- [x] Push source/artifacts `6037bb1` and record exact-source cross-platform CI:
      [run 37142332565](https://github.com/jhesham/cross-llm-delivery/actions/runs/37142332565),
      in progress at checkpoint; subsequent checkpoint is documentation only.
- [x] Confirm all four final release-branch and exact-main CI jobs before publication.
- [x] Record full live usage, update handoff and stop for token availability.

[F01 evidence](F01-PYTEST-DIAGNOSTICS-FIX.md): accepted `235a13c`, integrated
`fb72548`, generation source `6170865`. One live implementation call used
**201,535** tokens, including **155,136** cached input; no reservation overrun.
The reconciled repair/integration ledger excludes that earlier live usage; use
the original ledger backup/logs for whole-slice accounting. Cost/lead usage
unknown; actual fast routing lacks independent telemetry. Config is unchanged.
No installation or release promotion. N04–N08 and F01 are implemented and
unreleased on the working branch; stop before the next slice.

## v0.4.2 publication closure

- [x] Resolve the initial F01 Windows/Python 3.14 atomic replacement failure with
      committed red/green regressions and bounded Windows lock retries.
- [x] Pass all 49 focused recovery/ledger checks and the final local full suite.
- [x] Confirm all four final release-branch CI jobs before promotion.
- [x] Promote main through the checked normal-push workflow; verify all four
      exact-main CI jobs before tagging/publication.
- [x] Build all providers/hosts from the immutable tag source and publish nine
      assets; download all nine and verify hashes.
- [x] Record publication/handoff, preserving prior delivery evidence and installs.

Published [v0.4.2](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.4.2), source `64048696c4bce27e8b1119137a630e9b3c6164fa`.
All N04–N08 and F01 fixes are released; earlier checkpoints above are historical.
[Publication evidence](PUBLICATION-0.4.2.md). No provider calls or global installs.
