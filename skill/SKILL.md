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

#### Choosing the executor & model (the picker)

**ALWAYS present the model shortlist before the first dispatch of a build — every time, no
exceptions.** Do not skip it because "the default needs no decision": the user picks, not you.
The ONLY time you may skip is when the user has already named an executor this session (e.g. "use
gemini" / "use opencode deepseek") — then echo that choice and proceed. A default existing is not
permission to choose on the user's behalf.

There are two equivalent surfaces; use whichever fits:

1. **CLI picker (preferred when you're about to run the script).** Run `run_delivery.py` WITHOUT
   `--executor`; if stdin is a TTY it prints the shortlist and prompts. (Non-interactive runs and
   `--step` loops fall back to gemini, so they never block.) This is `cld.models.pick_executor`.
2. **Agent-presented (in chat).** Build it yourself and ask: `cld.models.list_models(runner=...)`
   → `cld.models.recommend(available_ids=...)` → show the buckets, take the user's pick, pass it
   as `--executor`.

   **GUARD — render the options verbatim from `render_shortlist`; never improvise them.** Call
   `cld.models.render_shortlist(recs)` (or run the live pipeline) and present EXACTLY those lines /
   model ids. Do NOT hand-type, reorder, abbreviate, or recall the option list from memory — the
   chat surface must match the program surface line-for-line. (A hand-typed dialog once dropped a
   real catalog entry and reordered the list; rendering from `render_shortlist` is the only
   sanctioned source.) If you present via a UI dialog, copy each option's id/label straight from
   `render_shortlist` output — same ids, same order, same count.

   **Browsing the full model list.** The shortlist dialog must include a "Browse all models…"
   option. If chosen: present provider groups (claude / gpt / gemini / deepseek / other), then
   the chosen group's models — every option rendered VERBATIM from
   `cld.models.browse_models(available_ids)` → `cld.models.render_browse_list(grouped)` (the
   same no-improvising guard applies; same ids, order, count). UI dialogs cap at 4 options —
   page with a "More…" entry when a group exceeds it. Free-text "Other" stays as the final
   escape hatch; a free-typed id is treated as untested.

   **Validate-on-demand (the headless guarantee).** Before dispatching a build on ANY pick
   whose `headless_status` is not proven/likely — browsed, free-typed, or uncatalogued — run
   `cld.validate.resolve_and_validate(spec, ...)`. It:
   - announces "Validating headless capability for <spec> — this runs one trivial slice
     (~30s), please wait…" before the dispatch, and a verdict line after;
   - on a metered model (cheap-metered / premium-metered / metered-unknown) asks "validating
     bills real $ — proceed?" BEFORE spending; declining means pick again;
   - on `proven`: proceed with the build;
   - on `known-bad` (built failing/no code): decline, mark it known-bad for THIS SESSION ONLY
     (pass the same `session_known_bad` set to `recommend`/`browse_models` so it's hidden),
     and RE-PRESENT the picker so the user picks another model;
   - on an executor error: report "couldn't validate" — not a model verdict; let the user
     retry or pick another.
   Never dispatch a real build on an untested model without this gate.

`recommend()` ALWAYS includes the proven Gemini workhorse as the default even though it is not in
`opencode models` output (it runs via the Gemini CLI) — you do NOT need to merge it in yourself.
Just pass the OpenCode ids from `list_models`.

Rules (enforced by `pick_executor`, and required of the agent surface too):
- **Default = the proven $0 flat-rate workhorse** (`gemini:gemini-3.1-pro-preview`). Enter selects it.
- **Cost guardrail:** a `premium-metered` model (`confirm_cost=True`) requires an explicit "this
  bills real $ per dispatch — proceed?" confirmation; declining falls back to the default. Never
  dispatch a billed model without that confirmation. (`free`/`flat` need none.)
- **Headless warning:** an `untested` model carries a warning. Offer `cld.validate.validate_model`
  (one trivial slice, real test as judge) to promote it to `proven`/`known-bad` before trusting it.
- The choice maps to `--executor <name>:<provider/model>` — `gemini`, `gemini:<model-id>`, or
  `opencode:opencode/<model>`. A per-slice `executor:` field supports "heavy model on this one slice."

Live example (ASCII, Windows-console-safe):
```
Recommended executors (installed + available):
  WORKHORSE (default)
  > 1) gemini:gemini-3.1-pro-preview              flat               proven
    2) opencode:opencode/deepseek-v4-pro          cheap-metered      likely
  HEAVY (hard slices, worth more $)
    3) opencode:opencode/claude-opus-4-8          premium-metered $  likely
  QUICK / BUDGET
    4) opencode:opencode/deepseek-v4-flash-free   free               untested  (!) validate first
Pick one [default: workhorse]:
```
(`$` = bills real money, confirms on pick. `(!)` = untested, offer validation.)

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
