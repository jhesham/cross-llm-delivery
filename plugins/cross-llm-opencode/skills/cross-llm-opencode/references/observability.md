# Observability — telemetry, `--status`, and dashboards

cross-llm-delivery emits a structured **event** per build-lifecycle moment. By default those events
go to a local JSONL stream the lead agent reads; optionally they also fan out to any
OpenTelemetry-compatible dashboard. Zero config required — dashboards are opt-in.

## Default: local, zero-config (always on)

Every build writes `<repo>/.cld/events.jsonl` (gitignored scratch). One JSON record per line:
`run_start`, `layer_start`, `slice_start`, `dispatch_start`, `dispatch_end`, `judge_verdict`,
`retry`, `escalate`, `needs_repair`, `slice_done`, `layer_done`, `run_done`. Every `dispatch_*`
record carries `model`, `rung`, and `source` (`tag` / `default` / `auto` / `escalated`), so the
stream always says **which model ran which slice and why**.

Read it two ways:

- **`python run_delivery.py --status`** — a compact digest the lead agent polls between turns:
  run id, layer position, done/pending/running counts, each in-flight slice's model + elapsed,
  cumulative tokens + cost, gate, and a **by-model rollup** (slices + tokens + **$cost** grouped by
  model — flat-rate slices show `$0.00`, a pinned premium slice shows its real spend).
- **`python run_delivery.py --watch [--interval N]`** — repaints `--status` every N seconds (a tiny
  human terminal view; `Ctrl-C` to stop). Equivalent to `tail -f .cld/events.jsonl`.

The stream is live-flushed, so `--status` is fresh mid-build. To monitor in real time, dispatch the
build in the **background** and poll `--status` between turns (see SKILL.md).

## Optional: any OpenTelemetry backend (opt-in)

Set an OTLP endpoint and the same events also export as nested **spans** (`run` → `dispatch`) with
GenAI semantic attributes (`gen_ai.request.model`, `gen_ai.usage.input_tokens` /
`output_tokens`) plus `cld.slice_id` / `cld.rung`. The local JSONL stream never changes.

Install the SDK + HTTP exporter once:

```bash
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

Then point it at a backend:

### Arize Phoenix — easiest local, no account

```bash
pip install arize-phoenix && phoenix serve            # UI at http://localhost:6006
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:6006/v1/traces
```

### Langfuse — two-keys convenience (cloud or self-hosted)

Langfuse is OTLP-native, so it's reached through the same seam. Just set the keys — the endpoint and
Basic-auth header are derived automatically:

```bash
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
# export LANGFUSE_HOST=https://your-langfuse        # optional; defaults to cloud.langfuse.com
```

(Equivalent explicit form: `OTEL_EXPORTER_OTLP_ENDPOINT=$LANGFUSE_HOST/api/public/otel/v1/traces`
plus `OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64(pk:sk)>"`.) This replaces the old
bespoke Langfuse Python-SDK path — there is now one OTel path for every backend.

### Self-host (Grafana Tempo / Jaeger) and hosted (Honeycomb / Grafana Cloud)

Any OTLP/HTTP collector works — set the endpoint (and headers for auth):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces
export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=YOUR_API_KEY"
```

## Verifying activation

The build header prints the live state:

```
telemetry: .cld/events.jsonl (local)
otel: ON -> https://cloud.langfuse.com/api/public/otel/v1/traces
```

`otel: OFF (...)` means JSONL-only (the default). Everything is **best-effort and guarded**: a missing
SDK, an unreachable endpoint, or a failing sink never breaks a build — the local stream always works.
