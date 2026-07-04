<!-- GENERATED from cross-llm-delivery (provider: opencode, v0.1.0) - do not edit here; edit the monorepo source. -->
---
name: cross-llm-opencode
description: >-
  Route the bulk IMPLEMENTATION of a large software build to a cheap headless
  executor LLM (opencode:opencode/deepseek-v4-pro) while Claude acts as architect and
  judge -- cutting expensive-model token cost on large builds while preserving
  quality. Use this skill whenever you have a multi-slice implementation plan
  (contracts + acceptance tests + a dependency DAG) and want to dispatch the
  coding to the executor in isolated git worktrees, judge each slice against
  its tests, run independent slices in parallel, and resume a
  partially-finished build. Trigger it for phrases like "build this plan",
  "dispatch these slices", "run the cross-llm delivery", "have the cheap model
  implement this", or any time a sizeable build has been decomposed into
  testable slices and you want Claude to orchestrate + judge rather than type
  all the code itself. NOT for small one-file fixes -- the per-dispatch
  overhead only pays off on large builds.
---

# Cross-LLM Delivery

## What this does and why

Large builds burn expensive-model (Claude/Opus) tokens on bulk typing. This skill
splits the work by comparative advantage: **Claude does the thinking** (decompose the
build into vertical slices, fix the interface contracts, write the acceptance tests,
judge each result) and **a cheap headless executor does the typing** (implements each
slice to make its tests pass). On a flat-rate or cheap-metered plan the executor
tokens are effectively free or very cheap, so the only Claude cost is the high-leverage
spec + judge work.

The engine (`cld`) is already built and tested. This skill is the thin layer that
**assembles it and runs a plan end-to-end.** You generally do NOT need to write code --
you prepare a plan and invoke the driver script.

## When to use it (and when not to)

- **Use it** when a build is large enough that executor implementation tokens dwarf
  Claude's spec+judge tokens, AND it has been decomposed into independently-testable
  vertical slices with a dependency DAG.
- **Don't use it** for small fixes or single-file changes -- the per-dispatch overhead
  (workspace scan + spec) makes orchestration a net loss. Small work stays with Claude
  directly.

## Prerequisites

## OpenCode CLI setup

1. Install Node.js (v18+ recommended).
2. Install the OpenCode CLI: `npm install -g opencode-ai`
3. Authenticate with your chosen model provider via the OpenCode TUI or:
   `opencode auth add <provider>`
   (Supported: Anthropic, Google, DeepSeek, Moonshot/Kimi, and others.)
4. Verify headless operation:
   `opencode run "print hello" -m opencode/deepseek-v4-flash-free --format json --dir . --dangerously-skip-permissions --port`
   (Should emit JSONL with a `step_finish` event; exit code 0.)

### Windows note

The npm shim is `opencode.cmd`. For long prompts, `cmd.exe /c` (invoked by the shim) mangles
the argv, causing the CLI to fall back to interactive mode silently. The executor automatically
resolves the real `opencode.exe` at `<npm-prefix>/node_modules/opencode-ai/bin/opencode.exe`.
Override with `OPENCODE_CLI_CMD=<path>` if auto-detection fails.

### Cost

OpenCode dispatches are metered at the underlying model provider's token rates.
`opencode/deepseek-v4-flash-free` is free; other models bill real money.
Monitor usage with `opencode stats`.


- The `cld` package importable (`pip install -e .` from the repo root).
- A git repo (worktree isolation runs `git worktree add/remove`).
- Optional: `ANTHROPIC_API_KEY` to enable behavioral (G-Eval) judging (no-op when absent).
- Telemetry is **always on and local** — every build writes `<repo>/.cld/events.jsonl` and you
  read it with `--status` (see below). Exporting to a dashboard (Arize Phoenix / Langfuse / any
  OTLP backend) is opt-in via env vars; see `references/observability.md`. The build header prints
  `telemetry:` and `otel:` status lines.

## The workflow

### 1. Decompose the build into a plan (Claude's job -- the thinking)

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

**Author the acceptance tests first** (committed, failing) -- they are the objective
contract the executor is judged against. See `references/authoring-plans.md` for how
to write good slices (vertical not horizontal, injectable boundaries, right-sizing).

### 2. Run the plan -- batch-step (context-lean, interactive)

Drive the build ONE DAG layer at a time so your context stays small and you can steer
between phases. Per layer:

