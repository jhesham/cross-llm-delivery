# F01 — pytest diagnostics policy, implemented through CLD

Implemented 2026-10-04 using exact **`codex:gpt-6-luna@max+fast`**.
Initial committed tests/contract: `0a51be7`; corrected test fixture: `7e4293c`.
Accepted source: `235a13c2d54dbde69b3d8f6622c10004224c39df`.
Checked integration: `fb72548a60cc236f49dac79d09221ad061eb3592`.
Final source/documentation used for generation: `6170865`.

## Behavior

`run_process` has a keyword-only `classify_output=True` policy. Both pytest
adapters (`cli.pytest_test_runner` and `validate._pytest`) explicitly select
`False`: ordinary nonzero exits retain their return code and `nonzero_exit`
metadata without interpreting assertion output or item labels as provider errors.
The adapters normalize only that ordinary exit error for independent pytest
judgment. Retained process JSON reflects the selected policy.

Timeouts, cancellation, launch failures, missing return codes and other lifecycle
errors remain fail-closed. Collection/configuration/no-tests outcomes remain
invalid assertion-red baselines. Provider executors retain the default output
heuristics, including final authentication failures and no retry/escalation.
Candidate verification and integration policy are unchanged.

The executor changed only `engine/cld/process.py`, `engine/cld/cli.py` and
`engine/cld/validate.py`: six insertions, four deletions. The lead added a policy
docstring and changelog entry after integration; no lead runtime correction.

## Live dispatch and checked fixture repair

All four N08 CI jobs passed before this call:
[run 37138995723](https://github.com/jhesham/cross-llm-delivery/actions/runs/37138995723).
The generated N08 Codex-provider driver used `.cld/f01/ledger.json`, explicit
executor selection, `--validation-policy deny`, one live attempt, a 1,200,000
token cumulative admission estimate, a 600,000 attempt reservation and an
explicit `CLD_DISPATCH_TIMEOUT=900`. Current exact-spec evidence was reused:
no canary, paid retry, model substitution or escalation.

Original run: `86c835bfe0094eabbc61ee61969a3ab4`.
Live session: `557284fe6f64450ea02afe45cee1dbc0`.
The frozen baseline was nine failed, 21 passed. The model runtime produced
28 passes and two failures caused by a lead-written green-path fixture accessing
`candidate.files` instead of `candidate.files_changed`. Those assertions had
been unreachable before the runtime fix. This was not an executor/runtime
failure. The model's own single pytest attempt hit Windows restricted-token
temporary-directory access errors; independent frozen acceptance provided the
28/2 result. No sandbox helper refresh failure was observed.

The one-call budget blocked a second dispatch. The original outcome records two
internal attempts, but measured live usage records **one actual provider call**.
No candidate was initially accepted. Its runtime tree `d7cebd3` and recovery ref
`refs/cld/recovery/557284fe6f64450ea02afe45cee1dbc0/attempt-2-failure`
remain available. Original logs, failed worktree and evidence were not rewritten
or removed.

The lead committed the one-line fixture correction at `7e4293c`, then used checked
`--reconcile-plan` to bind the new committed baseline. New run:
`4d51f27b65254a57b0d8c21520b372ce`; original ledger backup:
`.cld/f01/ledger.json.reconcile-1134915b47284733b39ae42100d0995b.bak`.
A lead staging script used real ledger ownership, managed worktree and recovery
APIs to copy only the original three allowed Git blobs into a newly owned
worktree. Hash comparisons proved the model runtime bytes unchanged; the new
recovery record explicitly describes lead staging with no provider dispatch.

Staging session: `6a85e4d22e444ef9b05721e95341614b`.
Real CLI `--mark-repaired F01` session:
`b2b1a4017cee45f0bfee51b6a7f81aaf`; corrected frozen baseline nine failed,
21 passed; candidate **30 passed**, accepted at gate 6.
Real CLI `--integrate` session: `03adfca04a1f472f937f11bdd5af33cc`;
same red baseline and **30 passing** candidate tests, integrated at gate 3.
The reviewed three-file diff was brought into the working branch by fast-forward.
No additional inference was needed for repair or integration.

The reconciled repair/integration ledger does not contain the original live
usage. Its zero/unknown usage must not be presented as the whole slice's cost;
the original backup and raw log supply the measured total below.

## Independent verification against final source

- Frozen F01 contract: **30 passed** through checked repair and integration.
- Final focused source group: **277 passed, one skipped in 403.90 s**. Covers
  both pytest adapters, actual child-process metadata/lifecycle, real-Git
  import isolation and candidate validation, final provider failures, integration
  and N06–N08 regressions. The skip is native POSIX execution on Windows.
- Exact original N06 broad selector against final source: **232 passed** through
  the real CLI pytest adapter, with no process error.
- Historical N06 baseline `c6c17fb`, with only the three-file F01 runtime change
  applied in a temporary owned detached worktree: **29 intended failures,
  203 passes**, return code 1, no process error; frozen preflight accepts valid
  assertion-red output. The passing authentication-like item remains present.
  Original saved N06 evidence was untouched; only this clean temporary worktree
  was removed after the replay.
- Wheel/sdist, isolated bundles and parity checks: **18 passed in 41.67 s**.
- All five providers for both hosts and both plugin formats regenerated from
  committed `6170865`. All 40 shared core Python files match across ten bundles;
  provider and OpenCode launcher bytes match. Ten outside-checkout bundles pass
  recursion smoke checks. Both standalone OpenCode suites retain 17 passes;
  both Antigravity suites retain nine passes and one platform skip on Windows.
- Both standalone Codex-provider host bundles pass additional isolated local
  red/green pytest probes through both adapters, including the misleading passing
  item label, retained provider authentication defaults and bundled-module
  ownership assertions. No LLM is called by these probes.
- All five tracked plugin packages pass generated freshness checks.

Counts overlap; do not sum these groups as distinct tests. Proof stays local
under `.cld/f01/`, including `historical-baseline.{txt,json}` and
`final-broad.{txt,json}`. Exact-source cross-platform CI is pending at this
checkpoint; record its run before stopping and require all four jobs green
before promotion.

## Measured usage and checkpoint

| Call | Input | Output | Cached input (subset) | Derived total |
|---|---:|---:|---:|---:|
| Implementation | 197,620 | 3,915 | 155,136 | **201,535** |

Uncached input: 42,484. Cached input is included in input, not added again.
One live call, no attempt/cumulative reservation overrun or active call. Cost
and lead usage are unavailable. Exact max/fast completed without a surfaced
tier failure; actual priority routing lacks independent telemetry.

Global Codex config is unchanged: 3,916 bytes, SHA256
`95fe9ceef623cf622fd4defd9c72c8f02bd8c88e9d543e0d243a5f8afc75280c`.
No persistent settings change, global installation, release promotion or cleanup
of the retained failed worktree. N04–N08 and F01 are implemented on the working
branch and unreleased. Stop after this checkpoint and confirm token availability
before further work.
