# Enabling executor tracing (Langfuse)

Tracing is **optional and OFF by default**. When on, the engine emits one Langfuse span per
executor dispatch (`cld.tracing.record_dispatch`) recording: slice id, model, token usage, the
judge's accept/reject, attempt count, diff size, and failing tests. Useful for **cost/token
visibility** and for **diagnosing the judge** (you can see "executor succeeded, judge scored it
fail"). It does NOT verify that green code survives live data — that's the authoring rules'
job (see `authoring-plans.md`), not tracing.

## It's off until BOTH are true

1. the `langfuse` package is importable (`pip install langfuse`), and
2. these env vars are set:

| Var | Required | Value |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | yes | project public key (`pk-lf-...`) |
| `LANGFUSE_SECRET_KEY` | yes | project secret key (`sk-lf-...`) |
| `LANGFUSE_HOST` | no | `https://cloud.langfuse.com` (EU, default) or `https://us.cloud.langfuse.com` (US), or a self-hosted URL |

If the keys are absent, `record_dispatch` silently no-ops (tracing simply stays off — it never
breaks the build). If `langfuse` isn't installed, same: no-op.

## Turn it on (free cloud tier)

```bash
pip install langfuse
# create a free project at https://cloud.langfuse.com, copy its keys, then:
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
# optional: export LANGFUSE_HOST=https://us.cloud.langfuse.com
```
Windows PowerShell: `$env:LANGFUSE_PUBLIC_KEY = "pk-lf-..."` etc.

## Verify it's actually live

`run_delivery.py` prints a status line at the start of every build:

- `tracing: ON (langfuse -> https://cloud.langfuse.com)` — spans will be emitted.
- `tracing: OFF (set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY to enable; ...)` — keys not set.
- `tracing: OFF (langfuse not installed)` — `pip install langfuse`.

Check that line before relying on traces — "the docs say tracing is available" is not the same
as "tracing is on for this run."
