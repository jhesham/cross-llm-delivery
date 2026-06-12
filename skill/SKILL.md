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

### 2. Run the plan — batch-step (context-lean, interactive)

Drive the build ONE DAG layer at a time so your context stays small and you can steer
between phases. Per layer:

```bash
python skill/scripts/run_delivery.py <plan.md> --repo <dir> --step [--workers N] [--executor <name>[:model]]
```

This runs only the next pending layer (independent slices fan out concurrently in isolated
worktrees), then EXITS, printing a ~10-line summary. Read the summary, relay it to the user,
and act on the gate (the exit code):
- **exit 0** (all passed): "Layer done, all green — continue?" → re-invoke `--step` for the next.
- **exit 2** (some failed/deferred): surface the failed slice + its failing test; offer
  inspect / retry / edit-the-slice / skip / abort.
- **exit 3** (complete): no layers left — review the final ledger, optionally run the integration gate.

Re-invoking `--step` advances automatically (the ledger is the state). A partially-done layer
re-runs only its non-`done` slices, so "fix T3 then continue" works by editing + re-`--step`.

Per slice inside a layer: isolate (git worktree `slice-<id>`) → Gemini implements → the
deterministic judge runs the REAL acceptance tests + diff-rule (failures feed back into a
retry) → accepted work is committed to its `slice-<id>` branch → ledger updated + Langfuse span.

**Why batch-step:** running the whole loop in one unbroken context burns large amounts of the
lead agent's tokens (every turn re-reads a growing context). Stepping one layer at a time keeps
your context to ~10 lines per layer and flat during interaction.

#### Choosing the executor & model (interactive picker)

When helping a user start a build (or when they ask "which model?"), present the recommended
shortlist and let them pick — the USER decides, never the orchestrator. The default is the proven
$0 flat-rate workhorse (`gemini:gemini-3.1-pro-preview`); "just go" needs no decision.

Build the shortlist from real data: run `opencode models` (via the project's runner) →
`cld.models.list_models` → `cld.models.recommend(available_ids=...)`. Present buckets
(workhorse / heavy / quick), each line:
`<executor:provider/model> · <cost_class> · <headless_status> · <why>`.

Rules:
- **Default pre-selected:** the proven workhorse. Pressing enter uses it.
- **Cost guardrail:** if the user picks a `premium-metered` model (`confirm_cost=True`), CONFIRM
  explicitly first — "This model bills real $ per dispatch (not flat-rate) — proceed?" Do not
  dispatch a premium model without that confirmation. (`free`/`flat` models need no confirmation.)
- **Headless warning:** an `untested` model carries a warning ("may not complete builds reliably").
  Offer to run `cld.validate.validate_model` on it (one trivial slice, real test as judge) before
  trusting it — it promotes the model to `proven` or `known-bad` from evidence.
- The choice maps to `--executor <name>:<provider/model>` — e.g. `--executor gemini` (default),
  `--executor gemini:<model-id>`, or `--executor opencode:opencode/deepseek-v4-flash-free`. A
  per-slice `executor:` field in the plan supports "use the heavy model on this one hard slice."

Example shown to the user:
```
Recommended executors (installed + available):
  WORKHORSE (default)
  ▸ gemini:gemini-3.1-pro-preview         · $0 flat · proven   · 14/14 grade-A workhorse
  HEAVY (hard slices, worth more $)
    opencode:opencode/claude-opus-4-8     · premium ⚠ · likely  · top capability; confirms cost
  QUICK / BUDGET
    opencode:opencode/deepseek-v4-flash-free · free ⚠ · untested · cheap; validate before trusting
Pick one [default: gemini workhorse]:
```

Use `--dry-run` first to print the layers without dispatching.

**Inspecting on request:** raw diffs/logs/JSON are NOT on stdout — per-slice detail is written
to `<dir>/.cld/<slice-id>/detail.json`. Only when the user asks "show me T3", read that one
file. Do not pull raw output into context otherwise.

**Keep orchestration cache-cheap (your context is a cached prefix):**
1. Summaries are append-only — never edit or re-print a prior layer's summary; just add the new one.
2. Don't restate volatile data (timestamps, full token totals) at the top of your turns — it churns the cached prefix.
3. Inspect a `.cld/` artifact at most once, and let it sit at the end of context — re-reading it re-injects and churns the cache.

### 3. Integrate and verify

After a batch merges, run the **integration gate** (full suite on the merged tree —
slice-green ≠ system-green). Re-run `run_delivery.py` to resume: already-done slices
are skipped via the ledger.

## Reference material

- `references/architecture.md` — the cld engine: modules, the locked Gemini CLI form,
  executor registry, ledger, DAG, quota-awareness, observability.
- `references/authoring-plans.md` — how to write good vertical slices + contracts.
