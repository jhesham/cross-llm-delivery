# N08 — native Antigravity cwd, implemented through CLD

Implemented 2026-10-04 using exact **`codex:gpt-6-luna@max+fast`**.
Committed assertion-red tests/contract: `44fdc2e66597d4c3a7131d603c541af8d09bacb7`.
Accepted model source: `f51b1d94959e1d14ac3a6da56153e314e3711b3c`.
Checked integration: `79031cf47d711b8dcca7b252d71418267b2fe77a`.
Final reviewed source/documentation used for generation: `d5cd59d`.

## Behavior

`_dispatch_cwd()` returns the native `Path.home()` on POSIX. Only Windows applies
the existing SystemDrive transformation for Antigravity's `/Users/...` transcript
paths, retaining case-insensitive drive comparison and cross-drive user paths.
An explicit executor `home` still controls dispatch cwd and transcript lookup.
The worktree remains a separate `--add-dir` argument. Exact model, timeouts,
cancellation, artifacts, recursion marker and two-argument injected runners are
unchanged. Missing-transcript guidance now reflects the platform.

This fixes the adapter's incorrect POSIX cwd. Model-free local subprocess/path
checks do not establish live Antigravity provider behavior on POSIX or macOS.

## Trace and independent verification

1. Waited for all four Ubuntu/Windows × Python 3.11/3.14 full-suite/generation
   jobs on N07 source/artifacts `54b41d0` before the live N08 call:
   [run 37136806667](https://github.com/jhesham/cross-llm-delivery/actions/runs/37136806667).
2. Committed the [plan](N08-CLD-PLAN.md), two-file [contract](N08-CLD-CONTRACT.md)
   and ten acceptance cases. Windows baseline: **five failed, four passed, one
   skipped in 0.17 s**. A provider-free real-Git frozen preflight confirmed the
   valid assertion-red baseline in 0.22 s. Windows SystemDrive regressions were
   already green. The real native POSIX default-home case is skipped on Windows
   and must be proved on Ubuntu CI.
3. Used the generated N07 Codex-provider driver, ledger `.cld/n08/ledger.json`,
   run `688e43811ee6431da8bdebdc8af183ec`. An initial invocation omitted the global
   `--executor` flag and was refused at preflight with zero attempts/tokens.
   Corrected that input in the same run with the exact selected spec. `deny`
   reused current validation evidence; **no canary** was needed.
4. One implementation call changed only the two allowed files. Captured source
   passed **nine frozen cases, one skip, in 0.25 s**. The executor's own test
   reported six passes, one skip and three Windows restricted-token temp-access
   errors, then stopped retries as instructed. Independent captured acceptance
   supplies the completed result; no helper refresh failure or paid retry.
5. The whole-plan command supplied the precise frozen N08 integration selector;
   CLD automatically verified its red baseline and integrated candidate, passing
   **nine cases, one skip, in 0.28 s**, gate 3. Reviewed the entire two-file diff
   before fast-forwarding the working branch to that checked integration.
   Local proof: `.cld/runs/688e43811ee6431da8bdebdc8af183ec/integration/328076f78889440989830efdb2d914e2/`.
   No reconciliation or F01 change was needed. The lead removed a duplicated
   phrase in the new diagnostic and added the changelog entry.
6. Final-source adjacent group: **270 passed, one skipped, 1,084 deselected,
   two existing deprecation warnings, in 24.41 s**. Includes N06–N08, all
   executors/process lifecycle, shared launchers, preflight, discovery and provider
   configuration identity. The local child exercises default selected-home
   dispatch, worktree/model argv, depth marker and artifact/deadline options
   without launching an LLM.
7. Regenerated all five providers for both hosts and both plugin formats from
   committed `d5cd59d`. Wheel/sdist, isolated bundles and parity suites:
   **18 passed in 36.90 s**. All 40 shared core Python files match across ten
   bundles and provider bytes match. Ten outside-checkout bundles pass recursion
   smoke checks; both Antigravity bundles pass the frozen N08 assertions
   (**nine passed, one platform skip each**). Both OpenCode bundles retain their
   17 native-launch passes. Five tracked Claude packages pass freshness checks.
   Artifact checks performed no inference or installation.

Counts overlap; do not sum the groups as distinct cases. Source/artifact push and
exact-source CI will be recorded at the checkpoint. The native POSIX child and
all four full-suite/generation jobs remain required before final closure or
further implementation/promotion.

## Measured usage

| Call | Input | Output | Cached input (subset) | Derived total |
|---|---:|---:|---:|---:|
| Implementation | 140,273 | 4,478 | 121,344 | **144,751** |

One live call, no canary, retry or substitution. Uncached input: 18,929 tokens.
Cached input is included in input, not added again. The cumulative admission
estimate was 1,200,000 tokens, with a 600,000 attempt reservation, one-call limit
and 900-second dispatch deadline. Actual usage exceeded neither reservation;
the ledger has zero attempt overruns or active calls. Cost and lead usage are
unavailable. Exact max/fast completed without a surfaced tier failure; actual
priority routing has no independent telemetry.

Global Codex config matches its pre-call byte digest exactly; no trust entry churn,
restoration or persistent setting changes. Raw logs, frozen proof and ledger stay
local and ignored. No global install, release promotion or live POSIX provider
call was performed.

## Next sitting

Stop after N08 and confirm token availability before further work. N04–N08 are
implemented on the working branch; N08's pending platform results must be checked.
The separate [F01 pytest diagnostic follow-up](FOLLOWUP-PYTEST-DIAGNOSTICS.md)
remains unimplemented. These fixes are unreleased; public main remains v0.4.1.
