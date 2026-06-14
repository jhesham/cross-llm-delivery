# Scalable Picker + Effort Axis + Cursor + Per-Unit Routing — Design (combined)

**Date:** 2026-06-14
**Status:** Design approved (brainstorming), pending writing-plans
**Author:** Claude (Opus 4.8) + jhesham@hotmail.com

## Problem & Goal

Adding Cursor (4th executor, ~70 models) breaks the flat "Browse all" picker (→116 models),
AND surfaced a dimension the original design wrongly flattened: **effort is a real, valuable
choice** (a cheap model on high effort can beat its default at a fraction of a top model's cost;
Opus-4.8 on *medium* can match a cheaper model — better value than high). Plus, large multi-slice
builds want **per-slice (and per-sub-slice) model/effort routing**, agent-prompted at unit
boundaries. This one spec covers four parts, built in order so each is independently testable:

1. **Scalable picker + effort axis** — unified model index, headless-only filter (default ON),
   executor→provider→model drill-down, top-N per provider, fuzzy search, and **effort as a
   second pick** (default = CLI's pre-selected). Built against the current 46 OpenCode models.
2. **CursorExecutor** — 4th executor; feeds its models+efforts into the index.
3. **Opt-in per-slice review mode** — off by default (the S1b "pick once, stick" rule stays);
   when on, the agent prompts executor/model/effort at each slice start.
4. **Sub-slices** (one level) — a slice may contain `## SUBSLICE:` units, each independently
   routable + (in review mode) prompted.

## Decisions (locked in brainstorming)

| Decision | Choice |
|---|---|
| Scope | ONE combined spec, four parts, in the order above |
| Effort model | Base model + **separate effort axis**; executor maps (base, effort) → CLI form |
| Effort default | CLI's pre-selected default; user may override; not forced |
| Headless filter | Default ON (proven/likely only); toggle "show all incl. untested" |
| Browse nav | Executor → Provider → Model (→ Effort), each ≤4-option-friendly |
| Top-N | Evidence + likely ranked; **base models** surfaced (effort is a 2nd pick, NOT separate rows); ~12/provider; rest via search |
| Search | "Search…" → free-text → fuzzy substring over id+provider+executor+label; labeled by source |
| Per-slice re-prompt | **Opt-in review MODE, off by default**; S1b fix intact when off |
| Choice persistence | Plan tag (deterministic) + per-unit in-session override recorded in the ledger |
| Sub-slices | ONE nesting level (`## SUBSLICE:` under `## SLICE:`) |
| Dogfood routing | ~90% gemini workhorse; ONE small late slice → `cursor:composer-2.5` via CLI (headless proof) |

## Effort facts (verified live)
- **Cursor:** effort suffixes `low, medium, high, xhigh, max` (× optional `fast`, × optional
  `thinking`); the plain/unlabeled id is often the default (e.g. `claude-opus-4-8-high` = "Opus
  4.8 1M", `composer-2.5-fast` = "(default)"). Effort applied by choosing the suffixed model id.
- **OpenCode:** `--variant high|max|minimal` (free string); no variant = provider default.
- **Gemini:** no effort axis (n/a — effort pick is skipped/disabled).

---

# PART 1 — Scalable Picker + Effort Axis  (built against current 46 opencode models)

## The unified model index (keystone)
`build_model_index(*, opencode_ids, cursor_models, evidence) -> list[ModelChoice]`:

```
ModelChoice = {
  spec: str,            # base --executor spec, e.g. "cursor:composer-2.5", "opencode:opencode/gpt-5"
  executor: str,        # gemini | opencode | cursor
  provider: str,        # claude|gpt|gemini|deepseek|grok|kimi|qwen|glm|minimax|other
  model: str,           # base model id (effort suffix stripped), e.g. "claude-opus-4-8"
  label: str,           # human label
  cost_class: str,      # free|flat|cheap-metered|premium-metered|metered-unknown
  headless_status: str, # proven|likely|untested|known-bad (evidence overlay applied)
  efforts: list[str],   # available effort levels for this base (e.g. ["low","medium","high","xhigh","max"]); [] if none
  default_effort: str | None,  # the CLI's pre-selected default effort (None for gemini/opencode-plain)
}
```
Built from `list_models` (opencode) + `list_cursor_models` (cursor, returns id+label so efforts
group) + the gemini/curated catalog. `provider` via `_provider_of` (extended to
grok/kimi/qwen/glm/minimax so "other" shrinks). **Effort grouping:** cursor's suffixed ids
(`claude-opus-4-8-low/-medium/-high/...`) collapse into ONE ModelChoice with `efforts=[...]` and
`default_effort` = the level whose label is plain/marked default.

## Feature A — headless filter (default ON)
`browse_filter(choices, *, headless_only=True)`: ON keeps `proven|likely` (known-bad always
hidden); OFF keeps all but known-bad (untested/unknown carry `(!)`). UI toggle "Show all incl.
untested". Untested pick → `resolve_and_validate` before build (unchanged).

## Feature B — top-N per provider
`rank_provider_models(choices, *, n=12)`: sort proven→likely→untested; one row per BASE model
(efforts are not separate rows — that's the whole point); return top n. Long tail via search.

## Feature C — navigation (Executor → Provider → Model → Effort)
Pure render fns returning `(lines, ordered)`; verbatim (no-improvising guard):
- **Executor:** executors in the index + "Search…".
- **Provider:** providers under the chosen executor (+counts) + "Search…".
- **Model:** `rank_provider_models` top-N + "More…" + "Search…".
- **Effort:** ONLY if the chosen model has `efforts`; list them with `default_effort`
  pre-selected (enter = default). Gemini/opencode-plain skip this step. The chosen
  (model, effort) → final spec via `spec_with_effort(choice, effort)`.

## Feature D — search
`search_models(index, query, *, headless_only=True) -> list[ModelChoice]`: case-insensitive
substring over `spec+provider+executor+model+label`; ranked exact-id→prefix→substring, proven
first; headless filter respected; [] on no match. Rendered `<label> (<model>) — <provider> via
<executor>  <cost> <status>`. Must satisfy: `"compo"`→Composer (cursor); `"3.1"`→gemini-3.1
direct + opencode + any cursor routing, each labeled. CLI = live filter; chat = "Search…" option
→ free-text → fresh results picker (AskUserQuestion can't live-filter).

## Feature E — effort → CLI mapping (in the executors, but designed here)
`spec_with_effort(choice, effort)` produces an executor-resolvable spec carrying the effort, and
each executor maps it to its CLI form: **cursor** → the suffixed model id
(`claude-opus-4-8` + `medium` → `claude-opus-4-8-medium`); **opencode** → `--variant <effort>`;
**gemini** → ignored. Spec form: `<executor>:<model>@<effort>` (e.g. `cursor:claude-opus-4-8@medium`,
`opencode:opencode/gpt-5@high`); `@<effort>` omitted = CLI default. `parse_executor_spec` extended
to split `@effort` (back-compatible: no `@` = today's behavior).

## Part 1 testing (fakes)
- `build_model_index`: merges 3 sources; evidence overlay; provider classification; effort
  grouping (opus suffix variants → 1 base w/ efforts + default_effort).
- `browse_filter` ON/OFF; `rank_provider_models` proven-first + base-only + cap.
- nav render fns: each level numbers round-trip to specs; effort step only when efforts present;
  cp1252-safe.
- `search_models`: "compo"/"3.1" cases; ranking; filter respected; [].
- `spec_with_effort` + `parse_executor_spec` `@effort`: cursor→suffix, opencode→variant,
  gemini→ignored; no-`@` back-compat.

---

# PART 2 — CursorExecutor  (feeds Part 1's index)

## Feasibility — PROVEN live (2026-06-14)
Installed on Windows; versioned binary works (top-level shim broken — executor resolves the
versioned path). Logged in (Pro). Headless `-p` works, no hang (`PONG`); bare hangs → never bare.
Builds a real slice (`-p --force --trust --workspace`). `--model` + `--list-models` confirmed.
No headless usage metric (about=tier/model; /usage TUI-only; local db = line attribution).

## Components
1. **`src/cld/executors/cursor.py` — `CursorExecutor`**: argv `<cursor-cmd> -p "<prompt>"
   --output-format json --workspace <cwd> --model <model[-effort]> --force --trust`. Injected
   runner; **timeout guard**; `rc!=0`/no result → `ok=False`; success → `parse_cursor_usage` +
   shared `capture_diff`. Maps `@effort` → the cursor suffix. Never bare.
2. **`_cursor_cmd()`**: `CURSOR_AGENT_CMD` override; else versioned `cursor-agent.cmd` (latest
   version dir) on Windows; fallback bare.
3. **`parse_cursor_usage(raw_json)`**: tokens from cursor JSON (REAL captured shape — a live
   capture slice gates it); `{}` on miss. Cost None (not exposed).
4. **`list_cursor_models(runner)` + `resolve_composer_default(runner)`**: parse `--list-models`
   into (id, label) → base models + efforts for the index; resolve newest `composer-*`
   (`(current)`→`(default)`→highest→static `composer-2.5`).
5. **Catalog + registry**: curated Composer entry (`cursor:composer-2.5`, cheap-metered/heavy/
   untested); `KNOWN_EXECUTORS += ("cursor",)`; `get_executor("cursor")`; spec mapping for
   `cursor:`/`cursor/` + `@effort`.
6. **Usage view**: `parse_cursor_about` (tier, default model) + CONDITIONAL `## Cursor account`
   block (only when a `cursor:*` slice in ledger) noting usage is server-side (/usage / portal).

## Part 2 testing — as in the standalone cursor design (argv incl. effort suffix; `_cursor_cmd`;
parse_cursor_usage fixture; list/resolve; registry/catalog; usage block conditional; live capture
+ validate-on-demand recording Composer's verdict). **DOGFOOD: one small late slice (e.g.
`parse_cursor_about` or `resolve_composer_default`) → `cursor:composer-2.5` via the cursor CLI**
— the single headless-proof Composer touchpoint (everything else dogfoods to gemini).

---

# PART 3 — Opt-in Per-Slice Review Mode

## Behavior
- **Default OFF:** build behaves exactly as today — executor chosen once, sticks, no per-slice
  prompt (the S1b fix is preserved). A slice's plan `executor:`/`@effort` tag still applies
  silently; the agent's existing "propose upgrade on genuinely-hard slice" rule still applies.
- **Opt-in ON:** the user enables a per-slice review mode (CLI `--per-slice-pick`, and/or telling
  the lead agent "review executor per slice"). When ON, at EACH slice start the agent presents the
  picker (current choice pre-selected; enter = keep) so the user can revisit
  executor/provider/model/effort for that slice.
- The chosen executor+model+effort for a slice applies to THAT slice only (not sticky), is passed
  to the orchestrator for that slice, and is **recorded in the ledger** (so resume + the usage
  view show what actually ran).

## Mechanics
- `run_delivery.py` gains `--per-slice-pick` (default off). The `--step` driver, when the mode is
  on and a slice has no explicit tag, surfaces the picker before dispatching that slice; the
  resolved spec becomes that slice's executor (via the existing per-slice `executor_factory`).
- SKILL.md documents the mode: OFF = current behavior; ON = prompt-per-slice; the agent must NOT
  prompt per slice unless the mode is on or a slice carries a tag (keeps S1b fix intact).

## Part 3 testing
- mode OFF: no per-slice prompt; build default used; existing tests unchanged.
- mode ON: a hook/callback is invoked per slice with the current choice; its return becomes that
  slice's spec; recorded in the ledger entry (model/effort visible).
- a tagged slice is honored without prompting even in ON mode (tag = decision).

---

# PART 4 — Sub-slices (one level)

## Plan model
- A `## SLICE:` block MAY contain `## SUBSLICE: <id>` blocks (same fields: brief, files,
  acceptance_test_path, deps, optional executor/@effort). One nesting level only.
- `load_slices` parses sub-slices into `SliceTask.subslices: list[SliceTask]` (a sub-slice is a
  SliceTask with `parent_id` set). `slices_to_markdown` round-trips them.

## Orchestration
- The DAG/orchestrator flattens a slice's sub-slices as ordered children executed under the
  parent (parent "done" when all sub-slices accepted). Each sub-slice is delivered like a slice
  (own worktree, own executor via tag/default/review-mode, own ledger entry keyed `parent/sub`).
- Per-slice review mode (Part 3) applies at sub-slice boundaries too: when ON, the agent prompts
  for each sub-slice's executor/model/effort.
- Ledger records each sub-slice (status + model + effort + tokens), so usage view shows them
  nested/attributed under the parent.

## Part 4 testing
- `load_slices` parses `## SUBSLICE:` into `subslices` with parent_id; round-trips.
- orchestrator runs sub-slices under their parent; parent done iff all children accepted; a failed
  sub-slice fails only itself (+ marks parent incomplete), not the build.
- per-sub-slice executor tag honored; review-mode prompt fires per sub-slice when ON.
- ledger + usage attribute sub-slice model/effort/tokens under the parent.

---

## Build order (sliceable, testable)
Part 1 (picker+effort, vs 46 opencode models) → Part 2 (CursorExecutor feeds it; Composer CLI
dogfood) → Part 3 (opt-in per-slice review) → Part 4 (sub-slices, most structural, last).
Each part ships independently green.

## Dogfood routing
~90% of dogfood slices → **gemini workhorse** ($0 flat, proven — keep the build cheap/reliable).
Pure-logic Part-1/2 slices may also go to gemini or opencode/deepseek-v4-pro (proven).
**Exactly one small late slice → `cursor:composer-2.5` via the cursor CLI** (since CursorExecutor
won't exist when earlier slices run) — the headless-proof Composer touchpoint; non-load-bearing
(gemini can redo it if Composer hiccups).

## Boundaries (YAGNI)
- Part 1 built against current 46 models; cursor feeds more later.
- Effort is a 2nd pick over BASE models — NOT separate rows per variant (the explosion we avoid);
  full variants still reachable via search.
- NOT cursor's `-w/--worktree` — engine worktree + `--workspace`.
- NOT fabricating cursor cost numbers — none exposed headlessly.
- Per-slice review is OPT-IN — default stays "pick once, stick" (S1b fix).
- Sub-slices = ONE level only (no arbitrary recursion).
- NOT changing the judge/protocol; `composer` stub STAYS.
