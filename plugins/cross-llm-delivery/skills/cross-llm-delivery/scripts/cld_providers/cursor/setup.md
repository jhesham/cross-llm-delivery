## Cursor CLI setup

1. Install Cursor (cursor.com) and sign in with your account.
2. The `cursor-agent` CLI is bundled with Cursor. Verify it is on PATH:
   `cursor-agent --version`
   On Windows the versioned binary lives at:
   `%LOCALAPPDATA%\cursor-agent\versions\<version>\index.js`
   The executor resolves the lexically-latest directory containing that Node
   entrypoint, using its bundled `node.exe` or `node` on PATH. Override with
   `CURSOR_AGENT_CMD=<executable-path>` if auto-detection fails; a shim override
   can reintroduce the long-prompt issue below.
3. Verify account status:
   `cursor-agent about`
   (Should print your subscription tier and active default model.)
4. Only under existing model/spend authorization, verify short-prompt headless operation:
   `cursor-agent -p "Reply with the single word: ok" --output-format json --force --trust --workspace <tmpdir>`
   (Should emit a JSON object with `"type":"result"` and `"is_error":false`; exit code 0.)

### Windows note

The top-level `cursor-agent.cmd` shim routes through `.cmd -> .ps1 -> node`. For long
multi-line prompts the shim mangles argv so `--trust` / `--workspace` do not register.
Short prompts work via the shim (feasibility probes, --list-models, about).

CLD already bypasses the shim by invoking the Node entrypoint directly, setting
`CURSOR_INVOKED_AS=cursor-agent` and closing stdin. This path passed a live
long-prompt slice on 2026-06-22 with cursor-agent 2026.06.15; that build also
resolved the recorded 2026.06.12 core hang. These are version-specific
observations. If the installation layout changes, inspect the resolver and
override instead of assuming every later release has the same behavior.

### Cost

Cursor dispatches are billed against your Cursor subscription (server-side). There is
no per-dispatch cost field in the API response. Monitor usage at cursor.com or in the
Cursor TUI (/usage). Run `cursor-agent about` to check your current subscription tier.
