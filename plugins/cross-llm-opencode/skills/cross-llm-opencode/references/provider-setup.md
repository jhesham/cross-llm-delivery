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

### API keys expire

OpenCode models (`opencode/...`) authenticate with an API key that OpenCode stores
in `~/.local/share/opencode/auth.json` (on Windows,
`%USERPROFILE%\.local\share\opencode\auth.json`). These keys expire. An expired
key makes every dispatch fail with `401 UNAUTHENTICATED` and the message "This API
key has expired"; CLD reports it as an executor dispatch failure, not a model
verdict, so a validation probe that hit it leaves the model untested. Signing in
again does not renew the key. Create a new key in the OpenCode Console
(https://opencode.ai/console/account#api-keys), run `opencode auth login`, choose
OpenCode and paste the new key (it replaces the stored one), and confirm with
`opencode auth list`. Then rerun the step; CLD validates the model again.

### Windows note

The launcher resolves an explicit absolute `OPENCODE_CLI_CMD` override first, then a native
`opencode.exe` on `PATH`, then the verified npm postinstall binary at
`<shim-dir>/node_modules/opencode-ai/bin/opencode.exe` behind `opencode.cmd`. It invokes that
binary directly, without a shell, so long and multiline arguments keep their original argv.
The npm postinstall chooses its platform and CPU build; CLD does not guess alternate package
layouts when its output is missing. An incomplete install fails closed. Set
`OPENCODE_CLI_CMD` to an absolute path to a native executable to use another installation.
Windows `.cmd` and `.bat` overrides are rejected; do not point the override at the npm shim.

On POSIX, the launcher uses an explicit override or native `opencode` found on `PATH`.

### Cost

OpenCode billing depends on the underlying provider, model and account plan.
Catalog free/flat labels are snapshots, not proof of current price. Missing
completed usage is unknown. Any real canary/validation requires the user's
exact model and spend authorization; CLI discovery alone does not grant it.
Monitor usage with `opencode stats`.
