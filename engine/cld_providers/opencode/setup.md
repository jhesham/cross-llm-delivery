## OpenCode CLI setup

1. Install Node.js (v18+ recommended).
2. Install the OpenCode CLI: `npm install -g opencode-ai`
3. Authenticate with your chosen model provider via the OpenCode TUI or:
   `opencode auth add <provider>`
   (Supported: Anthropic, Google, DeepSeek, Moonshot/Kimi, and others.)
4. Verify headless operation:
   `opencode run "print hello" -m opencode/deepseek-v4-flash-free --format json --dir . --dangerously-skip-permissions --port`
   (Should emit JSONL with a `step_finish` event; exit code 0.)

### Windows note

The npm shim is `opencode.cmd`. For long prompts, `cmd.exe /c` (invoked by the shim) mangles
the argv, causing the CLI to fall back to interactive mode silently. The executor automatically
resolves the real `opencode.exe` at `<npm-prefix>/node_modules/opencode-ai/bin/opencode.exe`.
Override with `OPENCODE_CLI_CMD=<path>` if auto-detection fails.

### Cost

OpenCode dispatches are metered at the underlying model provider's token rates.
`opencode/deepseek-v4-flash-free` is free; other models bill real money.
Monitor usage with `opencode stats`.
