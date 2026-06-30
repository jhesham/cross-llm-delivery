# Agent Telemetry & Real-Time Monitoring — Design

**Date:** 2026-06-25
**Status:** brainstorming → writing-plans next
**Scope:** all 3 phases designed here; build order is Phase 1 → 2 → 3 (each independently shippable).

## Goal

Give the **lead agent** (the orchestrating Claude) structured, zero-config telemetry it can read to
(1) trace a build and (2) monitor the executor in real time — and make the same data optionally
fan out to a human dashboard, without any account/server in the default path.

## The reframing that drives the design

The lead agent is **turn-based**: it acts between tool calls, never watches a stream continuously,
and can only *act* between slices (it cannot intervene mid-slice while the executor is typing). So:

- "Telemetry **to the lead agent**" = structured, cheap-to-read text/JSON it polls — NOT a web
  dashboard (the agent can't read a UI).
- "Real-time monitoring **by the lead agent**" = **dispatch the build in the background and poll a
  live event stream between turns**; per-event granularity within a layer, not mid-slice streaming.
- Human dashboards (Langfuse/Phoenix/etc.) are a *different consumer* and an *optional* add-on.

## Decisions (settled in brainstorming)

- **Primary consumer = the lead agent.**
- **Default = zero-config, local only** (no account, no Docker, no network). Dashboards opt-in.
- **Granularity = per-event, polled live.** Mid-slice executor stdout is NOT streamed to the agent.
- **Dashboards = OpenTelemetry seam** (vendor-neutral), NOT a Langfuse-specific integration.

## Architecture

A single producer → pluggable sinks. The engine emits one structured **event** per lifecycle moment;
sinks decide where events go. The default sink writes a local JSONL stream; optional sinks fan out.

```
orchestrator / run_delivery  --emit(event)-->  [ Sink(s) ]
                                                 ├─ JsonlSink   -> <repo>/.cld/events.jsonl   (default, always on)
                                                 └─ OtelSink    -> OTLP endpoint -> any backend (Phase 3, opt-in)
        run_delivery.py --status  <-- reads events.jsonl --> compact digest (the lead agent reads this)
        humans: tail -f .cld/events.jsonl  (or `--watch`)
```

### New module: `cld/telemetry.py`

- `EVENT TYPES` (string consts): `run_start`, `layer_start`, `slice_start`, `dispatch_start`,
  `dispatch_end`, `judge_verdict`, `retry`, `escalate`, `needs_repair`, `slice_done`, `layer_done`,
  `run_done`.
- `emit(event_type: str, **fields) -> None` — module-level entry; builds a record
  `{"ts": <iso>, "type": event_type, "run_id": <id>, **fields}` and forwards to the configured sink.
  **Best-effort: never raises** (a broken sink must never break a build), like `record_dispatch`.
- `class Sink(Protocol): def emit(self, record: dict) -> None`.
- `JsonlSink(path)` — append one JSON line per record; **thread-safe** (a lock, because the
  orchestrator emits from a `ThreadPoolExecutor`); flush per write so the stream is live.

#### `events.jsonl` lifecycle

- **One stream per BUILD, keyed to the ledger.** The file lives next to the ledger (default
  `<repo>/.cld/events.jsonl`). A build spans many `--step` invocations (one per DAG layer, each a
  fresh process); they all **append** to the same file so the file is the whole build's trace.
- **New build = fresh stream.** When `run_delivery` starts against a ledger with no recorded progress
  (a brand-new build), it truncates/rotates the prior `events.jsonl` first; continuing an in-progress
  ledger appends. (`run_start` is emitted on the first invocation of a build.)
- **No rotation/cap** — per build the stream is small (hundreds of short lines). It is `.cld/`
  gitignored scratch (like `detail.json`/`*.patch`); `git clean` / deleting `.cld/` clears it.
- **Future (YAGNI now):** if many builds in one repo become a disk concern, switch to a per-build
  subdir `.cld/runs/<run_id>/events.jsonl`; the schema/readers don't change.
- `MultiSink(sinks)` — fan-out; one failing sink doesn't stop the others.
- `set_sink(sink) / get_sink()` — the run wiring sets the active sink once (default `JsonlSink`).
- `run_id` — a stable id per run, generated once by `run_delivery.py` (e.g. `uuid4().hex[:8]` or a
  start timestamp) and threaded into the sink/emit wiring so every event of a run shares it.

### Event field conventions (the contract the renderer + exporters rely on)

| type | key fields |
|---|---|
| `run_start` | `run_id`, `plan`, `executor_default` |
| `layer_start` / `layer_done` | `layer`, `slice_ids`, (`gate` on done) |
| `slice_start` / `slice_done` | `slice_id`, (`status` on done) |
| `dispatch_start` | `slice_id`, `model`, `rung`, `attempt`, `source` |
| `dispatch_end` | `slice_id`, `model`, `rc`, `tokens`(dict), `cost`, `ms` |
| `judge_verdict` | `slice_id`, `passed`(bool), `reason`(str), `attempt` |
| `retry` | `slice_id`, `attempt`, `reason` |
| `escalate` | `slice_id`, `from_rung`, `to_rung` |
| `needs_repair` | `slice_id` |

Fields are additive; a missing optional field is fine. JSONL is utf-8, ASCII-safe values where the
renderer prints them (cp1252 discipline).

#### Model-switching visibility (a first-class concern)

Switching models between slices is common (per-slice `executor:` tags, complexity-based auto-routing,
a mid-build default change, or a cheap→workhorse escalation). Because **`model` is recorded on every
dispatch event** (not once per run), per-slice attribution is automatic — the stream always says which
model ran which slice. Two affordances make a switch *legible at a glance* rather than inferable:

- **`source` on `dispatch_start`** — WHY this model: `tag` (per-slice `executor:` tag), `auto`
  (router/complexity tier), `default` (the build default), or `escalated` (a higher rung after a
  cheaper one failed). So a different model on a slice is labelled with its reason.
- **A by-model rollup** in `--status` (and the `--usage` table): group slices + tokens + **cost** by
  model, so the mix — and especially the per-model COST when a paid model handled a slice — is one
  line:
  ```
  by model: antigravity:Gemini 3.1 Pro (High) [T1,T2,T3,T5 · $0.00] · opencode:claude-opus-4-8 [T4 (tag) · $0.41]
  ```
  This is the high-value view when models switch: flat-rate slices cost nothing, a pinned premium
  slice shows its real spend, attributed to the slice + the reason it switched.

## Phase 1 — local event stream + `--status` (the whole story for the lead agent)

1. **`cld/telemetry.py`** with `emit`/`Sink`/`JsonlSink`/`MultiSink` as above.
2. **Wire emit points** into `cld/orchestrator.py` (`run_plan_parallel`, `_run_one`, `deliver_slice`)
   and `run_delivery.py` (`run_start`/`run_done`, `layer_start`/`layer_done`). `record_dispatch`
   becomes one `emit("dispatch_end", ...)` caller; the existing Langfuse path is preserved (it stays
   a no-op unless configured) and is folded behind a sink in Phase 3 so there's no double-tracing.
3. **`run_delivery.py --status [--ledger …] [--repo …]`** — reads `.cld/events.jsonl` (+ the ledger
   for cross-`--step` completed state), reconstructs current state, prints a compact digest, e.g.:
   ```
   run a1b2 · layer 3/6 · 9 slices: 5 done(✓ 5/✗ 0) · T13 running antigravity@workhorse a1 47s ·
   T15 retry a2 (COLLECTION ERROR ...) · 2 pending · tokens 412k · cost $0.41 · gate: pending
   by model: antigravity:Gemini 3.1 Pro (High) [T11,T12,T13,T16,T17 · $0.00] · opencode:claude-opus-4-8 [T4 (tag) · $0.41]
   ```
   The `by model` line surfaces model-switching (which model ran which slice, the reason, per-model
   cost). Context-cheap (the agent reads THIS, not the raw log). ASCII-safe.
4. **Loud status line at build start** (already shipped: `tracing: ON/OFF`); extend to also note the
   local stream: `telemetry: .cld/events.jsonl (local) · tracing: OFF (...)`.

Delivers BOTH asks for the lead agent with zero config: it can read live state (`--status`) during a
build and the full trace (events.jsonl) after. Phases 2–3 add reach, not core capability.

## Phase 2 — real-time monitoring via background dispatch + poll

The mechanism by which a turn-based agent achieves "real-time": run the build off-turn, poll on-turn.

- **Convention (SKILL.md guidance):** the lead agent dispatches a long layer / full run in the
  **background** (the harness's background bash), then polls `run_delivery.py --status` between turns,
  pacing with `ScheduleWakeup`. Within a multi-minute layer it sees slices land one-by-one instead of
  a black box, and reacts at the next decision point (escalate / repair / stop). The synchronous
  `--step` stays the simple default for those who don't want background runs.
- **Live-flush guarantee:** Phase 1 already flushes per event, so `--status` is fresh mid-run.
- **Optional human `--watch`:** `run_delivery.py --watch [--interval N]` loops `--status` every N
  seconds (a tiny terminal view); humans can equally `tail -f .cld/events.jsonl`.
- No new engine surface beyond `--watch` + docs; the heavy lifting is the event stream from Phase 1.

## Phase 3 — OpenTelemetry export seam (opt-in; the human dashboard, vendor-neutral)

- **`OtelSink`** in `cld/telemetry.py`: lazily imports `opentelemetry` (guarded — absent SDK ⇒ no-op,
  exactly like the `langfuse` guard); maps events to **nested OTel spans** (`run` → `layer` → `slice`
  → `dispatch`) using **GenAI semantic attributes** (`gen_ai.request.model`,
  `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, plus `cld.judge.passed`, `cld.rung`).
- **Activation (generic):** standard `OTEL_EXPORTER_OTLP_ENDPOINT` (+ optional
  `OTEL_EXPORTER_OTLP_HEADERS`) turns it on; when set, the run wiring installs
  `MultiSink([JsonlSink(...), OtelSink(...)])`. Unset ⇒ JSONL only. The local default never changes.
- **Langfuse — a first-class, easy plug-in (NOT retired).** Langfuse is itself OTel-based (exposes an
  OTLP ingest endpoint), so it's reached through the *same* seam — no bespoke Langfuse SDK path:
  - *Generic way:* set `OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/public/otel` + an
    `Authorization: Basic <base64(pk:sk)>` header — same as any backend.
  - *Convenience (keeps the familiar UX):* if `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are set
    (and no explicit OTLP endpoint), `run_delivery` **auto-wires** the OtelSink to
    `{LANGFUSE_HOST or cloud}/api/public/otel` with the Basic-auth header derived from the keys. So
    existing Langfuse users keep "set two env vars and it works," now on the single OTel path.
  - This **drops the bespoke langfuse Python SDK dependency** (OTLP is plain HTTP), which also removes
    the silent-inert fragility — and `get_tracer`/`record_dispatch`'s old Langfuse-SDK path is
    replaced by `OtelSink` so there is exactly one tracing path. (`record_dispatch` keeps emitting the
    `dispatch_end` event; the span just comes from the sink.)
- **Docs:** `references/observability.md` (supersedes/extends `langfuse-setup.md`) — "bring your own
  backend": **Arize Phoenix** (`pip install arize-phoenix; phoenix serve` → local, no account) as the
  easy local option, **Langfuse** (the two-keys convenience above), plus Grafana Tempo / Jaeger
  (self-host) and Honeycomb / Grafana Cloud (hosted) as targets.

## Data flow (end to end)

1. `run_delivery.py` sets `run_id`, installs the sink(s) (JSONL always; +OTel if endpoint set),
   prints the telemetry/tracing status line, emits `run_start`.
2. `run_plan_parallel` emits `layer_start`; each worker thread emits `slice_start` →
   `dispatch_start` → (executor) → `dispatch_end` → `judge_verdict` → (`retry`/`escalate`/
   `needs_repair`)* → `slice_done`. All via `emit()` → the locked JSONL append (+ OTel span).
3. `layer_done` (with the gate) and `run_done` close it out.
4. Concurrently/after: `--status` reconstructs state from the JSONL (+ ledger); a human tails the file
   or watches a dashboard.

## Error handling

- `emit()` and every sink are **best-effort, never raise** — telemetry must never break a build.
- `JsonlSink` serializes writes with a lock (orchestrator is multi-threaded); a write failure is
  swallowed.
- `--status` degrades gracefully on a missing/partial/short events file (prints "no events yet").
- `OtelSink` no-ops when the SDK is absent or the endpoint is unreachable (export is async/batched).

## Testing

- **`telemetry.py` (unit):** `JsonlSink` writes valid JSONL; **thread-safe** under N concurrent
  `emit()` threads (all lines present + parseable, no interleave corruption); `MultiSink` fans out and
  isolates a failing sink; `emit()` swallows a raising sink.
- **emit points (integration):** `run_plan_parallel` with the `FileCreatingExecutor` writes an
  `events.jsonl` containing the expected ordered sequence for a slice (start→dispatch→verdict→done),
  incl. the escalate/needs_repair events on the failure path.
- **`--status` (unit):** render against a synthetic `events.jsonl` → asserts in-flight slice shown
  with elapsed, done counts, gate, token/cost totals; ASCII/cp1252-safe.
- **model-switching (unit):** a synthetic `events.jsonl` with two slices on different models (one
  `source=tag`, one `source=auto`) → `--status` shows each slice's model and the `by model` rollup
  groups slices + cost per model (incl. a non-zero cost for the paid model).
- **Phase 2:** `--status` mid-run shows in-flight (small integration); `--watch` smoke (1 iteration).
- **Phase 3:** `OtelSink` against `opentelemetry.sdk` `InMemorySpanExporter` → spans nested correctly
  with GenAI attributes; guarded no-op when the SDK is blocked (subprocess test, like the langfuse
  deps-blocked test).

## Dogfood-readiness (for building this via cross-llm itself)

The plan will be vertical slices with committed acceptance tests + a DAG — i.e. directly dogfood-able.
Suitability per area:
- **DOGFOOD-friendly (pure, isolated, real-default + real-shape easy to pin):** `telemetry.py`
  (emit/sinks/JsonlSink/MultiSink), the `--status` renderer (file in → text out), `OtelSink` (events
  in → spans in an in-memory exporter). These have crisp contracts and no live-orchestrator coupling.
- **CLAUDE (keep off the executor):** the orchestrator/`run_delivery` **emit-point wiring** — it edits
  the live engine the executor itself runs on (bootstrapping risk), and `--watch`/SKILL.md guidance.

## Non-goals / YAGNI

- No mid-slice executor stdout streaming to the agent (no actionable value; optional human concern).
- No bundled dashboard/UI, no hosted service, no metrics/logs OTel signals (traces only).
- No change to the synchronous `--step` default behavior; background-poll is additive.
- No mandatory dependency added to the default path (OTel SDK stays optional/guarded).

## Done criteria (per phase)

- **P1:** `cld/telemetry.py` + emit points + `.cld/events.jsonl` live stream + `run_delivery.py
  --status` digest + the telemetry status line; full suite green; vendored into bundles.
- **P2:** `--watch` + SKILL.md background-dispatch+poll convention; `--status` proven fresh mid-run.
- **P3:** `OtelSink` + `OTEL_EXPORTER_OTLP_ENDPOINT` activation + `references/observability.md`
  (Phoenix/Grafana/Honeycomb/Langfuse); single tracing path; SDK-absent no-op test.
