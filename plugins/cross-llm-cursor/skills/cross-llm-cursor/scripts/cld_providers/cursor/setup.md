## Cursor CLI setup

1. Install Cursor (cursor.com) and sign in with your account.
2. The `cursor-agent` CLI is bundled with Cursor. Verify it is on PATH:
   `cursor-agent --version`
   On Windows the versioned binary lives at:
   `%LOCALAPPDATA%\cursor-agent\versions\<latest>\cursor-agent.cmd`
   The executor auto-resolves the lexically-latest versioned path; override with
   `CURSOR_AGENT_CMD=<path>` if auto-detection fails.
3. Verify account status:
   `cursor-agent about`
   (Should print your subscription tier and active default model.)
4. Verify short-prompt headless operation:
   `cursor-agent -p "Reply with the single word: ok" --output-format json --force --trust --workspace <tmpdir>`
   (Should emit a JSON object with `"type":"result"` and `"is_error":false`; exit code 0.)

### Windows note

The top-level `cursor-agent.cmd` shim routes through `.cmd -> .ps1 -> node`. For long
multi-line prompts the shim mangles argv so `--trust` / `--workspace` do not register.
Short prompts work via the shim (feasibility probes, --list-models, about).

The core hang bug (cursor-agent 2026.06.12) is FIXED in 2026.06.15. The remaining
issue is the Windows shim only. The deferred fix is to invoke `node.exe index.js`
directly with `CURSOR_INVOKED_AS=cursor-agent` env, bypassing the shim entirely --
mirroring the OpenCode `.exe` fix. This is not yet applied; real slice dispatch
(long prompts) will fail until the direct-node fix lands.

### Cost

Cursor dispatches are billed against your Cursor subscription (server-side). There is
no per-dispatch cost field in the API response. Monitor usage at cursor.com or in the
Cursor TUI (/usage). Run `cursor-agent about` to check your current subscription tier.
