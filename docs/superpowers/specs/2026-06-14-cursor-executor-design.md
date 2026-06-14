# Cursor Executor — Design

**Date:** 2026-06-14
**Status:** Design approved (brainstorming), pending writing-plans
**Author:** Claude (Opus 4.8) + jhesham@hotmail.com

## Problem & Goal

Add **Cursor CLI (`cursor-agent`)** as a fourth executor alongside `gemini`, `composer`
(stub), and `opencode`. Cursor passed a full live feasibility gate (below), and its headless
surface is the cleanest of the CLIs — first-class `--model`, `--workspace`, `--force`,
`--trust` flags. This is a pure additive executor: it plugs into the existing pluggable
registry + picker + browse + validate + evidence + usage pipeline; nothing in the core changes.

## Feasibility — PROVEN live (2026-06-14)

- Installed on Windows via `irm 'https://cursor.com/install?win32=true' | iex`. The official
  top-level launcher shim is BROKEN here ("No version directories found" — a version-parse bug);
  the versioned binary `<LOCALAPPDATA>/cursor-agent/versions/<latest>/cursor-agent.cmd` works.
  (We replaced the broken root shim with a robust one, but the executor must not depend on that —
  it resolves the versioned path itself.)
- Logged in (`cursor-agent status` → `jhesham@hotmail.com`, Pro tier).
- **Headless works, no hang:** `cursor-agent -p "..." --output-format text` returned `PONG`.
  (The widely-reported `-p` hang did NOT reproduce. Bare `cursor-agent` DOES hang — it launches
  the interactive TUI and blocks on stdin; the executor must NEVER invoke it bare.)
- **Builds a real slice:** `-p --force --workspace <repo> "create calc.py ..."` wrote correct
  `def add(a,b): return a+b`, the acceptance test passed.
- `--model <id>` + `cursor-agent models` (`--list-models`) confirmed; rich catalog incl.
  `composer-2.5 (current)`, `composer-2.5-fast (default)`, claude/gpt-codex/gemini/grok/kimi/fable.
- **No headless usage metric:** Cursor exposes NO token/cost command. `about` = tier/model/email
  only; `/usage` is interactive-TUI-only (server-side numbers); local `ai-code-tracking.db` holds
  line-attribution, NOT tokens/cost. So no Cursor "account aggregate" is possible headlessly.

## Decisions (locked in brainstorming)

| Decision | Choice |
|---|---|
| Isolation | Reuse the engine's git worktree + pass it via cursor `--workspace`. (NOT cursor's own `-w/--worktree`.) |
| Default model | **Dynamic Composer** — resolve the newest `composer-*` from `--list-models`; surface in window-1 shortlist |
| Picker window 1 | Latest Composer (dynamically resolved) as the Cursor recommended entry |
| Picker window 2 ("Browse all") | ALL cursor models via `list_cursor_models()` → existing `browse_models`/`render_browse_list` |
| Cost tagging | SAME pattern as OpenCode: catalogued Composer = `cheap-metered`; everything else (browse-all) = `metered-unknown` + `untested` (no new cost_class) |
| Usage view | Per-build slices already show (provider-agnostic ledger); add a light `## Cursor account` block from `cursor-agent about` (tier + default model) + pointer to `/usage`/cursor.com (no headless numbers) |

## Current-state facts (verified)

- `Executor` protocol: `run(task, workdir) -> ExecutorResult{ok, diff, files_changed, token_usage, raw_log}`.
- `OpenCodeExecutor` is the template: `_oc_cmd()` (versioned/override resolution), `_default_runner`
  (subprocess, utf-8/replace), `capture_diff` (shared, filters `__pycache__`/.pyc), `parse_opencode_usage`,
  the `--dangerously-skip-permissions` + dispatch-guard (`step_finish` check), `--port` isolation.
- `KNOWN_EXECUTORS = ("gemini", "composer", "opencode")`; `get_executor` has per-name branches.
- Picker: `recommend(available_ids, evidence=)` (window 1), `browse_models`/`render_browse_list`
  (window 2, groups ANY id list by provider), `pick_executor`, `parse_executor_spec` (tolerant of
  slash form), `resolve_and_validate` (validate-on-demand), `EvidenceStore` (durable verdicts).
