# Behavioral evals (deepeval) — two verification regimes

**Date:** 2026-06-08 (T1.3)

The verification stack has two regimes (design doc → Verification Stack):

| Regime | Command | What it checks | Live LLM? |
|---|---|---|---|
| **Plumbing** (the bulk) | `python -m pytest` | structural: wiring, routing, state, persistence | no — fast, offline, deterministic |
| **Intelligence** (behavior) | `python -m pytest -m eval` | agent reasoning/routing quality via deepeval LLM-as-judge | yes — needs an eval model + key |

## Why behavioral evals are gated

`deepeval`'s `AnswerRelevancyMetric` (and most metrics) are **LLM-as-judge** — they call a
live model (OpenAI by default). Confirmed at T1.3: with no `OPENAI_API_KEY`, the metric
raises `DeepEvalError: OpenAI API key is not configured`.

To keep the default `pytest` run fast, offline, and deterministic (the judge loop runs it
constantly), behavioral evals are marked `@pytest.mark.eval` and **deselected by default**
via `addopts = "-q -m 'not eval'"` in `pyproject.toml`. The `eval` marker is registered
there too (no unknown-mark warnings).

## Running the real evals

1. Set a key: `$env:OPENAI_API_KEY = "sk-..."` (PowerShell).
2. Run: `python -m pytest -m eval`

Without a key, the gated test **skips cleanly** (an in-test guard calls `pytest.skip`) rather
than erroring — so `-m eval` is safe to run in any environment; it just won't exercise the
judge unless a key is present.

## Configuring a non-OpenAI judge (future)

deepeval supports other judge models (Azure, local, custom `DeepEvalBaseLLM`). If we want to
avoid an OpenAI dependency for evals, wire a custom model here. Out of scope for T1.3; noted
for the sharing README (T6.2), since a public release shouldn't hard-require OpenAI.