```bash
python skill/scripts/run_delivery.py <plan.md> --repo <dir> --step [--workers N] [--executor <name>[:model][@effort]]
```

This runs only the next pending layer (independent slices fan out concurrently in isolated
worktrees), then EXITS, printing a ~10-line summary. Read the summary, relay it to the user,
and act on the gate (the exit code):
- **exit 0** (all passed): "Layer done, all green -- continue?" -> re-invoke `--step` for the next.
- **exit 2** (some failed/deferred): surface the failed slice + its failing test; offer
  inspect / retry / edit-the-slice / skip / abort.
- **exit 3** (complete): no layers left -- review the final ledger, optionally run the integration gate.

Re-invoking `--step` advances automatically (the ledger is the state). A partially-done layer
re-runs only its non-`done` slices, so "fix T3 then continue" works by editing + re-`--step`.

**IMPORTANT — merge accepted slices before the next `--step`.** Each slice runs in a worktree
branched from your base branch's **HEAD**; accepted work is committed to a `slice-<id>` branch and is
**NOT auto-merged**. You (the caller) must merge accepted `slice-*` branches into your base before
running a later layer whose slices depend on them — otherwise those worktrees branch from a HEAD
missing the deps' code, and the executor will fail on the missing imports (or rewrite the deps and be
correctly diff-rejected for editing files outside its allowance). After a layer passes, merge its
accepted slices, then re-`--step`:

```bash
git merge slice-T2 slice-T3 slice-T5   # the accepted slice branches from the layer
```

`--step` prints a **loud preflight warning** if it detects a pending slice depending on an accepted
-but-unmerged slice, so a missed merge is caught before the wasted dispatch.

**Live monitoring (optional -- background dispatch + poll).** To watch a multi-minute layer land
slice-by-slice instead of blocking on it, dispatch in the BACKGROUND and poll the digest between
turns:

```bash
python skill/scripts/run_delivery.py <plan.md> --repo <dir> --step --workers N   # background
python skill/scripts/run_delivery.py --status --repo <dir>                       # poll between turns
```

`--status` is context-cheap -- one short digest (layer position, done/running/pending, in-flight
model + elapsed, tokens + cost, a by-model rollup, gate). Read THAT, not the raw log. It is fresh
mid-run (events flush live), so you see slices finish one-by-one and can react at the next decision
point (escalate / repair / stop). Humans can `--watch [--interval N]` or `tail -f .cld/events.jsonl`.
The synchronous foreground `--step` stays the simple default.

Per slice inside a layer: isolate (git worktree `slice-<id>`) -> executor implements -> the
deterministic judge runs the REAL acceptance tests + diff-rule (failures feed back into a
retry) -> accepted work is committed to its `slice-<id>` branch -> ledger updated + telemetry event emitted.

**Why batch-step:** running the whole loop in one unbroken context burns large amounts of the
lead agent's tokens (every turn re-reads a growing context). Stepping one layer at a time keeps
your context to ~10 lines per layer and flat during interaction.

#### Choosing the executor & model (the picker)

