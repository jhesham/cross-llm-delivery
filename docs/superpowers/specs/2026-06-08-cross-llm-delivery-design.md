# Cross-LLM Delivery — Design

**Date:** 2026-06-08
**Status:** Design approved, pending writing-plans
**Author:** Claude (Opus 4.8) + jhesham@hotmail.com

## Problem & Goal

Large builds (LangGraph-type agentic systems; backend-heavy automation/research/analysis
tooling) burn a large number of expensive Opus tokens on bulk implementation. The goal is
to **route implementation to a cheaper executor LLM agent and use Claude (Opus) as the
architect + judge**, preserving engineering quality while cutting token cost on large builds.

Small fixes stay with Claude directly — orchestration overhead only pays off when the
implementation work is large relative to the per-handoff cost (spec + judge + isolation).
This system is **for large builds only**.

## Core Division of Labor

| Work | Who | Token profile |
|---|---|---|
| Architecture, slice decomposition, interface contracts, acceptance tests | Claude (Opus) | low tokens, high leverage |
| Bulk implementation of each slice | Executor (Gemini 3.1 Pro v1; Composer later) | high tokens, cheap rate |
| Judging each slice against its tests | Claude (Opus) | low tokens |
| Behavioral/semantic judgment + UI/visual sign-off | Claude + Human-in-the-loop | low tokens |

The expensive model does the *thinking* (cheap in tokens); the cheap model does the
*typing* (expensive in tokens).

## Pipeline

```
superpowers:brainstorming  ──►  spec (this doc)
        │
superpowers:writing-plans  ──►  phased plan:
        │                        • vertical slices
        │                        • interface contracts
        │                        • per-slice acceptance tests
        │                        • dependency DAG (parallel vs sequential)
        ▼
[NEW SKILL: cross-llm-delivery]  ──►  executes the plan:
        per slice:  isolate (worktree) → dispatch to executor → run pytest/deepeval
                    → Claude judges against acceptance tests → integrate
        independent slices (per DAG) → dispatched in PARALLEL to multiple executor instances
```

The new orchestrator skill is conceptually `subagent-driven-development` with the executor
swapped from an internal Claude subagent to an **external cheap-model CLI**, and Claude
elevated to **judge**. The parallel fan-out reuses the `dispatching-parallel-agents` pattern.

## Engineering Principles (what keeps this true to good practice)

- **Vertical slices, not horizontal layers.** Each slice is thin but end-to-end and
  therefore *independently testable*. Horizontal layers can't be validated until other
  layers exist, which breaks the judge loop.
- **Stable interface contracts between slices.** Claude fixes the seams up front so a bad
  slice's rework stays *local* and cannot cascade. (For LangGraph, the state object
  `state in → state out` is the natural contract.)
- **Per-slice acceptance criteria written before handoff** — ideally a failing test the
  executor must make pass (TDD-flavored). Makes judging objective and rework cheap.
- **Walking skeleton first.** First slice = thinnest end-to-end thing that compiles and
  passes a trivial test, plus tracing/logging so behavioral judgment has a signal from
  day one.
- **Right-sized chunks.** Each slice big enough that executor implementation tokens dwarf
  Claude's (spec + judge) tokens, small enough to stay independently testable.
- **Batch-size economics.** Big-batch rework is super-linear (defects compound into
  dependents); small slices cap the blast radius. Risk-adjusted, chunking wins.

## Verification Stack (three layers, three tools)

| Layer | Tool | Job |
|---|---|---|
| Deterministic plumbing tests (the bulk) | **pytest** | structural: state transitions, wiring, routing, tools, persistence — mocked LLM/tool boundary |
| Behavioral evals | **deepeval** (pytest-native) | agent reasoning/routing quality via golden scenarios + LLM-as-judge; runs under the same `pytest` command |
| Tracing / observability | **Langfuse Cloud** (self-host was the original intent; Docker absent → Cloud, T1.2. Wired via `record_dispatch`, T5.5) | the behavioral verification *signal* — Claude judges agent behavior by reading traces |

