# Scalable Picker + Cursor Executor — Design (combined)

**Date:** 2026-06-14
**Status:** Design approved (brainstorming), pending writing-plans
**Author:** Claude (Opus 4.8) + jhesham@hotmail.com

## Problem & Goal

Adding Cursor as a 4th executor pushes the "Browse all models" picker from 46 to ~116 models —
a flat grouped list that no longer scales (heavy paging in the chat dialog, no way to find a
specific model, no headless-only safety). So this is TWO things in one spec, built in order:

1. **Picker/browse redesign** (built + tested against the 46 OpenCode models we have NOW):
   search, executor→provider→model drill-down, top-N-per-provider curation, and a
   headless-only filter (default ON). This makes the picker scale to any number of executors.
2. **CursorExecutor** (4th executor): plugs into the now-scalable picker; its ~70 models feed
   the unified index. Pure additive — protocol/judge/ledger/DAG/orchestrator unchanged.

Build order: **Part 1 (picker) first** — the hard UX is validated before Cursor's models pile on.

## Decisions (locked in brainstorming)

| Decision | Choice |
|---|---|
| Scope | ONE combined spec; picker redesign first, then Cursor |
| Top-N curation | Evidence + heuristic ranking: proven → catalogued/likely → collapse effort-tier noise; surface ~12/provider, rest searchable |
| Headless filter | Default ON (show only proven/likely); toggle "show all (incl. untested)" |
| Browse navigation | Executor → Provider → Model drill-down (each level ≤4-option-friendly) |
| Search | "Search LLM/model/provider…" → free-text → fuzzy substring over id+provider+executor; results labeled `<model> — <provider> via <executor>` |
| Cursor default model | Dynamic Composer (resolve newest `composer-*` from `--list-models`) |
| Cursor cost tagging | OpenCode pattern: Composer `cheap-metered`; rest `metered-unknown`/`untested` |
| Cursor usage view | Per-build slices already show; conditional `## Cursor account` block from `about` (no headless cost metric) |

---

# PART 1 — Scalable Picker / Browse Redesign

## Current state (verified)
- Window 1: `recommend(available_ids, evidence=)` → `render_shortlist` (bucketed curated list).
- Window 2: `browse_models(ids, session_known_bad=, evidence=)` groups ANY id list by provider
  (claude/gpt/gemini/deepseek/other via `_provider_of`); `render_browse_list` numbers them.
- `_spec_for` maps a catalog id → executor spec (`opencode/x`→`opencode:opencode/x`; `gemini:x` as-is).
- `list_models(runner)` → opencode ids; gemini workhorse is catalog-only.
- `EvidenceStore.statuses()` overlays durable proven/known-bad verdicts.

## The unified model index (the keystone)
A single in-memory list of records, built once per picker invocation, that every browse/search
feature reads:

```
ModelChoice = {
  spec: str,            # the --executor spec, e.g. "cursor:composer-2.5", "opencode:opencode/gpt-5"
  executor: str,        # "gemini" | "opencode" | "cursor"
  provider: str,        # "claude" | "gpt" | "gemini" | "deepseek" | "grok" | "kimi" | "other"
  model: str,           # bare model id for display, e.g. "composer-2.5", "gpt-5.2"
  label: str,           # human label, e.g. "Composer 2.5"
  cost_class: str,      # free|flat|cheap-metered|premium-metered|metered-unknown
  headless_status: str, # proven|likely|untested|known-bad (evidence overlay applied)
}
```

`build_model_index(*, opencode_ids, cursor_ids, evidence)` assembles it from:
`list_models` (opencode) + `list_cursor_models` (cursor) + the gemini/curated catalog, applying
the evidence overlay. `provider` via the existing `_provider_of` (extended to recognize
grok/kimi/qwen/glm/minimax/etc. so "other" shrinks). This replaces the ad-hoc per-call grouping.

## Feature A — headless filter (default ON)
`browse_filter(index, *, headless_only=True)`:
- ON (default): keep only `headless_status in {proven, likely}`. (known-bad always hidden.)
- OFF: keep everything except known-bad, but `untested`/`metered-unknown` carry the `(!)` warning.
The browse UI exposes a toggle option ("Show all models incl. untested"). On a pick of an
untested/unknown model, `resolve_and_validate` runs before the build (unchanged).

