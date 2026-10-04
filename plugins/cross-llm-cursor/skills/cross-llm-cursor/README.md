<!-- GENERATED from cross-llm-delivery (provider: cursor, v0.4.2) - do not edit here; edit the monorepo source. -->

# cross-llm-cursor (Claude Code lead)

A self-contained cross-llm-delivery skill: Claude Code leads the build and the
cursor CLI implements each slice. The engine and driver are vendored
under `scripts/`; no pip install is needed. Start with [SKILL.md](SKILL.md).

**Independent project; not affiliated with or endorsed by Anthropic or OpenAI.
Claude, Claude Code, Codex and other names are trademarks of their owners.**

## Scope

Use it for contract-driven, multi-slice implementation: the lead writes slice
contracts and commits acceptance tests, the executor implements each slice in a
Git worktree, and the engine independently runs acceptance and integration.
Debugging and tiny edits are better handled directly by the lead.

## Requirements

- Python 3.11+ and Git.
- The chosen lead (Claude Code) and an installed, authenticated
  cursor executor CLI; see [provider setup](references/provider-setup.md).
- Local Claude Code and Codex CLI/IDE workflows, subject to their actual skill
  and plugin discovery limitations. ChatGPT web, claude.ai and Cowork are not
  supported surfaces.

Installation: [INSTALL.md](https://github.com/jhesham/cross-llm-delivery/blob/main/INSTALL.md).
Limits: [KNOWN-ISSUES.md](https://github.com/jhesham/cross-llm-delivery/blob/main/KNOWN-ISSUES.md).
Evidence: [support matrix](https://github.com/jhesham/cross-llm-delivery/blob/main/docs/SUPPORT-MATRIX.md).
Recorded evidence includes live Windows builds and Ubuntu/Windows CI; live
POSIX/macOS dispatch and full five-plugin IDE discovery remain unverified.

## What installing and using it does

- Runs the bundled Python engine locally; nothing is installed system-wide.
- Launches the selected executor CLI under your account and configuration.
- Creates Git worktrees, `refs/cld/*` refs and `.cld/` logs, events and a
  ledger (`.cld-ledger.json` by default; custom ledger paths are possible).
- Runs acceptance/integration tests, project commands and Git hooks with your
  user privileges. A worktree is **not a security sandbox**.

There is no publisher-operated service to use or sign up for. Not all network
traffic goes through one CLI: the selected executor can send prompts and
repository content to its configured provider/endpoints; optional DeepEval
Anthropic grading reads `ANTHROPIC_API_KEY`; OTLP export, when configured with
`OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_HEADERS` or
`LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` (with the OpenTelemetry SDK),
sends dispatch metadata; and project subprocesses can use the network too.
Local events are always recorded during execution; those events are not
exported externally unless telemetry export is configured. Logs and provider output may contain sensitive
data and are not guaranteed to be redacted. Do not paste secrets into plans,
briefs, logs or support requests.

Authentication and billing belong to the executor: the Claude executor removes
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` and
requires a claude.ai subscription login in an isolated, no-persistence session;
other executors use the installed CLI, account and configuration with plan,
API or provider billing as applicable. CLD charges no separate inference fee;
dollar costs may be unknown.

Details: [PRIVACY.md](PRIVACY.md) and [SECURITY.md](SECURITY.md).

## Reviewer preview (no inference)

From this bundle directory, with an existing Git repository at an absolute
path:

```bash
python scripts/run_delivery.py examples/demo-plan.md --repo <absolute-git-repo> --host claude-code --dry-run --json
```

Expected: `"gate_code": 0`, `"run_id": null` and `"layers": [["T1", "T3"], ["T2"]]`
for [the demo plan](examples/demo-plan.md). The preview dispatches no executor,
spends nothing on models and writes nothing to the repository. It is a plan
preview, not a live acceptance run or demo build.

## Support

Questions and bugs: [GitHub Issues](https://github.com/jhesham/cross-llm-delivery/issues).
Vulnerabilities: private reporting as described in [SECURITY.md](SECURITY.md).