**ALWAYS present the model shortlist before the first dispatch of a build -- every time, no
exceptions.** Do not skip it because "the default needs no decision": the user picks, not you.
The ONLY time you may skip is when the user has already named an executor this session (e.g. "use
the workhorse" / "use the heavy model") -- then echo that choice and proceed. A default existing
is not permission to choose on the user's behalf.

There are two equivalent surfaces; use whichever fits:

1. **CLI picker (preferred when you're about to run the script).** Run `run_delivery.py` WITHOUT
   `--executor`; if stdin is a TTY it prints the shortlist and prompts. (Non-interactive runs and
   `--step` loops fall back to the default workhorse, so they never block.) This is `cld.models.pick_executor`.
2. **Agent-presented (in chat).** Do NOT hand-assemble the dialog -- that is how it gets built
   wrong. Use the ONE helper that emits the complete, correct dialog:
   ```python
   from cld.models import list_models, recommend, render_chat_picker
   recs = recommend(available_ids=list_models())
   print(render_chat_picker(recs))   # paste this VERBATIM into chat as the picker
   ```
   `render_chat_picker(recs)` returns the whole dialog as one string: the curated shortlist
   (verbatim) + a numbered `Browse all models...` + a numbered `Other` free-text entry, ending in
   the "Pick one" prompt. Show it exactly, take the user's pick, pass it as `--executor`.

   **REQUIRED DIALOG SHAPE (what `render_chat_picker` guarantees -- do not produce a picker missing
   any of these):**
   1. the curated shortlist options (from `render_shortlist`, verbatim);
   2. **a literal `Browse all models...` option** -- selecting it opens the SECONDARY picker
      (the full unified drill-down below). This is NOT optional and NOT the same as "Other";
   3. `Other` (free-text id) as the final escape hatch.
   If a picker ever has only the shortlist + "Other" and no "Browse all models..." entry, it is
   WRONG -- the user cannot reach the full model list. The fix is always: call `render_chat_picker`
   instead of typing the options by hand.

   **Picker frequency -- choose ONCE per build, then STICK.** Present the executor picker ONCE,
   before the first dispatch of a build. That choice is the build default and persists for ALL
   slices and re-dispatches in the build. Do NOT re-run the picker per slice or on a plain
   re-dispatch (the live S1b interruption bug) -- reuse the executor already chosen. Re-run the
   picker ONLY when the user says "change executor" or starts a new build. The per-slice
   overrides below are deliberate exceptions, NOT a per-slice picker.

   **Per-slice executor (`executor:` tag).** A `## SLICE:` block may carry an optional
   `executor: <name>:<model>` line; that slice runs on that executor SILENTLY (the tag is the
   decision -- no prompt). Untagged slices use the build default. You MAY propose an upgrade for a
   slice you assess as genuinely HARD (a high bar -- not routine), ONCE, for the user to confirm;
   every other slice stays silent. This must NEVER become a per-slice picker (it would reintroduce
   the interruption the frequency rule removes). The orchestrator honors the tag automatically via
   `run_plan_parallel`'s `executor_factory`; an unknown spec fails only that slice, not the build.

   **Gates on any per-slice metered/untested model** (tag or proposal): a metered model hits the
   cost-confirm before that slice dispatches; an untested one runs
   `cld.validate.resolve_and_validate` first. The $0 flat workhorse stays the silent default.

   **GUARD -- render the options verbatim from `render_shortlist`; never improvise them.** Call
   `cld.models.render_shortlist(recs)` (or run the live pipeline) and present EXACTLY those lines /
   model ids. Do NOT hand-type, reorder, abbreviate, or recall the option list from memory -- the
   chat surface must match the program surface line-for-line. If you present via a UI dialog, copy
   each option's id/label straight from `render_shortlist` output -- same ids, same order, same
   count.

   **The SECONDARY picker (what `Browse all models...` opens) -- scalable drill-down.** With many
   models across executors, the full list is navigated by DRILL-DOWN, not one flat list. Build a
   unified index once: `cld.models.build_model_index(...)`. Then walk the levels, rendering each
   VERBATIM (the no-improvising guard applies to ALL of these -- copy the lines exactly, never
   hand-type):
   - **Executor:** `render_executor_level(index)` -> pick available executors.
   - **Provider:** `render_provider_level(index, executor=...)` -> pick model provider (each shows a count).
   - **Model:** `render_model_level(index, executor=, provider=)` -> the top ~12 base models
     (proven first), plus a `More...` entry (remaining) and a `Search...` entry.
   - **Effort:** `render_effort_level(choice)` -> ONLY if the chosen model has efforts; pick one
     (the CLI default is marked `(default)` -- enter keeps it). Map the pick to a spec with
     `cld.models.spec_with_effort(choice, effort)` (yields `executor:model@effort`, or the bare
     spec when the default effort is chosen).

   **Headless-only filter (default ON).** `render_model_level` filters to proven/likely by
   default (via `browse_filter`); offer a "show all (incl. untested)" toggle that passes
   `headless_only=False`. Untested picks still go through validate-on-demand before the build.

   **Search (at every level).** A `Search...` entry -> ask for free text -> call
   `cld.models.search_models(index, query, headless_only=...)` and present the results VERBATIM,
   each labeled `<label> (<model>) -- <provider> via <executor>`. Fuzzy substring over
   id/provider/executor/label, ranked exact->prefix->substring. (CLI surface can live-filter; the
   chat dialog uses the Search... -> free-text -> results-picker form.)

   Free-text "Other" remains the final escape hatch; a free-typed id is treated as untested.

   **Validate-on-demand (the headless guarantee).** Before dispatching a build on ANY pick
   whose `headless_status` is not proven/likely -- browsed, free-typed, or uncatalogued -- run
   `cld.validate.resolve_and_validate(spec, ...)`. It:
   - announces "Validating headless capability for <spec> -- this runs one trivial slice
     (~30s), please wait..." before the dispatch, and a verdict line after;
   - on a metered model (cheap-metered / premium-metered / metered-unknown) asks "validating
     bills real $ -- proceed?" BEFORE spending; declining means pick again;
   - on `proven`: proceed with the build;
   - on `known-bad` (built failing/no code): decline, record the verdict in the DURABLE
     evidence store (`~/.cld/validation-evidence.json` via `cld.evidence.EvidenceStore`),
     and RE-PRESENT the picker so the user picks another model. Verdicts persist across
     sessions: pass `evidence=store.statuses()` into `recommend`/`browse_models` so recorded
     known-bad models are hidden and recorded proven models show as proven. A recorded
     verdict is consulted BEFORE spending on a new validation; pass `force_revalidate=True`
     to re-run and refresh a stale verdict (e.g. a suspected transient failure);
   - on an executor error: report "couldn't validate" -- not a model verdict; let the user
     retry or pick another.
   Never dispatch a real build on an untested model without this gate.

`recommend()` ALWAYS includes the proven default workhorse as the default option. Enter selects it.

Rules (enforced by `pick_executor`, and required of the agent surface too):
- **Default = the proven $0 flat-rate or low-cost workhorse** (`opencode:opencode/deepseek-v4-pro`). Enter selects it.
- **Cost guardrail:** a `premium-metered` model (`confirm_cost=True`) requires an explicit "this
  bills real $ per dispatch -- proceed?" confirmation; declining falls back to the default. Never
  dispatch a billed model without that confirmation. (`free`/`flat` need none.)
- **Headless warning:** an `untested` model carries a warning. Offer `cld.validate.validate_model`
  (one trivial slice, real test as judge) to promote it to `proven`/`known-bad` before trusting it.
- The choice maps to `--executor <name>:<provider/model>` -- optionally with an `@<effort>` suffix
  for reasoning level (effort; default omits the suffix). A per-slice `executor:` field supports
  "heavy model on this one slice."

## OpenCode executor

**Default workhorse:** `opencode:opencode/deepseek-v4-pro` (cheap-metered, solid headless perf)

### Locked invocation form (verified on Windows)

```
opencode run "<task>" -m opencode/<provider/model> --format json --dir <workdir>
    --dangerously-skip-permissions --port
```

- `--format json` emits JSONL (one event per line); `parse_opencode_usage` reads the
  `step_finish` event(s) for token counts.
- `--dangerously-skip-permissions` is required for headless autonomy in isolated worktrees.
- `--port` (bare, no value) forces a fresh local server per dispatch; prevents stale session joins.
- `--dir <workdir>` scopes file writes to the target repo (clean worktree isolation confirmed).
- On Windows the npm shim is `opencode.cmd`, but the real `opencode.exe` must be used for
  long prompts (the `.cmd` shim routes through `cmd.exe /c`, which mangles multi-line argv).
  The executor auto-resolves the real `.exe` behind the shim; override with `OPENCODE_CLI_CMD`.

### Auth

Authenticate once per provider via the OpenCode TUI or `opencode auth add <provider>`.
Credentials are stored locally. Cost is billed per token at the provider's rates (not flat-rate).


Use `--dry-run` first to print the layers without dispatching.

#### Routing control flow

##### The one-screen routing plan

After slicing and assessing complexity, present the routing plan ONCE -- before the first
dispatch of a build, as a companion to the executor picker. Use the ONE helper that emits
the complete, correct plan (do not hand-assemble it):

```python
from cld.models import render_routing_plan
from cld.evidence import EvidenceStore
plan_text = render_routing_plan(
    slices,
    provider=chosen_provider,
    evidence=EvidenceStore().statuses(),
    available_ids=available_ids,
)
print(plan_text)   # paste VERBATIM into chat
```

Each row shows: slice id, complexity (`easy` / `standard` / `complex`), recommended model,
whether the plan uses the agent recommendation `[rec]` or a pinned executor tag `[you]`,
and `!` for complex slices that expect orchestrator repair on failure. Example output:

```
Routing plan (14 slices):
  T1   easy      <workhorse-spec>   [rec]
  T2   standard  <workhorse-spec>   [rec]
  T3   complex   <workhorse-spec>   [rec]  !
  T4   standard  <heavy-spec>       [you]
  ...
! = complex, expects orchestrator repair on failure
[rec] = auto-routed  [you] = pinned via executor: tag
```

Present this plan exactly as rendered -- same order, same ids, no edits.

##### Run-modes (how the user controls lead-agent behavior)

The run-mode is the lead agent's behavior during gate-4 repair. It is carried in the
conversation context -- there is NO CLI flag for it.

| Mode | How it is set | What happens at gate 4 |
|------|---------------|------------------------|
| **advise** (default) | No instruction given, or "ask me before fixing" | Lead agent summarizes failing slices, asks the user whether to repair, and waits. |
| **autonomous** | User said "fix things yourself" / "don't interrupt me" | Lead agent repairs without asking -- surgically fixes, commits, marks repaired, and continues. |
| **review each slice** | User said "show me each slice" / "I want to review" | After every slice result (pass or fail), the lead agent pauses and asks the user before proceeding. |
| **adjust first** | User says "pin T4 to the heavy model" before the build starts | Edit the slice's `executor:` tag (`[you]`) in the plan file, then run. The tag is the decision -- no further prompt. |

Only one mode is active at a time; the user changes it by saying so in chat.

##### The gate-4 repair loop

When `--step` exits with code **4**, the summary lists one or more `! NEEDS REPAIR` slices
(workhorse failed after exhausting its retries). This is NOT a terminal state -- the ledger
marks the slice `needs_repair`, not `failed`; without an explicit repair action it will be
re-dispatched unchanged on the next `--step`, which would fail again.

The lead agent's repair procedure:

1. **Advise mode:** summarize the failing slices and ask the user before touching anything.
   Autonomous mode: proceed directly to step 2.
2. **Diagnose:** read the failing test output from `.cld/<slice-id>/detail.json` (only on
   explicit request or as part of repair; do not pull raw output into context otherwise).
3. **Surgically fix** the failing source files in the repo (not in the worktree -- that is
   gone). Commit the fix to the current branch.
4. **Mark repaired** -- run this for each repaired slice:
   ```bash
   python skill/scripts/run_delivery.py <plan.md> --mark-repaired <slice_id> --ledger <path>
   ```
   This closes out the `needs_repair` entry so the next `--step` does not re-dispatch it
   from scratch. Without this step, the ledger would re-queue the slice and overwrite the fix.
5. **Continue:** re-invoke `--step` as normal. The repaired slice is now `done`; the DAG
   advances to the next pending layer.

Cheap escalation (quick-model to workhorse) is fully automatic and never reaches gate 4.
Gate 4 is triggered only when the workhorse itself exhausts retries -- a genuine hard case.
The ONLY gated spend at gate 4 is the orchestrator's repair effort (Claude's tokens); the
executor itself is not re-invoked until after the fix is committed and `--mark-repaired` has
run. Cheap routing and cheap escalation are automatic and free; orchestrator repair is the
only decision point.

**Inspecting on request:** raw diffs/logs/JSON are NOT on stdout -- per-slice detail is written
to `<dir>/.cld/<slice-id>/detail.json`. Only when the user asks "show me T3", read that one
file. Do not pull raw output into context otherwise.

**Keep orchestration cache-cheap (your context is a cached prefix):**
1. Summaries are append-only -- never edit or re-print a prior layer's summary; just add the new one.
2. Don't restate volatile data (timestamps, full token totals) at the top of your turns -- it churns the cached prefix.
3. Inspect a `.cld/` artifact at most once, and let it sit at the end of context -- re-reading it re-injects and churns the cache.

### 3. Integrate and verify

After a batch merges, run the **integration gate** (full suite on the merged tree --
slice-green != system-green). Re-run `run_delivery.py` to resume: already-done slices
are skipped via the ledger.

**Usage view:** run `run_delivery.py <plan> --usage` (or the `cross-llm-opencode-usage`
skill) for a combined per-build + account usage table (per-slice model/tokens/cost
from the ledger + provider aggregate stats). On-demand markdown -- renders in CLI and VS Code;
re-run to refresh.

## Reference material

- `references/architecture.md` -- the cld engine: modules, the locked CLI invocation form,
  executor registry, ledger, DAG, quota-awareness, observability.
- `references/authoring-plans.md` -- how to write good vertical slices + contracts.
