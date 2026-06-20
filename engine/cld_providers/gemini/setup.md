## Gemini CLI setup

1. Install Node.js (v18+ recommended).
2. Install the Gemini CLI: `npm install -g @google/gemini-cli`
3. Authenticate: `gemini auth login` (opens a browser; credentials stored in OS keychain).
4. Verify headless operation: `gemini -p "print hello" --yolo --skip-trust -o json`
   (should return JSON with a stats block; exit code 0).

### Windows note

The npm shim is `gemini.cmd`. The executor auto-detects this on Windows (`os.name == "nt"`).
Override with `GEMINI_CLI_CMD=gemini.cmd` if auto-detection fails.

### Flat-rate plan

The `gemini:gemini-3.1-pro-preview` workhorse runs on a flat-rate Google One AI Premium
subscription. Token usage is $0 marginal; quota (rolling window) is the binding constraint.
The `run_plan_parallel` quota gate defers slices when usage is high to avoid exhausting the window.
