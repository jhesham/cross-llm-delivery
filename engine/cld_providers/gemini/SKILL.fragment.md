## Gemini executor

**Default workhorse:** `gemini:gemini-3.1-pro-preview` (flat-rate plan, $0 marginal cost)

### Locked invocation form (verified on Windows, Phase 0 + four gate dispatches)

```
GEMINI_CLI_TRUST_WORKSPACE=true gemini -p "<task>" -m gemini-3.1-pro-preview \
    --yolo --skip-trust -o json
```

- `--yolo --skip-trust` is required for headless autonomy (YOLO is silently downgraded
  without a trusted workspace).
- `-o json` returns `stats.models.<id>.tokens` captured into `ExecutorResult.token_usage`.
- On Windows the npm shim is `gemini.cmd`; override with `GEMINI_CLI_CMD` env var.
- Gemini exposes no `list_models` CLI command; the catalog entry is static.

### Auth

Authenticate once with `gemini auth login` (stores credentials in the OS keychain).
The flat-rate plan requires a Google One AI Premium subscription (or equivalent).
No per-call billing; quota is the binding constraint, not dollars.
