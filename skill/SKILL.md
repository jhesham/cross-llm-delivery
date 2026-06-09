---
name: cross-llm-delivery
description: >-
  Route the bulk IMPLEMENTATION of a large software build to a cheap headless
  executor LLM (Gemini 3.1 Pro via the Gemini CLI) while Claude acts as architect
  and judge — cutting expensive-model token cost on large builds while preserving
  quality. Use this skill whenever you have a multi-slice implementation plan
  (contracts + acceptance tests + a dependency DAG) and want to dispatch the coding
  to Gemini in isolated git worktrees, judge each slice against its tests, run
  independent slices in parallel, and resume a partially-finished build. Trigger it
  for phrases like "build this plan with Gemini", "dispatch these slices", "run the
  cross-llm delivery", "have the cheap model implement this", or any time a sizeable
  build has been decomposed into testable slices and you want Claude to orchestrate
  + judge rather than type all the code itself. NOT for small one-file fixes — the
  per-dispatch overhead only pays off on large builds.
---

# Cross-LLM Delivery

## What this does and why

Large builds burn expensive-model (Claude/Opus) tokens on bulk typing. This skill
splits the work by comparative advantage: **Claude does the thinking** (decompose the
build into vertical slices, fix the interface contracts, write the acceptance tests,
judge each result) and **a cheap headless executor does the typing** (Gemini 3.1 Pro
implements each slice to make its tests pass). On a flat-rate Gemini plan the executor
tokens are effectively free, so the only Claude cost is the high-leverage spec + judge
work.

The engine (`cld`) is already built and tested. This skill is the thin layer that
**assembles it and runs a plan end-to-end.** You generally do NOT need to write code —
you prepare a plan and invoke the driver script.

## When to use it (and when not to)

- **Use it** when a build is large enough that executor implementation tokens dwarf
  Claude's spec+judge tokens, AND it has been decomposed into independently-testable
  vertical slices with a dependency DAG.
- **Don't use it** for small fixes or single-file changes — the per-dispatch overhead
  (workspace scan + spec) makes orchestration a net loss. Small work stays with Claude
  directly.

## Prerequisites

- The Gemini CLI installed and authenticated (`gemini -p "..."` returns output).
  See `references/architecture.md` for the locked invocation form.
- The `cld` package importable (`pip install -e .` from the repo root).
- A git repo (worktree isolation runs `git worktree add/remove`).
- Optional: `ANTHROPIC_API_KEY` to enable behavioral (G-Eval) judging; `LANGFUSE_*`
  keys to enable trace emission. Both degrade to no-ops when absent.

## The workflow

### 1. Decompose the build into a plan (Claude's job — the thinking)

Author a plan markdown with one block per slice. Each slice is **thin but end-to-end
and independently testable**, with a stable interface contract and a failing acceptance
test the executor must make pass. Express dependencies so independent slices can run in
parallel.

```
## SLICE: T1
brief: Implement <X> so that tests/test_x.py passes. <contract details, constraints,
  injectable boundaries, allowed files.>
files: src/x.py, tests/test_x.py
acceptance_test_path: tests/test_x.py
deps:

## SLICE: T2
brief: Implement <Y> ...
files: src/y.py
acceptance_test_path: tests/test_y.py
deps: T1
```

**Author the acceptance tests first** (committed, failing) — they are the objective
contract the executor is judged against. See `references/authoring-plans.md` for how
to write good slices (vertical not horizontal, injectable boundaries, right-sizing).

### 2. Run the plan (the engine's job — the typing + judging)

```bash
python skill/scripts/run_delivery.py <plan.md> --repo <repo_dir> --workers 4
```

**Choose the executor/LLM at invocation** (the user decides, not the orchestrator):
`--executor gemini` (default) or `--executor gemini:<model-id>` to pin a specific model.
On Windows, prefer `--workers 1` until the parallel-worktree isolation fix lands (a
known issue — concurrent dispatch can collide; serial is safe).

What happens per slice:
1. **Isolate** — a git worktree (`slice-<id>`) so parallel agents never collide.
2. **Dispatch** — Gemini implements the slice in its worktree.
3. **Judge** — Claude's deterministic judge runs the acceptance tests + checks the
   diff rule (no edits outside the allowed files). On failure it feeds the failing
   tests back into a retry.
4. **Record** — the outcome is persisted to a JSON ledger (resumable) and emitted as
   a Langfuse span (observable).

Independent slices in a DAG layer run concurrently; dependent layers run in order.

Use `--dry-run` first to print the execution layers without dispatching.

### 3. Integrate and verify

After a batch merges, run the **integration gate** (full suite on the merged tree —
slice-green ≠ system-green). Re-run `run_delivery.py` to resume: already-done slices
are skipped via the ledger.

## Reference material

- `references/architecture.md` — the cld engine: modules, the locked Gemini CLI form,
  executor registry, ledger, DAG, quota-awareness, observability.
- `references/authoring-plans.md` — how to write good vertical slices + contracts.
