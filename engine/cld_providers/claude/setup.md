## Claude Code CLI executor setup

Install Claude Code and sign in with your Claude subscription (`claude auth login`). CLD checks `claude auth status` before any dispatch and requires `authMethod: "claude.ai"`: executor turns use your plan's usage limits, never API billing. `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` are removed from the executor's environment.

CLD launches the native binary without a shell: `CLAUDE_CLI_CMD` (absolute path), else `claude.exe` on PATH (`claude` on POSIX), else the native `node_modules/@anthropic-ai/claude-code/bin/claude.exe` behind an npm `claude.cmd` shim. A shim-only install blocks dispatch (gate 5) naming `CLAUDE_CLI_CMD`.

Each slice runs one isolated session: `--safe-mode` (no CLAUDE.md, skills, plugins, hooks, MCP servers or custom agents), `--restricted` (file tools confined to the worktree; settings, git and tool-configuration writes denied), an empty strict MCP config, tools `Read,Edit,Write,Glob,Grep,Bash` under `--permission-mode dontAsk`, no auto-memory and no saved session. The shell is **not sandboxed**: it runs with your user privileges, like the OpenCode, Cursor and Antigravity executors. A slice that must edit a tool-configuration file may be refused under `--restricted`.

Pass an exact model and effort: `--executor claude:claude-sonnet-5@low` (efforts: low, medium, high, xhigh, max). Aliases such as `sonnet` are rejected. The CLI's `total_cost_usd` is recorded as an estimate only; CLD cost stays unknown, so use token and attempt budgets. Hitting your plan's usage limit is a final error (gate 5): wait for the window to reset, then resume. Validation requires `--validation-policy allow`. Switching account or plan invalidates validation evidence.
