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

### Auth

Cursor uses subscription-based billing. Authenticate by signing into Cursor (cursor.com).
The `cursor-agent` CLI uses the same account credentials. Run `cursor-agent about` to
verify your subscription tier and active model.

### Known issue: long-prompt headless dispatch (Windows .cmd shim)

**Core hang: FIXED on cursor-agent 2026.06.15.** The earlier `2026.06.12` version hung
indefinitely on long multi-line prompts. The 06.15 build resolves this -- direct-node
invocation with a long prompt now completes cleanly (exit 0, valid result JSON, actual
file writes verified).

**Remaining issue (as of 2026-06-19): Windows .cmd shim mangles long prompts.**
The `.cmd -> .ps1 -> node` shim route mangles long/multi-line `-p` argv so `--trust` /
`--workspace` do not register, causing "Workspace Trust Required" failures on real slice
prompts. Short prompts (list-models, about, feasibility probes) still work via the shim.

**Deferred fix:** make `_cursor_cmd()` invoke the versioned `node.exe index.js` directly
(mirroring the OpenCode `.exe` fix) with `CURSOR_INVOKED_AS=cursor-agent` env and
`stdin=DEVNULL`. This is the direct-node path that was verified working on 06.15 with a
long multi-line prompt. The fix is NOT yet applied -- CursorExecutor still dispatches via
the `.cmd` shim and real long-prompt slices will fail until the direct-node fix lands.
Override with `CURSOR_AGENT_CMD=<path>` if you have a working binary.
