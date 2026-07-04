## Cursor executor

**Default workhorse:** `cursor:composer-2.5` (cheap-metered, Cursor's Composer model)

### Locked invocation form (headless)

```
cursor-agent -p "<task>" --output-format json --workspace <workdir>
             --model <model> --force --trust
```

- `--output-format json` emits a SINGLE JSON object (NOT JSONL) on success:
  `{"type":"result","subtype":"success","is_error":false,"result":"...","usage":{...}}`
- `--force` auto-approves writes in the workspace (required for headless operation).
- `--trust` skips the workspace-trust prompt (required for headless operation).
  NEVER invoke without both flags -- bare invocation opens an interactive TUI that hangs.
- Token counts are at `usage.inputTokens` / `usage.outputTokens` / `usage.cacheReadTokens` /
  `usage.cacheWriteTokens`. There is NO per-dispatch cost field; cursor billing is server-side.
- The flags above are the logical form. On Windows the executor dispatches this via the
  bundled Node entrypoint directly rather than the `cursor-agent.cmd` shim -- see
  "Windows dispatch" below.

### Auth

Cursor uses subscription-based billing. Authenticate by signing into Cursor (cursor.com).
The `cursor-agent` CLI uses the same account credentials. Run `cursor-agent about` to
verify your subscription tier and active model.

### Windows dispatch: direct-node (not the .cmd shim)

On Windows the `cursor-agent.cmd` shim mangles long/multi-line `-p` prompts (it drops
`--trust` / `--workspace`, causing "Workspace Trust Required" failures on real slices).
The executor therefore bypasses the shim: it resolves the lexically-latest
`%LOCALAPPDATA%\cursor-agent\versions\<v>\index.js` and invokes it with the bundled
`node.exe` directly (`[<node>, <version>\index.js] -p ...`), setting
`CURSOR_INVOKED_AS=cursor-agent` and closing stdin. This is the path verified working on
cursor-agent 2026.06.15 with a long multi-line prompt (the earlier 2026.06.12 core hang is
also fixed in that build). Override the binary with `CURSOR_AGENT_CMD=<path>` if needed.

Live-validated 2026-06-22: a real long multi-line slice via direct-node wrote the file on disk
(exit 0, valid result JSON), so `cursor:composer-2.5` is `verified` and offered in the shortlist.

TLS interception (corporate proxy / AV MITM, e.g. Norton): cursor's bundled node uses its own CA
store and would fail HTTPS to the Cursor API (writing nothing — a silent empty diff). The executor
auto-sets `NODE_OPTIONS=--use-system-ca` for the bundled node so it trusts the OS trust store; no
action needed on intercepted machines.
