# Optional phase — Codex as an implementation provider

This phase is separate from using Codex as the lead. T15's [offline contract evidence](T15-EVIDENCE.md) and T16's [Windows executor evidence](T16-EVIDENCE.md) are recorded separately. T16 and optional M6 are complete after four-job CI. This optional phase does not hide any required review fix.

## T15 — Codex executor contract and fixtures

Dependencies: T08/T09/T11. Estimate: 8–12k. Files: proposed `engine/cld_providers/codex/`, `tests/fixtures/codex/`, provider contract tests, [compatibility notes](SOURCES.md).

- [x] Re-read current official noninteractive docs and inspect `codex --version` / `codex exec --help` on the available Windows target. Feature-test required flags rather than assert a universal minimum from one version; Linux CLI inspection is a T16 target-host gate because WSL is unavailable locally.
- [x] Define argv/stdin, working-root, sandbox, configured model/effort, timeout, completion/error, session isolation, and JSONL usage contracts. Use capability detection with actionable errors for missing required flags.
- [x] Use fresh executor sessions by default; do not resume the lead session or `--last`. Prevent recursive CLD invocation through executor role instructions and a dispatch-depth guard.
- [x] Capture sanitized real success/failure/usage events only when a live call is authorized; record source version and context. Before then, use clearly labeled synthetic fixtures for parser development, not live-validation claims. T15 uses synthetic fixtures; live capture remains T16.
- [x] Specify handling for malformed/truncated JSONL, unknown event types, nonzero exit, turn failure, missing successful completion, multiple turn completions, stderr-only auth errors, and interrupted output.
- [x] Select model IDs through explicit configuration or verified discovery; no guessed default, obsolete catalog entry, fixed price, or assumed subscription entitlement. Define unknown-cost reporting and validation policy.

**Gate:** Contract and tests describe both real defaults and fixtures. Local help proves supported flags; actual usage/completion fixtures require recorded evidence before declaring live support. No default permission-bypass flag is permitted by this design.

## T16 — Codex provider and end-to-end proof

Dependencies: T15/T13. Estimate: 10–18k. Files: `cld_providers/codex/provider.py`, package/init/resources, provider registry/generator discovery, tests and examples.

- [x] Implement the adapter using shared process deadlines, stdin prompt transport, explicit cwd/root, and supported sandbox options. Preserve the user's auth/config through documented interfaces; never read or copy credentials into artifacts.
- [x] Require valid dispatch completion and independently verified candidate acceptance. Codex JSONL file-change events and final prose are diagnostics, not the allowed-files authority.
- [x] Normalize usage without double-counting cache/reasoning categories; retain raw usage and mark derived totals/cost uncertainty. Feed validation and admission budgets through the shared policy.
- [x] Register the provider and generate both host variants; remove fixed three-provider assumptions only where needed while preserving existing output names.
- [x] Test long prompts/Unicode, spaces in paths, errors, cancellation, failed auth, unsupported CLI, usage, no recursive dispatch, and worktree isolation offline.
- [x] Run one user-selected trivial live slice, a controlled admission stop/resume and fresh-process integration. Record exact CLI/model/host/platform/usage, provider suite and isolated bundle imports. [Evidence](T16-EVIDENCE.md) narrows this to Windows; live process interruption and POSIX dispatch remain unverified.

**Gate:** Optional M6 passes the same acceptance/recovery contracts as other providers. T17's offline matrices and T19's planned rehearsal now include four providers. One Windows live canary passed; POSIX live dispatch and process-level interruption remain explicit limitations, not implied support.
