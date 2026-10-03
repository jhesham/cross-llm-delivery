# N06 — five-provider recursion defense, implemented through CLD

Implemented 2026-10-03 using exact **`codex:gpt-6-luna@max+fast`**.
Committed red tests/contract: `c6c17fb2af418bbee349111c76c7b2584cd00c0d`.
Accepted model source: `102de90a6e5538416eb763b10b6129838f39c30c`.
Checked integration: `c3e7486c4ff25cd9e82c383fd89f727129a996e0`.
Final runtime and shared documentation used for generation: `7b1ab0e`.

## Behavior

All five direct executor `.run` entrypoints use a shared predicate before any
probe, command resolution, artifact creation or diff capture. A lead has
`CLD_EXECUTOR_DEPTH` absent or exactly `0`; every other value fails closed with
`recursive_dispatch`. Codex/Claude now follow the CLI's literal-zero rule too.

Production OpenCode, Cursor and Antigravity dispatches supply the `1` child
marker through an optional shared-dispatch environment overlay. Codex/Claude
retain their existing invocation overlays. Cursor merges the incoming overlay
with inherited environment, its invocation marker and bundled-Node TLS options.
The lead environment is unchanged. Legacy injected runners still receive exactly
two positional arguments. Probes and unrelated `run_process` calls are not
globally relabeled as executors.

The three older prompts now identify a one-slice executor and prohibit invoking
CLD, another provider or a dispatch tool, including feedback prompts. These are
defenses against accidental nested spend; worktree isolation is not an OS sandbox.
N07 resolver and N08 cwd behavior were deliberately outside this slice.

## Trace and independent verification

1. Confirmed N05's exact-source CI at `0d2eb08` passed all four full-suite,
   generator and packaging jobs before live N06 calls:
   [run 37119733253](https://github.com/jhesham/cross-llm-delivery/actions/runs/37119733253).
2. Committed 53 acceptance cases, the [plan](N06-CLD-PLAN.md) and six-file
   [contract](N06-CLD-CONTRACT.md). Baseline: **29 failed, 24 passed**. A provider-free
   real-Git frozen preflight accepted this as valid assertion-red output.
3. Used the checkout-generated N05 Codex-provider driver. Original run
   `7de01c823cb64fb1a1151de8fbb9f89c`, ledger `.cld/n06/ledger.json`. `deny` refused
   stale prior evidence without spend. One authorized fresh canary passed.
4. Codex added a temporary probe trust entry to user config, and N05 correctly
   blocked production when the config changed. Removed only that owned entry
   after proving an exact byte-digest reconstruction of the pre-call config;
   no evidence record was rewritten. `deny` then reused the fresh evidence.
5. The first implementation changed only the six allowed files and passed
   independent captured acceptance: **53 passed in 5.31 s**, CLD gate 6.
   The executor reported the known Windows restricted-token pytest access
   failure after its self-test, rather than spending turns on repeated retries.
6. A broad provider-free integration baseline had the expected 29 failures and
   203 passes, but generic process diagnostics classified a passing test's
   `authentication failed` parameter name as a process authentication error.
   That preflight failed closed; it did not publish an integration. The separate
   [F01 follow-up](FOLLOWUP-PYTEST-DIAGNOSTICS.md) retains the reproduction.
7. The engine refused to silently change the frozen integration selector. Used
   checked `--reconcile-plan` with the unchanged plan/base, preserving the
   accepted commit and old ledger backup:
   `.cld/n06/ledger.json.reconcile-7143fa8bd02c4ac89d3232ecebe59b3c.bak`.
   Integration-only run `cb38fa7314c94dc68f5e6c6ebe082114` then tested the frozen
   N06 suite: **53 passed in 5.45 s**, CLD gate 3. No further model calls.
8. Fast-forwarded the working branch to that verified integration. The entire
   original adjacent group then passed independently on final source:
   **232 passed, 1,098 deselected, two existing deprecation warnings, in 55.26 s**.
   Covered all executor fixtures, process lifecycle, launcher environment merging,
   credentials removal, Codex/Claude adapters, recursion and N05 admission.
9. Wheel/sdist, isolated bundle and parity checks: **18 passed in 40.10 s**.
   Regenerated five providers for both hosts from committed source `7b1ab0e`;
   40 core Python files match across ten bundles, and all provider bytes match.
   Ten outside-checkout standalone checks prove direct/nested CLI blocking;
   the six legacy bundles also launch local Python children with the marker.
   Five tracked Claude packages pass freshness checks; portable Codex plugins
   and catalog regenerated. Artifact checks performed no inference.

Counts overlap: the 53 N06 cases are included in the 232-test adjacent group.
Cross-platform N06 CI: pending push/run identification at this checkpoint.

## Measured usage

| Call | Input | Output | Cached input (subset) | Derived total |
|---|---:|---:|---:|---:|
| Validation | 118,580 | 1,518 | 100,864 | 120,098 |
| Implementation | 725,929 | 16,318 | 658,176 | 742,247 |
| **Total** | **844,509** | **17,836** | **759,040** | **862,345** |

Two live calls total, no paid retry or substitution. Deadline: 900 seconds per
dispatch. Cumulative admission estimate: 1,200,000 tokens; actual total remained
below it. The implementation exceeded its 600,000 per-call reservation by
142,247 tokens; one attempt overrun is recorded in the original ledger. Admission
reservations are not provider-enforced hard caps. Uncached input: 85,469 tokens.
Cached tokens are a subset of input, not added again. Cost and lead usage are
unavailable. Both calls requested fast; actual priority routing had no independent
tier telemetry. The reconciled integration-only ledger omits validation from its
derived usage, so use the original backup/records for the full slice total above.

Global Codex config matches its pre-call digest exactly. No persistent global
setting changes, installs, release promotion or model calls after implementation.
Private raw logs, probe repositories and old failed integration evidence remain
local; successful CLD collection removed its owned production worktree.

## Next sitting

Stop after N06 for token availability. Require green N06 CI before N07. N07/N08
remain authorized through exact Luna/max/fast. Check current exact-spec evidence
first and reuse it if fresh; do not force another canary unnecessarily. Keep the
Windows self-test access-limit instruction in subsequent executor briefs.
F01 is an additional documented follow-up, not implemented in this slice.
