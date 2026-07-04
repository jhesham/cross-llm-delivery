# Changelog

## 0.1.0 — 2026-07-03 (initial public release)

- **Provider-blind engine** (`engine/cld/`): orchestrator with DAG layering + parallel dispatch,
  per-slice git-worktree isolation, resumable JSON ledger, integration gate.
- **Deterministic judge**: committed failing acceptance tests are the dispatch contract; pass/fail
  is the real pytest exit code; an allowed-files diff rule rejects out-of-scope edits; failures
  retry with structured judge feedback.
- **Three executor providers** behind a drop-in registry: **antigravity** (`agy`), **opencode**,
  **cursor** (incl. `cursor:composer-2.5`), each with a model catalog, headless-dispatch quirks
  handled (shim bypass, stdin detachment, console-encoding safety), and validate-before-trust
  probing for untested models.
- **Complexity routing + escalation ladder**: untagged slices route to the cheapest viable model
  and climb on failure; explicit `--executor` models are honored verbatim; per-slice `executor:`
  tags pin a slice.
- **Telemetry**: every lifecycle moment emits to `.cld/events.jsonl`; `--status` digest (layer
  position, in-flight slices + elapsed, tokens, cost-by-model, gate); `--watch` live view;
  opt-in OpenTelemetry export (GenAI semantic spans) to any OTLP backend, with a two-env-var
  Langfuse convenience.
- **Generator**: produces self-contained per-provider Claude Code skills (vendored engine, no
  pip install) into `dist/`, with an optional mirror-publishing helper.
- **Safety rails**: caller-merge preflight (warns when a pending layer depends on accepted but
  unmerged slices), executor-CLI preflight (friendly message instead of a traceback when no CLI
  is installed), non-destructive diff preservation for rejected slices.
