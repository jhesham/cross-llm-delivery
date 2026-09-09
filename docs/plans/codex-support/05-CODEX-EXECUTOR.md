# Optional phase — Codex as an implementation provider

This phase is separate from using Codex as the lead. It can ship after the required release. Keep T15/T16 unchecked and marked deferred unless selected for implementation; their deferral must not hide any required review fix.

## T15 — Codex executor contract and fixtures

Dependencies: T08/T09/T11. Estimate: 8–12k. Files: proposed `engine/cld_providers/codex/`, `tests/fixtures/codex/`, provider contract tests, [compatibility notes](SOURCES.md).

- [ ] Re-read current official noninteractive docs and inspect `codex --version` / `codex exec --help` on target platforms. Record a supported minimum/version range from evidence; do not assume the locally observed 0.153.4 is universal.
- [ ] Define argv/stdin, working-root, sandbox, configured model/effort, timeout, completion/error, session isolation, and JSONL usage contracts. Use capability detection with actionable errors for missing required flags.
- [ ] Use fresh executor sessions by default; do not resume the lead session or `--last`. Prevent recursive CLD invocation through executor role instructions and a dispatch-depth guard.
- [ ] Capture sanitized real success/failure/usage events only when a live call is authorized; record source version and context. Before then, use clearly labeled synthetic fixtures for parser development, not live-validation claims.
- [ ] Specify handling for malformed/truncated JSONL, unknown event types, nonzero exit, turn failure, missing successful completion, multiple turn completions, stderr-only auth errors, and interrupted output.
- [ ] Select model IDs through explicit configuration or verified discovery; no guessed default, obsolete catalog entry, fixed price, or assumed subscription entitlement. Define unknown-cost reporting and validation policy.

**Gate:** Contract and tests describe both real defaults and fixtures. Local help proves supported flags; actual usage/completion fixtures require recorded evidence before declaring live support. No default permission-bypass flag is permitted by this design.

## T16 — Codex provider and end-to-end proof

Dependencies: T15/T13. Estimate: 10–18k. Files: `cld_providers/codex/provider.py`, package/init/resources, provider registry/generator discovery, tests and examples.

- [ ] Implement the adapter using shared process deadlines, stdin prompt transport, explicit cwd/root, and supported sandbox options. Preserve the user's auth/config through documented interfaces; never read or copy credentials into artifacts.
- [ ] Require valid dispatch completion and independently verified candidate acceptance. Codex JSONL file-change events and final prose are diagnostics, not the allowed-files authority.
- [ ] Normalize usage without double-counting cache/reasoning categories; retain raw usage and mark derived totals/cost uncertainty. Feed validation and admission budgets through the shared policy.
- [ ] Register the provider and generate both host variants; remove fixed three-provider assumptions only where needed while preserving existing output names.
- [ ] Test long prompts/Unicode, spaces in paths, errors, cancellation, failed auth, unsupported CLI, usage, no recursive dispatch, and worktree isolation offline.
- [ ] When authorized, run one trivial passing live slice plus a controlled interrupted/resumed case. Record exact CLI/model/host/platform/usage, then run the provider suite and isolated bundle imports.

**Gate:** Optional M6 passes the same acceptance/recovery contracts as other providers. Expand T17/T19 matrices to four providers if this ships; if live evidence is incomplete, mark this provider experimental with the exact limitation rather than implying verified support.