- Usage: `render_usage_table(ledger, oc_stats)` + `parse_opencode_stats`; `--usage` flag in run_delivery.

## Components

Five components, each mirroring the proven OpenCode equivalent. Nothing in protocol/judge/
ledger/DAG/orchestrator changes.

### 1. `src/cld/executors/cursor.py` — `CursorExecutor`
Satisfies `Executor`. argv:
`<cursor-cmd> -p "<prompt>" --output-format json --workspace <cwd> --model <model> --force --trust`
- `--force` (auto-approve writes) + `--trust` (skip the workspace-trust prompt — REQUIRED for
  headless; without it cursor blocks asking to trust the dir, confirmed live). These are the
  headless-safe form, analogous to opencode's `--dangerously-skip-permissions`.
- Runs via the injected `runner` (default = subprocess, utf-8/errors=replace).
- **Timeout guard** on the dispatch (a hung run can never freeze a build — same discipline as
  the Bug-B per-judge timeout). On timeout → `ok=False`.
- `rc != 0` or no usable result → `ok=False` with `raw_log`. Success → `parse_cursor_usage(raw)`
  + shared `capture_diff`.
- NEVER invoked bare (would hang the TUI); always `-p`.

### 2. `_cursor_cmd()` — versioned-path resolution
Override via `CURSOR_AGENT_CMD`; else resolve
`<LOCALAPPDATA>/cursor-agent/versions/<lexically-latest>/cursor-agent.cmd` on Windows
(non-Windows: `cursor-agent` on PATH). Falls back to bare `cursor-agent` if the versioned path
isn't found. (Mirrors the opencode `_oc_cmd` "bypass the broken shim" approach.)

### 3. `parse_cursor_usage(raw_json) -> dict[str,int]`
Parse Cursor's `--output-format json` for token counts (shape captured from a real dispatch at
build time — written against the REAL output, not guessed, per the OpenCode lesson). Returns
`{}` on unparseable input (best-effort; tokens are observability). Cost is NOT available
headlessly → per-slice `cost` stays `None`.

### 4. `list_cursor_models(runner)` + `resolve_composer_default(runner)` (in `models.py`)
- `list_cursor_models`: run `cursor-agent --list-models`, parse the `<id> - <label>` lines into
  ids (strip the trailing ` (current)`/` (default)` annotations). Returns `[]` on failure.
  Feeds the window-2 browse picker (ids prefixed `cursor:` via the spec mapping).
- `resolve_composer_default`: from that list, pick the `composer-*` id Cursor labels `(current)`;
  fallback `(default)`; fallback highest `composer-N.N`; final fallback the static string
  `"composer-2.5"`. This is the dynamic default that auto-tracks future Composer releases.

