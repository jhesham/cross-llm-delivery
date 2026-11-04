# Observability — telemetry, `--status`, and dashboards

cross-llm-delivery emits a structured **event** per build-lifecycle moment. By default those events
go to a local JSONL stream the lead agent reads; optionally they also fan out to any
OpenTelemetry-compatible dashboard. Zero config required — dashboards are opt-in.

## Default: local events and durable inspection

Run-scoped events are retained under `<repo>/.cld/runs/<run-id>/events.jsonl`;
compatibility event/summary paths may also exist. Event writes are best-effort.
Durable ledger/usage state drives machine status independently of export.
One JSON record per line:
`run_start`, `layer_start`, `slice_start`, `dispatch_start`, `dispatch_end`, `judge_verdict`,
`retry`, `escalate`, `needs_repair`, `slice_done`, `layer_done`, `run_done`. Every `dispatch_*`
record carries `model`, `rung`, and `source` (`tag` / `default` / `auto` / `escalated`), so the
stream always says **which model ran which slice and why**.

Read it two ways:

- **`python scripts/run_delivery.py --status --repo <dir> --json`** — a compact durable digest:
  run id, layer position, done/pending/running counts, each in-flight slice's model + elapsed,
  cumulative tokens + cost, gate, and a **by-model rollup** (slices + tokens + **$cost** grouped by
  model; missing cost/token fields stay unknown, including subscription calls).
- **`python scripts/run_delivery.py --watch --repo <dir> [--interval N]`** — a
  human terminal view (`Ctrl-C` to stop), not the one-response JSON interface.

Poll `--status --json` between steps or during an already-running build rather
than repeatedly loading raw logs. It never dispatches a provider. Run-scoped
events preserve prior build evidence rather than implying a new build erases it.

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

### Backends that need credentials (Langfuse, Honeycomb, Grafana Cloud)

CLD's telemetry setup reads only `OTEL_EXPORTER_OTLP_ENDPOINT` and adds no credentials to the
exporter. For a backend that needs keys, run a local
[OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) that holds them and point CLD
at it. For Langfuse, a minimal collector configuration:

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 127.0.0.1:4318
exporters:
  otlphttp/langfuse:
    endpoint: https://cloud.langfuse.com/api/public/otel   # or your self-hosted Langfuse
    headers:
      Authorization: "Basic ${env:LANGFUSE_AUTH}"         # base64 of "<public key>:<secret key>"
      x-langfuse-ingestion-version: "4"                     # per Langfuse's OpenTelemetry guide
service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [otlphttp/langfuse]
```

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318/v1/traces
```

Set `LANGFUSE_AUTH` in the collector's environment; the keys stay with the collector
process. Exporting directly also works: the OpenTelemetry SDK applies the standard
`OTEL_EXPORTER_OTLP_HEADERS` / `OTEL_EXPORTER_OTLP_TRACES_HEADERS` variables on its own (CLD
does not read them), so anything you put there is sent with every export.

### Self-host without credentials (Grafana Tempo / Jaeger)

Any OTLP/HTTP collector works — set the endpoint:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

## Verifying activation

The build header prints the live state:

```
telemetry: .cld/events.jsonl (local)
otel: ON -> http://127.0.0.1:4318/v1/traces
```

`otel: OFF (...)` means JSONL-only (the default). Everything is **best-effort and guarded**: a missing
SDK, an unreachable endpoint, or a failing sink never becomes an acceptance
requirement. Event writes are best-effort; durable state/usage are separate.
