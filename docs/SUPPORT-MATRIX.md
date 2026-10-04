# Current support and evidence matrix

Updated 2026-10-04 for **v0.4.2**. Lead host and executor provider are independent
choices. Every pair below has a generated standalone bundle; plugin packaging
exists for both hosts. Packaging and offline tests do not establish discovery,
account/model access, live platform behavior or current vendor compatibility.

## Host/provider coverage

The [v0.4.2 publication record](plans/v0.4.0-review-fixes/PUBLICATION-0.4.2.md)
records all ten bundles, both plugin formats, matching shared engine files and
four passing Windows/Ubuntu × Python 3.11/3.14 CI jobs. Offline provider tests
and bundle checks are distinct from the live observations below.

| Lead host | Executor | v0.4.2 bundle/package | Recorded live CLD build |
|---|---|---|---|
| Codex | OpenCode | Verified | Windows, exact Kimi K3; [T14](plans/codex-support/T14-EVIDENCE.md) |
| Codex | Antigravity | Verified | No end-to-end host/provider proof recorded here |
| Codex | Cursor | Verified | No end-to-end host/provider proof recorded here |
| Codex | Codex CLI | Verified | Windows, Luna/max [T16](plans/codex-support/T16-EVIDENCE.md); Luna/max+fast [N05–N08/F01](plans/v0.4.0-review-fixes/REMEDIATION-N04-N08.md) |
| Codex | Claude Code CLI | Verified | Windows, `claude-sonnet-5@low`, unsandboxed Codex lead; [Claude executor evidence](plans/claude-executor/EVIDENCE.md) |
| Claude Code | OpenCode | Verified | No end-to-end host/provider proof recorded here |
| Claude Code | Antigravity | Verified | No end-to-end host/provider proof recorded here |
| Claude Code | Cursor | Verified | No end-to-end host/provider proof recorded here |
| Claude Code | Codex CLI | Verified | Windows, Luna/max+fast, accepted and integrated slices; [Claude executor build, sitting 2](plans/claude-executor/EVIDENCE.md) |
| Claude Code | Claude Code CLI | Verified | No end-to-end host/provider proof recorded here |

“No proof recorded here” describes this matrix's evidence coverage, not a claim
that a pairing is unsupported. Adapter-level canaries are narrower: the
Cursor direct-Node long-prompt check was recorded on 2026-06-22 with
cursor-agent 2026.06.15, and the Claude executor's isolated probe/validation
ran on Windows with CLI 2.1.286. Their results do not verify every lead surface.

## Discovery evidence

- **Codex standalone CLI and VS Code:** [T14](plans/codex-support/T14-EVIDENCE.md)
  records app-server discovery and an actual IDE skill invocation of
  `cross-llm-opencode`, including a read-only vendored-driver preview. This does
  not prove invocation of every later provider skill or IDE version.
- **Codex plugins:** [T13B](plans/codex-support/T13B-EVIDENCE.md) records the
  original three local plugins. Later Codex and Claude executor plugin
  discovery, and IDE plugin discovery, remain unverified. All five packages
  and their catalog are generated and checked separately.
- **Claude Code:** [T14](plans/codex-support/T14-EVIDENCE.md) records the existing
  OpenCode plugin skill in `/skills`. The [Claude executor handoff](plans/claude-executor/HANDOFF.md)
  records all five installed Claude-host skills and model-free checks including
  the Claude executor picker. This is distinct from fresh five-plugin
  marketplace discovery and from end-to-end execution of every pairing.

## Boundaries to retain

- A successful `codex:gpt-6-luna@max+fast` dispatch proves the requested spec was
  exercised. Independent actual-tier routing telemetry remains unverified;
  absent telemetry must not be advertised as confirmed priority processing.
- Live POSIX/macOS dispatch, macOS discovery and actual Ubuntu Codex CLI flag
  inspection remain unverified. Offline native POSIX path/process tests are
  covered by CI; they do not call a real provider.
- A sandboxed Codex lead for the Claude executor remains unverified. Its
  recorded canary used `danger-full-access`; that is evidence provenance,
  not a recommendation to bypass host permissions.
- Live provider mid-process interruption remains unverified. The
  [T19A process-death/resume proof](plans/codex-support/T19A-EVIDENCE.md) is
  provider-independent; the T14/T16 live restarts occurred after acceptance.
- Model catalogs and CLI layouts are snapshots. Validate exact selected
  models/accounts/configuration under existing authorization. Missing usage
  remains unknown, and admission budgets cannot hard-cap an in-flight call.

The [T19B matrix](plans/codex-support/T19B-MATRIX.md) remains the historical
four-provider fixture-replay record. Later dated plans and publication records
retain their original measurements; use this page for the current summary.
