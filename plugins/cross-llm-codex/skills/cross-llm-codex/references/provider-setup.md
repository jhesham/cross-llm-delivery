## Codex CLI executor setup

Install and sign in to a current Codex CLI through the official Codex setup instructions. Verify the installed binary with `codex --version` and `codex exec --help`; CLD feature-tests the required noninteractive flags before dispatch.

CLD launches the native binary without a shell. It uses `CODEX_CLI_CMD` when set (an absolute path to an existing executable), otherwise `codex` on PATH (`codex.exe` on Windows). For an npm-only Windows install, CLD resolves the native `codex.exe` behind the `codex.cmd` shim inside the npm package; if only the shim can be found, dispatch is blocked (gate 5) and names the shim — set `CODEX_CLI_CMD` to the native executable. CLD never dispatches through `cmd.exe`, which can mangle quoted configuration arguments. Run `python scripts/list_models.py --json` from the skill directory for advisory picker choices, then choose a model ID and supported effort explicitly. The picker uses `codex debug models --bundled` without refresh or inference; a listing is not a validation or entitlement guarantee. Older CLIs without that optional command can still use an explicit ID. Preview with `--dry-run --json` before a budgeted one-slice build.

Codex uses the current user's documented CLI authentication and configuration. CLD does not read or copy credentials, and the prompt travels on stdin. The default write sandbox is `workspace-write`; this adapter does not enable full-access or approval-bypass flags. Keep CLD's worktree root inside the selected repository and retain the independent acceptance/integration gate.

Usage cost in USD is unknown unless a future CLI event supplies it. Under a cost ceiling, the existing unknown-usage policy blocks by default. Pass an explicit model as `--executor codex:<exact-model-id>@<supported-effort>` and select a validation policy before live execution.

For explicitly requested max effort and fast mode, use
`--executor codex:gpt-6-luna@max+fast`. CLD emits separate configuration
arguments for `model_reasoning_effort="max"` and `service_tier="fast"`.
Only `+fast` is accepted; unknown tiers and tier suffixes on other providers
fail before dispatch. Fast and tier-unspecified specs have separate validation
evidence. Account/model access still requires validation; this syntax is not
proof that fast service was delivered.

With an explicit tier, warning control events or service-tier diagnostics on
stderr fail the dispatch even if Codex exits zero. Reported actual tiers other
than `fast`/`priority` also fail. No candidate diff is collected on that failure;
the worktree and process logs remain available for inspection. Missing actual
tier telemetry remains unverified; CLD cannot detect an unreported server-side
downgrade. Do not silently remove `+fast` and retry.

The shared dispatch deadline defaults to 600 seconds; read-only CLI probes
default to 30 seconds. For a larger max-effort slice, explicitly configure a
finite positive deadline **before** invoking the driver, for example:

```powershell
$env:CLD_DISPATCH_TIMEOUT = "1200"
```

```bash
export CLD_DISPATCH_TIMEOUT=1200
```

This applies to provider dispatches including validation, not read-only probes.
It does not increase attempt or usage budgets. Restore the previous environment
setting after the build; never increase a deadline or retry paid work automatically.

Configuration checked 2026-09-28 against the official
[Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
