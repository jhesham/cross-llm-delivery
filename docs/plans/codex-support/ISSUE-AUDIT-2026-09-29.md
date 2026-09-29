# Open-issue audit — 2026-09-29

Reviewed all seven open public issues against published source, offline
regressions and retained downstream Windows run evidence. This audit made no
provider calls and changed no downstream checkout or model-admission state.

| Issue | Disposition | Evidence / remaining work |
|---|---|---|
| [#11: per-run telemetry](https://github.com/jhesham/cross-llm-delivery/issues/11) | Closed as completed | Events live under `.cld/runs/<run_id>/events.jsonl`; same-run steps append, separate builds preserve earlier streams, and legacy flat streams remain readable. |
| [#8: Antigravity POSIX](https://github.com/jhesham/cross-llm-delivery/issues/8) | Keep open | No recorded real macOS/Linux Antigravity build establishes live dispatch support. |
| [#9: Cursor POSIX](https://github.com/jhesham/cross-llm-delivery/issues/9) | Keep open | No recorded real macOS/Linux Cursor build establishes live dispatch support. |
| [#10: Cursor cost capture](https://github.com/jhesham/cross-llm-delivery/issues/10) | Keep open | Cursor parsing captures token usage, not per-dispatch dollar cost; the required real nonzero-cost build is unverified. Unknown cost is now displayed honestly, which does not complete cost capture. |
| [#12: explicitly chosen executor telemetry](https://github.com/jhesham/cross-llm-delivery/issues/12) | Keep open | Explicit build-level selections still emit `source: default`; `chosen` provenance is not implemented. |
| [#13: new provider adapters](https://github.com/jhesham/cross-llm-delivery/issues/13) | Keep open; Codex portion complete | Codex is shipped and live-used on Windows. The broader contributor invitation also covers Qwen Code, Ollama and other adapters. |
| [#14: roadmap](https://github.com/jhesham/cross-llm-delivery/issues/14) | Keep open | This is a living umbrella, with unfinished demo/provider/telemetry work. Its Codex and per-run-telemetry entries need a future editorial refresh. |

## Issue #11 closure evidence

Published code in `engine/cld/cli.py` binds telemetry to the ledger's run,
appends without truncation, and reads the legacy flat stream only when no
bound build exists. Default status follows the default ledger's current build;
use `--ledger` to inspect another retained build. A standalone `--run` selector
was an optional suggestion in the issue and is not implemented.

On 2026-09-29, all 14 focused checks passed:

```text
tests/test_status.py
tests/test_telemetry_emit_points.py
tests/integration/test_build_state.py::test_telemetry_appends_within_run_and_preserves_previous_runs
tests/integration/test_t19_rehearsal.py::test_status_under_writer_and_separate_cli_build_isolation
```

These cover legacy status, current-run events, repeated-step append, prior-run
preservation, and separate CLI builds while a writer is active. The published
runtime source also passed the [four-job CI matrix and generator checks](https://github.com/jhesham/cross-llm-delivery/actions/runs/36542440084).
GitHub confirms closure as completed at `2026-09-29T11:55:42Z`.
Local proofs: `.cld/environment/issue11-verification.xml` and
`.cld/environment/issue11-closure.json`.

## Updated live Codex evidence

A retained downstream Windows CLD build used the exact executor
`codex:gpt-6-luna@max+fast` on 2026-09-29, around 19:05–19:10 Australia/Sydney.
All three production slices passed on the first attempt (15 slice acceptance
tests); verified integration passed at 19:11. Shell commands actually executed.
This supersedes the earlier claim that no live delivery with this requested
model/effort/tier combination had been observed.

Production usage for that build: 370,700 input tokens, including 318,208
cache-read tokens, plus 11,665 output tokens. Reported dollar cost is unknown.
These figures exclude its separate validation attempts. No client source,
prompts, credentials or raw downstream logs are published by this audit.

The retained CLI events report no actual model/effort/service-tier metadata.
CLD's exact requested identity and successful delivery are recorded, but actual
backend fast-tier delivery cannot be established without tier telemetry.
macOS/POSIX behavior, refreshed picker discovery and live interruption retain
their existing evidence boundaries.

Stop after this audit; obtain token-availability confirmation before another
task. Provider calls/usage/cost for the audit itself are zero; lead counters
are unavailable.
