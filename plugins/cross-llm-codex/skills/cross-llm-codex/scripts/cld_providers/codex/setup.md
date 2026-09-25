## Codex CLI executor setup

Install and sign in to a current Codex CLI through the official Codex setup instructions. Verify the installed binary with `codex --version` and `codex exec --help`; CLD feature-tests the required noninteractive flags before dispatch. On the target host, choose a model ID and supported effort explicitly, then run a preview with `--dry-run --json` and a budgeted one-slice build. `codex debug models` may show a catalog, but it is not a validation or entitlement guarantee.

Codex uses the current user's documented CLI authentication and configuration. CLD does not read or copy credentials, and the prompt travels on stdin. The default write sandbox is `workspace-write`; this adapter does not enable full-access or approval-bypass flags. Keep CLD's worktree root inside the selected repository and retain the independent acceptance/integration gate.

Usage cost in USD is unknown unless a future CLI event supplies it. Under a cost ceiling, the existing unknown-usage policy blocks by default. Pass an explicit model as `--executor codex:<exact-model-id>@<supported-effort>` and select a validation policy before live execution.
