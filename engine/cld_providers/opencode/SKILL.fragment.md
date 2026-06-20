## OpenCode executor

**Default workhorse:** `opencode:opencode/deepseek-v4-pro` (cheap-metered, solid headless perf)

### Locked invocation form (verified on Windows)

```
opencode run "<task>" -m opencode/<provider/model> --format json --dir <workdir>
    --dangerously-skip-permissions --port
```

- `--format json` emits JSONL (one event per line); `parse_opencode_usage` reads the
  `step_finish` event(s) for token counts.
- `--dangerously-skip-permissions` is required for headless autonomy in isolated worktrees.
- `--port` (bare, no value) forces a fresh local server per dispatch; prevents stale session joins.
- `--dir <workdir>` scopes file writes to the target repo (clean worktree isolation confirmed).
- On Windows the npm shim is `opencode.cmd`, but the real `opencode.exe` must be used for
  long prompts (the `.cmd` shim routes through `cmd.exe /c`, which mangles multi-line argv).
  The executor auto-resolves the real `.exe` behind the shim; override with `OPENCODE_CLI_CMD`.

### Auth

Authenticate once per provider via the OpenCode TUI or `opencode auth add <provider>`.
Credentials are stored locally. Cost is billed per token at the provider's rates (not flat-rate).
