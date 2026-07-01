# cld engine — architecture reference

The `cld` package is the orchestration engine. The skill drives it; this file documents
the pieces for anyone who needs to extend or debug a run.

## Executors (the CLI backends)

Each provider plugin under `cld_providers/<name>/` registers an executor that wraps a CLI
behind an injected `runner` (so every executor is unit-testable without live calls). The
default workhorse is `antigravity:Gemini 3.1 Pro (High)` (the Antigravity `agy` CLI, flat-rate).
Other backends: `opencode` and `cursor` (direct-node dispatch on Windows).
Pick a backend per slice with `--executor "<provider>:<model>"`.

Each executor returns an `ExecutorResult` (ok / diff / files_changed / token_usage / raw_log);
diffs are captured uniformly via `cld.executors._capture.capture_diff`.

## Module map

| Module | Role |
|---|---|
| `cld.executors.base` | `Executor` Protocol + `SliceTask` / `ExecutorResult` dataclasses |
| `cld_providers.<name>.provider` | per-provider executor + catalog + registration (antigravity, opencode, cursor) |
| `cld.executors` (`get_executor`) | registry: `get_executor("<provider>")` resolves via `cld.providers_api` (pluggable) |
| `cld.plan.slice` | `load_slices(md)` / `slices_to_markdown` — plan parsing |
| `cld.worktree` | `worktree(repo, branch, runner=)` context manager (isolation) |
| `cld.judge` | `judge(...)` — run tests, parse pass/fail + failing names, diff-rule check |
| `cld.orchestrator` | `deliver_slice` (single), `run_plan` (sequential, resumable), `run_plan_parallel` (DAG fan-out + worktree isolation + quota gate) |
| `cld.ledger` | `Ledger` — atomic, corruption-safe JSON progress store (resumability) |
| `cld.dag` | `parallel_batches` / `topo_layers` / `has_cycle` — DAG layering |
| `cld.integration_gate` | `integration_gate` — full-suite check after a batch merges |
| `cld.behavioral` | `evaluate_compliance` — Claude-as-judge G-Eval (behavioral regime, no OpenAI) |
| `cld.telemetry` | `emit`/`Sink`/`JsonlSink`/`OtelSink` — one structured event per lifecycle moment (local JSONL always; OTLP export opt-in) |
| `cld.status` | `render_status` — the compact `--status` digest (layer/slices/tokens/cost/by-model/gate) |

## Two verification regimes

1. **Plumbing (deterministic)** — pytest pass/fail + diff-rule. The primary gate, run by
   `cld.judge` on every slice.
2. **Behavioral (non-deterministic)** — `cld.behavioral.evaluate_compliance` scores code
   against a spec via **Claude G-Eval** (needs `ANTHROPIC_API_KEY`; skips otherwise). For
   slices whose quality isn't fully captured by `==`.

## Cost & quota model

The executor runs on a **flat-rate Gemini plan** → tokens are $0 marginal. The binding
constraint is **quota** (a rolling window), not dollars. `run_plan_parallel` accepts a
`quota_check` callable; when usage ≥ `quota_threshold` it defers slices (records them in
`PlanResult.deferred`) instead of dispatching, so a big fan-out can't exhaust the window.

## Resumability

Every processed slice is persisted to the ledger (`status`, `commit`, `attempts`) with an
atomic write. A fresh run loads the ledger and skips done slices — a mid-build stop resumes
from the right place. This is the machine-managed successor to a hand-rolled status file.