Build only the domain-specific scenarios and glue; harnesses are off-the-shelf.

**Two verification regimes for agentic systems:**
1. *Plumbing* (most of the code) — deterministic, judged by Claude against pytest.
2. *Intelligence* (behavior) — non-deterministic, judged by Claude + human via deepeval
   evals and Langfuse traces.
3. *UI/visual* (when present) — exits the automated loop; human-in-the-loop gates it.

**Design rule enforced in every slice spec:** all model and tool calls go through an
**injectable/mockable boundary** (DI of model client + tool registry; never hardcoded in a
node). This keeps deterministic tests deterministic and enables later Composer/Gemini A/B.

## Executor

- **v1: Gemini CLI (Gemini 3.1 Pro).** Chosen over cursor-agent because Gemini CLI runs
  **natively on Windows** (Node-based `npm i -g @google/gemini-cli`, headless via
  `gemini -p`, `--yolo` auto-approve, JSON output) — sidestepping the WSL requirement that
  blocks cursor-agent on this Windows Server machine.
- **Pluggable executor adapter:** single contract `(task + worktree) → diff`. Composer
  (cursor-agent) and others become drop-in additions, not redesigns.
- **v2 candidate (decided 2026-06-09): OpenCodeExecutor.** OpenCode CLI (`opencode run
  "..." --model provider/model --format json --dangerously-skip-permissions --dir <wt>`)
  is a clean headless executor with a major advantage: **one CLI fronts 40+ models**
  (OpenCode Zen gateway — Gemini, GPT, Claude, DeepSeek, Qwen, etc.), giving true per-slice
  model selection through a single adapter. Slots into the existing registry (the `composer`
  stub slot). **Cost caveat — load-bearing:** OpenCode **Zen is metered pay-as-you-go**
  ($/1M tokens), which would **re-introduce the per-token cost the flat-rate Gemini plan
  dissolved** (recall: every dispatch is ~98% input overhead — irrelevant under flat billing,
  real money under metered). **Decision: Gemini flat-rate stays the DEFAULT executor ($0
  marginal preserved); OpenCodeExecutor is an opt-in second adapter** — attractive for (a)
  driving a different *flat-rate/free* model, or (b) Zen's dirt-cheap tier (e.g. DeepSeek V4
  Flash ~$0.14/$0.28 per 1M, where 98% overhead is still trivially cheap). Do NOT make a
  metered provider the default path. See `docs/notes/opencode-executor-option.md`.
- **Open validation:** the "≈Opus quality at ~10× fewer tokens" claim was Composer's; we
  must re-validate *cost and quality* for Gemini 3.1 Pro on a real slice (smoke test)
  before trusting it.

## Baked-in Requirements

1. **Integration gate.** After each parallel batch of slices merges, run a *full-suite*
   judge pass against the merged result. Slice-green ≠ system-green (contracts can drift,
   merges can conflict).
2. **Resumability.** A **progress ledger** (slices done / pending / failed, with the DAG
   state) persisted to the repo, so a fresh session resumes mid-build after a token reset
   instead of re-deriving everything.

## Open Items for writing-plans to Nail Down

- Exact executor-adapter contract format (how task spec + worktree are passed; how the
  diff is collected).
- Progress-ledger schema and location.
- Per-slice spec/acceptance-test format consumed by the orchestrator.
- Smoke-test definition (the head-to-head that validates Gemini quality/cost).
- Prerequisite setup: install + auth Gemini CLI on Windows; confirm headless + model id.

## Prerequisites / Environment

- Machine: Windows Server 2025, native (PowerShell/win32).
- Project root: `D:\claude_server\cross-llm-delivery`.
- Persistence: this design doc (canonical, git-committed) + claude-mem auto-capture +
  Claude memory pointer.
