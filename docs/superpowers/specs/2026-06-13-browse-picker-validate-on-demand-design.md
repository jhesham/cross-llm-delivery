# Full-list Browse Picker + Headless Validate-on-Demand — Design

**Date:** 2026-06-13
**Status:** Design approved (brainstorming), pending writing-plans
**Author:** Claude (Opus 4.8) + jhesham@hotmail.com

## Problem & Goal

The model picker (chat + CLI) shows only the ~4 curated models from `recommend()`. Users
cannot browse the **full set of 46 OpenCode models**, and there is no honest "headless-only"
guarantee — 40 of those models are uncatalogued and therefore `untested` (we have no evidence
they actually build a slice headlessly). The chat "Other" option is blind free-text.

**Goal:** let the user browse ALL available models through the chat picker (and CLI), while
keeping the headless promise honest via **validate-on-demand**: any unproven pick is validated
against a real trivial slice BEFORE the real build runs. Cost stays gated — metered validation
confirms spend first.

**Non-goals / constraints:**
- Single source of truth: the chat dialog renders model options VERBATIM from a `models.py`
  render function — never hand-typed (the guard added in commit 4a2b77f, after a hand-typed
  `AskUserQuestion` dropped a real catalog entry and reordered the list).
- `AskUserQuestion` caps at 4 options + auto "Other" (free-text only). A second picker is not
  possible inside one dialog — hence the multi-step flow below.
- Reuse `validate_model` (T8, `src/cld/validate.py`) verbatim — no new validation logic.
- No live LLM in the default test suite — all tests use fakes.

## Decisions (locked in brainstorming)

| Decision | Choice |
|---|---|
| Uncatalogued-model headless filter | **Validate-on-demand** — show all; validate an untested pick before the real build |
| Browse flow shape | **Recommended-4 + "Browse all…"** → provider groups → models (two-step) |
| Metered validation cost | **Confirm before validating** a metered model; free/flat validate silently |
| Known-bad action | **Decline + re-present picker** (mark hidden, re-open so user reselects) |
| Known-bad persistence | **Session-only** — no catalog write; next session it's `untested` again |

## Architecture & data flow

Three new units in `src/cld/models.py` (the existing single-source-of-truth module) plus a gate
that wraps the existing `validate_model`. Nothing in the executor/judge/orchestrator core changes.

1. `browse_models(available_ids) -> dict[str, list[BrowseItem]]` — groups ALL available ids by
   provider, annotated with catalog metadata where known, else `untested`.
2. `render_browse_list(grouped) -> tuple[list[str], list[BrowseItem]]` — renders the grouped view
   verbatim (same guard/contract as `render_shortlist`: numbered lines + an ordered list so a
   numeric pick maps back to an id). ASCII / cp1252-safe.
3. `resolve_and_validate(spec, *, ...) -> ResolveResult` — the gate. Looks up the chosen model's
   `headless_status`; if unproven, runs `validate_model` (with the metered-cost confirm) and
   returns whether the build may proceed.

### Chat flow (two-step, respects the 4-option cap)
- **Dialog 1:** the curated top-4 (from `render_shortlist`) **+ a "Browse all models…" option**.
- **If "Browse all…":** **Dialog 2** = provider groups (`claude` / `gpt` / `gemini` / `deepseek` /
  `other`, ≤4 shown per dialog; if >4 groups, page with a "More…" entry). **Dialog 3** = the chosen
  group's models (paged the same way). Final "Other" = free-text id (the ultimate escape hatch).
- Every option in every dialog is copied from `render_browse_list` / `render_shortlist` output —
  never hand-typed.
- **Any `untested` pick** (browsed or free-typed) → `resolve_and_validate` runs before the build.

### CLI flow
`pick_executor` may gain a "browse all" entry, but the CLI prompt already lists every available
model, so the browse step is secondary there. `resolve_and_validate` applies to CLI picks too.

## Components

### `BrowseItem` (dataclass)
`id: str`, `provider: str`, `cost_class: str`, `headless_status: str`, `in_catalog: bool`.
- Catalogued models copy `cost_class`/`headless_status` from `MODEL_METADATA`, `in_catalog=True`.
- Uncatalogued models: `headless_status="untested"`, `in_catalog=False`, `cost_class` inferred
  from the id — a `-free` suffix → `"free"`, otherwise `"metered-unknown"`.

### `browse_models(available_ids) -> dict[str, list[BrowseItem]]`
Pure. For each id, build a `BrowseItem` and group by provider. Provider is parsed from the id:
strip a leading `opencode/`, then take the leading token up to the first `-` or `.` (e.g.
`claude-opus-4-8` → `claude`, `gpt-5.2` → `gpt`, `gemini-3.1-pro` → `gemini`, `deepseek-v4-pro`
→ `deepseek`); anything else → `other`. Group order: providers with catalogued/proven models
first, then alphabetical. Always self-include the flat-rate Gemini-CLI workhorse
(`gemini:gemini-3.1-pro-preview`) in the `gemini` group (same rule as `recommend`).

