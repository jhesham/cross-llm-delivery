## OpenCode CLI setup

1. Install Node.js (v18+ recommended).
2. Install the OpenCode CLI: `npm install -g opencode-ai`
3. Authenticate with your chosen model provider through the installed
   OpenCode TUI or its supported auth flow (`opencode auth --help`). Do not
   infer account/model access from the bundled catalog.
4. Inspect `opencode --version`, `opencode run --help` and `opencode models`.
   These are read-only discovery, not proof of authentication/entitlement or
   successful headless execution. Use CLD's explicit validation policy for an
   authorized one-slice validation; do not dispatch an unsolicited live probe.

### Windows note

The npm shim is `opencode.cmd`. For long prompts, `cmd.exe /c` (invoked by the shim) mangles
the argv, causing the CLI to fall back to interactive mode silently. The executor automatically
resolves the real `opencode.exe` at `<npm-prefix>/node_modules/opencode-ai/bin/opencode.exe`.
Override with `OPENCODE_CLI_CMD=<path>` if auto-detection fails.

### Cost

OpenCode dispatches are metered at the underlying model provider's token rates.
Catalog free/flat labels are snapshots, not proof of current price. Missing
completed usage is unknown. Any real canary/validation requires the user's
exact model and spend authorization; CLI discovery alone does not grant it.
Monitor usage with `opencode stats`.