### 5. Catalog + registry + spec mapping
- `MODEL_METADATA`: add ONE curated Cursor entry for the resolved Composer
  (`cursor:composer-2.5`, `cheap-metered`/`heavy`/`untested`, note "Cursor's cost-optimized
  Composer; auto-tracks the current version"). All other cursor models reach the picker via
  `list_cursor_models` → `browse_models` as `metered-unknown`/`untested` (the OpenCode pattern).
- `KNOWN_EXECUTORS += ("cursor",)`; `get_executor("cursor")` → `CursorExecutor(**kwargs)`.
- Spec mapping: a `cursor:<model>` spec parses via the existing `parse_executor_spec`
  (`cursor` is a known executor; slash-form `cursor/<model>` tolerated too). `_spec_for` /
  `render_browse_list` emit `cursor:<id>` for cursor catalog ids (extend the gemini/opencode
  prefix logic to include cursor).

### 6. Usage view — Cursor account block
- Per-build: already works (ledger is provider-agnostic; cursor slices show model + tokens).
- Add `parse_cursor_about(text) -> dict` (tier, default model from `cursor-agent about`) and a
  CONDITIONAL `## Cursor account` block in `render_usage_table` — shown ONLY when the ledger has
  a `cursor:*` slice. It lists tier + default model + the note: "token/cost totals are
  server-side — run /usage in the Cursor TUI or see cursor.com (no headless metric)."
  `run_delivery.py --usage` shells `cursor-agent about` (timeout-guarded) to source it.

## Picker behavior (SKILL.md)

`cursor` joins the executor picker identically to opencode:
- Window 1 shortlist gains the Composer entry (`cursor:composer-2.5`, the dynamically-resolved
  current). Untested → "validate first"; promoted by the evidence store once validated.
- "Browse all models…" → Cursor's full `--list-models` set, grouped by provider, alongside
  gemini/opencode (same secondary picker).
- A `cursor:<model>` pick (tag or selection) flows through cost-confirm (metered) +
  validate-on-demand (untested) + the evidence store, unchanged.
- `--executor cursor` / `cursor:<model>` and the per-slice `executor:` tag both work via the
  existing factory + parse_executor_spec.

## Error handling

| Failure | Behavior |
|---|---|
| cursor-agent not installed / versioned path missing | `_cursor_cmd` falls back to bare `cursor-agent`; dispatch `ok=False` with install hint; `list_cursor_models` → []; picker degrades (cursor absent). Never crashes. |
| Not logged in | dispatch fails → `ok=False` → judge fails → existing retry/feedback. (Validation surfaces it as untested/known-bad honestly.) |
| Bare/hung invocation | Prevented by design (always `-p`) + the dispatch timeout guard. |
| `--list-models` fails | `list_cursor_models` → []; `resolve_composer_default` → static `"composer-2.5"`. |
| `cursor-agent about` fails (usage view) | Cursor account block shows "unavailable"; per-build table unaffected. |
| token usage unparseable | `parse_cursor_usage` → `{}`. |
| unknown `cursor:<model>` spec | that slice fails only (existing per-slice error handling), build continues. |

## Testing (fakes; live dispatch explicit, not in default suite)

- `CursorExecutor` (fake runner): correct argv (`-p`, `--output-format json`, `--workspace <cwd>`,
  `--model`, `--force`, `--trust`); diff capture; `ok=False` on nonzero; timeout → `ok=False`;
  never invoked bare. (Mirrors `test_opencode.py`.)
- `_cursor_cmd`: resolves versioned path on Windows; `CURSOR_AGENT_CMD` override wins; falls back
  when path missing.
- `parse_cursor_usage`: against the REAL captured JSON fixture (from the live build-time capture).
- `list_cursor_models`: fake `--list-models` text → ids (annotations stripped); `[]` on failure.
- `resolve_composer_default`: `(current)` wins → `(default)` → highest `composer-N.N` → static.
- registry: `get_executor("cursor")` → CursorExecutor; `"cursor" in KNOWN_EXECUTORS`.
- catalog/picker: the Composer entry surfaces in `recommend`; cursor ids group under their
  providers in `browse_models`; `_spec_for` emits `cursor:<id>`.
- usage: `parse_cursor_about` parses tier/model; `render_usage_table` adds the Cursor block ONLY
  when a cursor slice is present; cp1252-safe; degrades on missing `about`.
- Live (explicit): one build-time dispatch to capture the real `--output-format json` shape (for
  the parse_cursor_usage fixture) + a `resolve_and_validate` run to record Composer's headless
  verdict in the evidence store.

## Build approach (dogfood method)

Sliced TDD, builder-tagged. Pure-logic slices (`list_cursor_models`, `resolve_composer_default`,
`parse_cursor_usage`, `parse_cursor_about`) are dogfood candidates — and a fitting one to dispatch
to **Cursor itself once its executor works** ("Cursor dogfoods itself", the milestone we did with
OpenCode). The CursorExecutor seam, `_cursor_cmd`, registry, and SKILL.md are Claude-direct. The
live JSON-shape capture is Claude (one real dispatch), gating the parse_cursor_usage slice.

## Boundaries (YAGNI)

- NOT using cursor's native `-w/--worktree` — the engine's worktree isolation is the one model.
- NOT fabricating a Cursor cost/quota number — none is exposed headlessly; point to `/usage`/portal.
- NOT adding cursor's hundreds of model-effort variants to the curated catalog — only Composer is
  curated; the rest are reachable via browse-all (the OpenCode pattern).
- NOT changing protocol/judge/ledger/DAG/orchestrator — cursor is ADDED to the registry as a 4th
  entry; the `composer` stub STAYS (it's the documented worked-example).