### `render_browse_list(grouped) -> tuple[list[str], list[BrowseItem]]`
Returns `(lines, ordered)`. `lines`: a header, then per group a provider label and numbered
entries `  N) <executor-spec>   <cost_class>   <headless_status>  [(!) warning]`. `ordered`: the
items in the same numeric order so `ordered[choice-1]` resolves the pick. Spec mapping reuses
`_spec_for` (`opencode/<x>` → `opencode:opencode/<x>`; `gemini:<x>` unchanged). ASCII only
(`$` for billed, `(!)` for untested) — the cp1252 console rule.

### `resolve_and_validate(spec, *, headless_status_of, validate_fn, confirm_fn, output_fn) -> ResolveResult`
`ResolveResult(spec, status, validated: bool, proceeded: bool, note: str)`.
- Resolve the chosen model's `headless_status` via `headless_status_of(spec)` (catalog lookup;
  unknown/free-typed → `"untested"`), honoring any in-session `known-bad` marks.
- `proven` / `likely` → passthrough, `proceeded=True`, `validated=False`.
- `untested`:
  - If the model is **metered** (`cost_class` in `cheap-metered`, `premium-metered`,
    `metered-unknown`): `confirm_fn("validating runs one real dispatch that bills ~$ — proceed?")`.
    On **no** → `proceeded=False`, `note="validation declined (cost)"`.
  - On **yes**, or a **free/flat** model: **emit a progress message first** via
    `output_fn` — `"Validating headless capability for <spec> — this runs one trivial slice
    (~30s), please wait…"` — so the user isn't left staring during the dispatch. Then run
    `validate_fn(spec)` (wraps `validate_model`). On return, emit the verdict line
    (`"… proven"` / `"… NOT headless-capable"` / `"… couldn't validate"`).
    - `proven` → `proceeded=True, validated=True`; promote in-session to `proven`.
    - `known-bad` → `proceeded=False, validated=True`; mark `known-bad` **in-session only**;
      caller re-presents the picker with this model hidden.
    - executor error / `untested` (the executor itself crashed — not a model verdict) →
      `proceeded=False, validated=False, note="couldn't validate"`; caller asks the user.
- The existing **build-time** premium cost-confirm (in `pick_executor`) is unchanged and separate
  from the validation-time confirm above.

### Known-bad handling (session-only)
A `known-bad` verdict is held in an in-session set (e.g. passed into `recommend`/`browse_models`
as `session_known_bad`), NOT written to `MODEL_METADATA`. Those models are filtered out of the
re-presented picker. Next session the set is empty → the model is `untested` and re-validatable.

## Error handling

| Failure | Behavior |
|---|---|
| `list_models` empty (OpenCode down) | Browse shows Gemini-only; "Browse all…" omitted; picker degrades to the curated workhorse. |
| Free-typed id not in `opencode models` | Treated `untested`; the validation dispatch fails cleanly → `known-bad` → don't proceed, re-present. |
| Validation executor crashes (CLI missing, dispatch error) | `untested` (not a model verdict) → report "couldn't validate," let user decide. |
| >4 provider groups or >4 models in a group | Paginate: show 3 + a "More…" entry that re-opens the next page (same dialog pattern). |
| Metered validation, user declines cost | `proceeded=False`; re-present picker so they choose a free/proven model instead. |

## Testing (fakes only; no live LLM in the suite)

- `browse_models`: provider grouping from ids; uncatalogued → `untested` + `in_catalog=False`;
  `-free` suffix → `free`, else `metered-unknown`; Gemini-CLI workhorse self-included in `gemini`.
- `render_browse_list`: numbering round-trips to the right id via `ordered`; cp1252-encodable;
  spec mapping (`opencode/x` → `opencode:opencode/x`).
- `resolve_and_validate`: proven passthrough (no validate call); untested+free → validates →
  proven proceeds; untested+metered → confirm gate, both yes (validates) and no (declines) paths;
  known-bad → `proceeded=False` + session-mark; executor-error → `untested`, "couldn't validate".
- progress message: before any `validate_fn` call, `output_fn` receives a "Validating headless
  capability … please wait" line (assert it's emitted before the verdict line).
- Known-bad session filter: a model marked known-bad is absent from the next `render_browse_list`.
- All using fake `validate_fn` / `confirm_fn` / `headless_status_of` — deterministic, offline.
- The live `validate_model` (T8) is already covered by its own integration test; not re-run here.

## Boundaries (YAGNI)

- NOT auto-benchmarking or ranking — browse shows availability + evidence, not scores.
- NOT persisting validation results to the catalog (session-only known-bad; promotions are
  in-session). A durable evidence store is a separate future feature.
- NOT changing the executor/judge/orchestrator/`--step` core — additions live in `models.py` +
  a thin gate; `validate_model` reused as-is.
- NOT a third-level "Other → picker" (the `AskUserQuestion` cap forbids it) — free-text "Other"
  remains the escape hatch, and free-typed ids are validated like any untested pick.

## SKILL.md updates

Document the browse flow and the validate-on-demand gate under the existing picker section:
- "Browse all models…" leads to provider-grouped sub-dialogs, all rendered from
  `render_browse_list` (reinforce the no-improvising guard for the new surface).
- Any untested pick is validated before the build; metered validation confirms cost first.
- A known-bad verdict declines the pick, hides it for the session, and re-presents the picker.