## Feature B — top-N per provider (collapse the noise)
`rank_provider_models(choices, *, n=12)` for one provider's choices:
1. Sort: `proven` first, then `likely`, then `untested`/`unknown`.
2. **Collapse effort-tier variants:** group by base model (strip trailing effort/speed suffixes
   like `-low/-medium/-high/-xhigh/-max/-fast/-thinking/-none`); keep ONE representative per base
   (prefer the plain/`current`/`default`-labeled, else the first). This turns cursor's ~30
   opus/codex/fable tiers into a handful of base entries.
3. Return the top `n`. The collapsed-away variants remain reachable via search.

## Feature C — navigation (Executor → Provider → Model)
Rendered for BOTH surfaces (CLI prompt + chat AskUserQuestion ≤4 options/level):
- **2a Executor:** list executors present in the index (gemini / opencode / cursor) + "Search…".
- **2b Provider:** providers available under the chosen executor (each with a count) + "Search…".
- **2c Model:** `rank_provider_models` top-N for that executor+provider + "More…" (paged remainder)
  + "Search…". Each line rendered VERBATIM from a render fn (the no-improvising guard holds).
Pure functions return `(lines, ordered_choices)`; the agent/CLI maps a numeric pick → spec.

## Feature D — search
`search_models(index, query, *, headless_only=True) -> list[ModelChoice]`:
- Case-insensitive substring match across `spec + provider + executor + model + label`.
- Ranked: exact model-id match → prefix match → substring; within ties, proven first.
- Respects the headless filter (same toggle). Returns [] if no match (UI re-prompts).
- Each result rendered as `<label> (<model>) — <provider> via <executor>  <cost> <status>` so
  ambiguous queries disambiguate by source. Examples (live behavior the design must satisfy):
  - `"compo"` → `Composer 2.5 — cursor` (+ `composer-2.5-fast` if shown).
  - `"3.1"` → `gemini-3.1-pro-preview — gemini (flat)`, `gemini-3.1-pro — opencode`,
    and any cursor gemini-3.1 routing — each a distinct labeled row.
- **CLI surface:** can do live-filter (real prompt). **Chat surface:** a "Search…" option →
  free-text answer → a fresh results picker (AskUserQuestion can't live-filter; this is the
  within-constraints equivalent of autocomplete).

## SKILL.md (picker behavior, rewritten)
- Window 1 unchanged (curated shortlist + "Browse all models…").
- "Browse all" now opens the **Executor→Provider→Model** drill-down with a **headless-only
  default** and a **Search…** entry at every level. Render every option verbatim from the new
  render fns (guard reinforced). Document the toggle + that untested picks validate-on-demand.

## Part 1 testing (fakes; no live calls)
- `build_model_index`: merges opencode+cursor+gemini ids into ModelChoice records; evidence
  overlay applied; provider classification (incl. grok/kimi/qwen → not "other").
- `browse_filter`: ON hides untested/unknown + known-bad; OFF keeps all but known-bad.
- `rank_provider_models`: proven-first ordering; effort-tier collapse (8 opus variants → 1 base);
  caps at n.
- navigation render fns: executor list, provider list w/ counts, model list top-N + More/Search;
  numbering round-trips to specs; cp1252-safe.
- `search_models`: `"compo"`→composer; `"3.1"`→multiple labeled gemini routings; exact>prefix>
  substring ranking; headless filter respected; [] on no match.

---

# PART 2 — CursorExecutor

