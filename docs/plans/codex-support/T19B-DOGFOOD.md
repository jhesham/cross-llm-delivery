# T19B bounded CLI dogfood contract

Unlike T19A, delegate only a short documentary draft using OpenCode's read-only
plan agent, `--pure`, an isolated temporary cwd, one call and a native 90-second
deadline. Do not dispatch any other provider, continue a session, read repository
files, invoke tools, edit the product or perform an installation. Exact model:
`opencode/kimi-k3`. This is CLI drafting, not a CLD-accepted implementation.
The lead owns facts, fixture replay, rollback rehearsal and independent acceptance.

Return only Markdown with this title: `# T19B evidence matrix`. Table columns:
Host, Executor, Replay. Exactly eight rows: both `codex` and `claude-code`, each
with `antigravity`, `opencode`, `cursor`, `codex`; every Replay cell `offline`.
Explain that fixture success/nonzero-exit replay proves an offline contract only.
OpenCode/Cursor fixtures are captured; Codex/Antigravity protocol fixtures are
synthetic. No replay is evidence of a live call or actual host discovery.

Facts for a concise prose section (do not invent versions or coverage):
- Windows Codex standalone CLI/app-server and actual VS Code skill invocation,
  local marketplace discovery, and Claude plugin discovery were observed in
  T14-EVIDENCE.md and T13B-EVIDENCE.md. Keep these independent of bundle smoke.
- Live Kimi K3/OpenCode canary under Codex host: Windows only, T14-EVIDENCE.md.
- Live gpt-6-luna@max Codex executor under Codex host: Windows only,
  T16-EVIDENCE.md. Acceptance-to-integration fresh-process restart passed;
  live mid-process interruption remains unverified.
- Windows/Ubuntu Python 3.11/3.14 offline CI is verified. macOS discovery/live
  behavior and live POSIX executor dispatch remain unverified. Actual Ubuntu
  Codex CLI flags were not inspected; no live POSIX support claim.
- T19A Kimi call timed out without edits. A local export recovered 825,553
  provider tokens / USD 0.900996 as a lower bound, including 667,450 cache-read
  tokens. Final interrupted-response usage is unknown. Lead usage unavailable.
- Use one worker, explicit exact model, one production attempt plus any required
  validation allowance, and admission budgets with unknown-usage denial. These
  are not hard in-flight token caps. Keep executor context small and do not
  increase timeouts/budgets to conceal poor delegation outcomes.

Acceptance: `tests/integration/test_t19b_matrix.py::test_kimi_evidence_matrix_contract`.
