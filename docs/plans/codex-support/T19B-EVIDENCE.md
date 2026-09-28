# T19B — support evidence, rollback and overhead

Local acceptance complete; closing source requires all four CI jobs before
signoff. Parent T19 closes with T19A/T19B, while M5 and T20 remain open. No
production defect was demonstrated: this child changes tests and tracking only.

## Offline and host evidence

`test_t19b_matrix.py` generates all four providers for both host bundles and
launches each in a fresh interpreter with only its own vendored scripts on
PYTHONPATH. Each process asserts its loaded engine path and single-provider
registry. It replays success and nonzero-exit fixtures against real Git; only
success captures the changed file, and failed output retains partial files
without reporting a candidate diff. Antigravity logs/transcripts are kept outside
the consumer checkout. OpenCode/Cursor are captured fixtures; Codex/Antigravity
are explicitly synthetic protocol fixtures. No actual provider binary is run.

Eight bundle cases and the documentary contract passed locally. Two rollback
cases passed (one after correcting a test assumption: status with accepted work
correctly returns gate/exit 6, not zero). Total: **11 unique passing cases**.
The fake Codex capability fixture was corrected to match the recorded T16
version/help syntax; this was test scaffolding, not a production capability bug.
See [matrix and evidence levels](T19B-MATRIX.md) and
[rollback/merge procedure](T19B-ROLLBACK.md).

The actual Windows Codex standalone CLI, IDE invocation, local marketplace and
Claude plugin discovery proofs remain [T14](T14-EVIDENCE.md) and
[T13B](T13B-EVIDENCE.md), at their recorded versions. Fourth Codex-plugin discovery
was not observed separately; its packaging/catalog is offline-tested. Windows
live OpenCode and Codex executor canaries under a Codex lead are recorded in T14
and [T16](T16-EVIDENCE.md). This does not establish live Claude-lead execution,
live provider mid-process recovery, live POSIX dispatch or macOS support.
Actual Ubuntu Codex flags were not inspected; no live POSIX claim is made.
These are explicit limitations, not silently generalized passes. No new live
Codex interruption call was authorized or performed.

## Rollback and inspectable integration

Fresh CLI processes migrate a legacy ledger and preserve its exact backup.
Before dispatch, the rehearsal archives the schema-2 envelope, restores exact
legacy bytes at the original path, remigrates explicitly and preserves the
archive/HEAD. After new work, it keeps the active schema-2 ledger, both archives,
accepted SHA/ref and backups; it does not restore old state or run old code on
the new schema. Fresh compatible integration proves the persisted integration
ref/SHA and accepted ancestry, leaving the original checkout untouched. The
guide explains the exact-SHA review/merge step without performing a main merge.

## Measured sizes

Fresh generated SKILL.md UTF-8 byte counts; estimates are **ceil(chars / 4)**,
not model-tokenizer output or billing counts. Banner SHAs do not alter length.

| Host | Provider | Bytes | Estimated tokens |
|---|---|---:|---:|
| codex | antigravity | 3,178 | 795 |
| codex | opencode | 3,157 | 790 |
| codex | cursor | 3,129 | 783 |
| codex | codex | 3,212 | 803 |
| claude-code | antigravity | 22,247 | 5,562 |
| claude-code | opencode | 23,397 | 5,849 |
| claude-code | cursor | 25,367 | 6,341 |
| claude-code | codex | 4,427 | 1,107 |

The sampled **one-slice** T19A blocked status response is **1,442 bytes**, about
361 estimated tokens. This measures that ledger only; it is not a maximum-size
claim for arbitrary builds. Data: `.cld/t19b/measurements.json`. Codex is below
the 1–2k entry target; the older three Claude entries exceed it. T20 owns their
reference split and regeneration. Maintainer defaults in SESSION-GUIDE now
contain failures using one worker, one production attempt plus needed validation,
short briefs and explicit deadlines; public CLI defaults were not changed.

## Bounded dogfood outcome and usage

Baseline `ee11f89` committed the documentary contract/test before the live draft.
The exact installed `opencode/kimi-k3` model was listed. One isolated OpenCode
1.18.29 `run --pure --agent plan --format json` call used a facts-only supplied
brief, a temporary cwd and local global/plan-agent tool denial. Syntax was
checked against [OpenCode permission documentation](https://opencode.ai/docs/permissions/)
and installed CLI help. The process used CLD's native process runner with a
**90-second** deadline; this was CLI drafting, not CLD acceptance or a probe.

It timed out at **90.007585 seconds**, with no draft, no observed tool calls and
no completed steps. No retry, model substitute, global configuration change or
fresh validation call followed. The lead completed the matrix directly. Session
`ses_f17ecf572ffe3xf0f9rLknLf95` and a read-only local export show one unfinished
assistant response. **Full usage/cost is unknown**; zero completed usage is not
evidence of a free call. Ignored artifacts: `.cld/t19b/request-result.json`,
`processes/cld-process-9mnl3oyd/`, `usage.json`, `opencode-session.json`.

T19A's separately recovered **lower bound** was 825,553 tokens/USD 0.900996,
including 667,450 cache-read; final interrupted usage remains unknown. No paid
retry launched in either child. Lead usage counters are unavailable; T19B's
4–7k allowance was an estimate, not measured consumption. Fixture review,
rollback and direct fallback added overhead. Three successive no-candidate
draft/implementation timeouts (T18, T19A, T19B) do not demonstrate delegation
savings. Keep paid retries off by default; T20 should reassess the value of any
new bounded dogfood contribution rather than increasing spend automatically.

## Closing gates

- [x] Eight isolated bundle/provider fixture replays, success and failure.
- [x] Historical discovery/live levels and missing environments explicit.
- [x] Byte-preserving rollback limits and final integration ref/merge inspection.
- [x] Size/usage measurements and maintainer budget-default review.
- [x] Eleven unique local acceptance cases passed; defect register has no open
  P1 or required P2 item. Full suite remains excluded from live inference.
- Closing source must pass the complete offline suite plus all generator/plugin
  gates in Windows/Ubuntu Python 3.11/3.14 CI before signoff. Save exact-SHA
  metadata to `.cld/t19b/ci-final-jobs.json`; CI is the final combined collection.

T19A's closing source `24ae8f4` passed every job/gate in
[run 36421323442](https://github.com/jhesham/cross-llm-delivery/actions/runs/36421323442).

Verified closing source `d78c7349578b8672ea2332dd029b88451549dc30` passed
all four full-suite jobs and all generator/plugin gates in
[run 36425920464](https://github.com/jhesham/cross-llm-delivery/actions/runs/36425920464).
Exact metadata: `.cld/t19b/ci-final-jobs.json`. Refreshed during T20A; no runtime
change to the T19B rehearsal was needed.
