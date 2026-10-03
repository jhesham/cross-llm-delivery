# N07 — native OpenCode launch, implemented through CLD

Implemented 2026-10-04 using exact **`codex:gpt-6-luna@max+fast`**.
Committed assertion-red tests/contract: `504da9cdc6512ff9446ddbcfdb5e89a5dfde2fed`.
Accepted model source: `45a52f7af2879fb6562625d516ae031d1fac1e10`.
Checked integration: `80acbf99769ee17906be2aa3b595471ae6a07cd5`.
Final source/documentation used for generation: `ba4482d`.

## Behavior

OpenCode now uses the shared native-command contract for production dispatch,
model discovery, stats and preflight. Selection priority is an explicit absolute,
existing `OPENCODE_CLI_CMD`, then Windows `opencode.exe` on PATH, then the npm
postinstall target `<shim-dir>/node_modules/opencode-ai/bin/opencode.exe`.
The last path was verified against the locally installed `opencode-ai` 1.18.29
package's bin mapping and postinstall source. CLD does not guess optional CPU or
platform package names if the postinstall output is missing.

Missing/incomplete installations fail with native override guidance. The shared
resolver refuses Windows `.cmd`/`.bat` overrides, including Codex/Claude overrides;
production never falls back to an OpenCode shell shim. On POSIX it uses the
explicit override or the native `opencode` on PATH.

Only the logical OpenCode argv prefix is rewritten. Unrelated Git/Python calls
are unchanged, and injected two-argument runners receive the logical command
without requiring a CLI installation. Existing caller argv, exact model/variant,
long/multiline Unicode arguments, fresh-server flag, environment overlays,
recursion marker, timeout, cancellation and artifact options are preserved.
Default dispatch returns `missing_binary` before any process or diff capture
when resolution fails; discovery/stats degrade to empty results. Preflight reports
the actionable launch problem. The `_oc_cmd` compatibility export delegates to
the same native resolver.

## Trace and independent verification

1. Confirmed all four Ubuntu/Windows × Python 3.11/3.14 full-suite/generation jobs
   passed on N06 source/artifacts `7212bca` before this live slice:
   [run 37122319883](https://github.com/jhesham/cross-llm-delivery/actions/runs/37122319883).
2. Committed the [plan](N07-CLD-PLAN.md), four-file [contract](N07-CLD-CONTRACT.md)
   and 17 offline acceptance cases. All 17 initially failed by assertion, with no
   collection error. A provider-free real-Git frozen preflight verified that red
   baseline before dispatch. Existing resolver tests were updated to the new
   contract; local process fixtures use Python as their explicit native executable.
3. Used the generated N06 Codex-provider driver, bound ledger
   `.cld/n07/ledger.json`, run `b5faf509b06e48e1b0b957af518a8457`. Current exact-spec
   validation evidence was reused under `deny`; **no fresh canary** was needed.
4. One implementation call changed only the four allowed files and passed all
   **17 frozen tests in 0.55 s**, gate 6, on attempt one. The executor reported
   Windows restricted-token access errors during its self-test; independent
   captured acceptance supplies the completed result. No retry or substitution.
5. Reviewed the complete source diff and integrated through CLD gate 3 using
   the unchanged precise N07 selector. The frozen baseline was red, the integrated
   candidate passed all 17 cases, and the working branch was fast-forwarded to
   that checked commit. The integration proof is local under
   `.cld/runs/b5faf509b06e48e1b0b957af518a8457/integration/eb26928e9d3246e8bc64cc794e3af0f7/`.
   The separate [F01 diagnostic defect](FOLLOWUP-PYTEST-DIAGNOSTICS.md) was not
   changed, and no ledger reconciliation was needed in N07.
6. Independent adjacent group on integrated source: **261 passed, 1,084
   deselected, two existing deprecation warnings, in 26.61 s**. This includes all
   N07/N06 cases, executors, process lifecycle, shared launcher, Codex/Claude,
   CLI preflight, discovery and OpenCode configuration identity. The lead also
   made the positive preflight fixture independent of an installed OpenCode and
   clarified the injected-runner discovery contract; the final affected pair of
   suites passed **49 tests in 2.28 s**.
7. Regenerated all five providers for both hosts and both plugin formats from
   committed source `ba4482d`. Wheel/sdist, bundle and parity suites:
   **18 passed in 39.04 s**. All 40 shared core Python files match across ten
   bundles; provider source bytes match, and the new OpenCode launcher matches
   in both host bundles. All ten outside-checkout bundles passed recursion smoke
   checks. Both standalone OpenCode bundles additionally passed all 17 frozen
   N07 assertions, including the real local Python child preserving over 8k of
   multiline Unicode/metacharacter argv. These checks performed no inference.
   Five tracked Claude plugin packages pass freshness checks.

Counts overlap; do not add acceptance, adjacent, follow-up and standalone counts
as distinct tests. Cross-platform CI for the pushed N07 source/artifacts will be
recorded at the checkpoint; all four results are required before N08.

## Measured usage

| Call | Input | Output | Cached input (subset) | Derived total |
|---|---:|---:|---:|---:|
| Implementation | 421,439 | 13,490 | 361,728 | **434,929** |

One live call, zero canaries or paid retries. Uncached input: 59,711 tokens.
Cached input is already included in input and must not be added again. Cumulative
admission estimate: 1,200,000 tokens; attempt reservation: 600,000; deadline:
900 seconds. Actual usage exceeded neither estimate; ledger reports zero attempt
overruns and no in-flight reservation. Cost and lead usage are unavailable.
The exact requested max/fast spec completed without a surfaced tier failure;
actual priority routing has no independent telemetry.

Global Codex config matches its pre-call byte digest exactly; there was no trust
entry churn or restoration in N07. No persistent setting changes, global install
or release promotion. Raw logs, synthetic probe evidence and ledger stay ignored
and local; public documentation records the trace without private provider logs.

## Next sitting

Stop after N07 and confirm token availability. Require all four N07 CI jobs green
before starting N08 with exact Luna/max/fast; reuse current exact-spec validation
if fresh. N08's Antigravity POSIX cwd fix and F01 remain pending. N04–N07 are
working-branch fixes, not a published release.