(Mechanics unchanged from the standalone cursor design; it feeds Part 1's index.)

## Feasibility — PROVEN live (2026-06-14)
- Installed on Windows (`irm 'https://cursor.com/install?win32=true' | iex`). Top-level launcher
  shim is BROKEN here ("No version directories found"); the versioned binary
  `<LOCALAPPDATA>/cursor-agent/versions/<latest>/cursor-agent.cmd` works — the executor resolves
  that itself (don't depend on the root shim).
- Logged in (Pro tier). Headless `-p` works, NO hang (`PONG`). Bare `cursor-agent` DOES hang
  (interactive TUI on stdin) → NEVER invoke bare.
- Builds a real slice: `-p --force --trust --workspace <repo>` wrote correct `add(a,b)`, test passed.
- `--model <id>` + `--list-models` confirmed (composer-2.5 `(current)`, `-fast (default)`, +
  claude/gpt-codex/gemini/grok/kimi/fable). NO headless usage metric (about=tier/model only;
  /usage is TUI-only; local ai-code-tracking.db = line attribution, not tokens/cost).

## Components
1. **`src/cld/executors/cursor.py` — `CursorExecutor`** (mirrors OpenCodeExecutor): argv
   `<cursor-cmd> -p "<prompt>" --output-format json --workspace <cwd> --model <model> --force --trust`.
   Injected runner; **timeout guard** (hung run can't freeze a build); `rc!=0`/no result → `ok=False`;
   success → `parse_cursor_usage` + shared `capture_diff`. Never invoked bare.
2. **`_cursor_cmd()`** — `CURSOR_AGENT_CMD` override; else resolve the versioned
   `cursor-agent.cmd` on Windows (lexically-latest version dir); fallback bare `cursor-agent`.
3. **`parse_cursor_usage(raw_json)`** — tokens from cursor's `--output-format json` (written
   against the REAL captured shape — a live capture slice gates this, per the OpenCode JSONL lesson);
   `{}` on unparseable. Cost not available → per-slice `cost` stays None.
4. **`list_cursor_models(runner)` + `resolve_composer_default(runner)`** (in models.py) — parse
   `cursor-agent --list-models` into ids (strip ` (current)`/` (default)` annotations); feed the
   Part-1 index. `resolve_composer_default`: newest `composer-*` labeled `(current)` → `(default)`
   → highest `composer-N.N` → static `"composer-2.5"`.
5. **Catalog + registry** — add ONE curated entry for resolved Composer (`cursor:composer-2.5`,
   `cheap-metered`/`heavy`/`untested`); `KNOWN_EXECUTORS += ("cursor",)`; `get_executor("cursor")`
   branch; `_spec_for`/`parse_executor_spec` handle `cursor:`/`cursor/` (extend the prefix logic).
6. **Usage view** — `parse_cursor_about(text)` (tier, default model) + a CONDITIONAL
   `## Cursor account` block in `render_usage_table`, shown ONLY when the ledger has a `cursor:*`
   slice; notes "token/cost are server-side — run /usage in the Cursor TUI or see cursor.com".
   `run_delivery.py --usage` shells `cursor-agent about` (timeout-guarded).

## Part 2 error handling
| Failure | Behavior |
|---|---|
| not installed / versioned path missing | `_cursor_cmd` falls back to bare; dispatch `ok=False` + install hint; `list_cursor_models`→[]; picker drops cursor. |
| not logged in | dispatch `ok=False` → judge fails → retry/feedback; validation = honest untested/known-bad. |
| bare/hung | prevented (always `-p`) + timeout guard. |
| `--list-models` fails | `list_cursor_models`→[]; `resolve_composer_default`→static. |
| `about` fails | Cursor account block → "unavailable"; per-build table fine. |
| usage unparseable | `parse_cursor_usage`→{}. |
| unknown `cursor:<model>` spec | that slice fails only; build continues. |

## Part 2 testing (fakes; live dispatch explicit)
- `CursorExecutor`: correct argv (`-p`,`--output-format json`,`--workspace`,`--model`,`--force`,
  `--trust`); diff capture; `ok=False` on nonzero; timeout→`ok=False`; never bare.
- `_cursor_cmd`: versioned-path resolution; `CURSOR_AGENT_CMD` override; fallback.
- `parse_cursor_usage`: real captured-JSON fixture.
- `list_cursor_models`: fake `--list-models` → ids (annotations stripped); []  on fail.
- `resolve_composer_default`: `(current)`→`(default)`→highest→static.
- registry/catalog: `get_executor("cursor")`; Composer in `recommend`; cursor ids in the index
  under right providers; `_spec_for`→`cursor:<id>`.
- usage: `parse_cursor_about`; Cursor block only when a cursor slice present; cp1252-safe; degrades.
- Live (explicit): one dispatch to capture the real JSON shape (fixture) + a `resolve_and_validate`
  recording Composer's headless verdict in the evidence store. **Dogfood:** the pure-logic Part-2
  slices are dogfood candidates — once CursorExecutor works, dispatch one TO Cursor itself
  ("Cursor dogfoods itself").

## Boundaries (YAGNI)
- Part 1 built against the CURRENT 46 opencode models; cursor just feeds more into it.
- NOT cursor's native `-w/--worktree` — engine worktree + `--workspace` is the one isolation model.
- NOT fabricating a Cursor cost number — none exists headlessly.
- NOT cataloguing cursor's hundreds of effort variants — only Composer curated; rest via index/search.
- NOT changing protocol/judge/ledger/DAG/orchestrator; `composer` stub STAYS.
