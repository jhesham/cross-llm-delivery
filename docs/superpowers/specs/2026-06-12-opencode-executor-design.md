# OpenCode Executor + Model Picker — Design

**Date:** 2026-06-12
**Status:** Design approved (brainstorming), pending writing-plans
**Author:** Claude (Opus 4.8) + jhesham@hotmail.com

## Problem & Goal

Add **OpenCode CLI** as a second executor alongside Gemini, with a **full interactive
model-picker** so the USER can choose which LLM builds a slice — defaulting to the proven
flat-rate workhorse. OpenCode (`opencode run -m provider/model --format json`) fronts 40+
models across cost/capability tiers, which is exactly the multi-model breadth the
pluggable-executor design always intended (the `composer` registry stub has held the slot).

**Non-goals / constraints:**
- The USER picks the model (reproducibility + cost predictability) — NOT the orchestrator
  autonomously. Consistent with the BUG-2 decision.
- Cost discipline is paramount: some OpenCode models bill real money per dispatch (claude-opus,
  gpt-5) unlike flat-rate Gemini ($0). The picker must make cost visible and gate the expensive
  ones — we just spent two sessions killing a token drain and will not silently reopen cost.
- This build is **OpenCode only** — claude/cursor/codex executors are separate future adapters
  (the design leaves the pattern open). Codex is intentionally excluded (no clean headless mode).

## Key insight: safe by inheritance

Every prior token-bleed fix lives in the SHARED pipeline (judge, orchestrator, worktree,
driver), NOT in `GeminiExecutor`. OpenCode plugs into that same pipeline, so it inherits them
all by construction — it cannot reopen those wounds because it doesn't touch that code:

| Prior fix | Lives in (shared) | Inherited |
|---|---|---|
| BUG B — judge runs ONLY the slice's `acceptance_test_path` | `run_delivery.py::pytest_test_runner` | ✅ |
| BUG A — worktree path = abspath sibling (`--repo .` safe) | `worktree.py` | ✅ |
| Batch-step `--step` (context-lean lead agent) | `run_delivery.py` + orchestrator | ✅ |
| Per-judge timeout (hung test can't freeze a build) | `pytest_test_runner` | ✅ |
| Feedback→retry loop; compact summary→`.cld/` | `deliver_slice` / `summary.py` | ✅ |

The OpenCode executor contributes ONLY the "type the code" half (build argv, run CLI, parse its
tokens, capture diff). The one NEW cost-axis it introduces — premium-metered models — is a
deliberate dimension, gated by the picker (below), not a regression of the old bleeds.

## CLI facts (confirmed against opencode 1.17.0)

- `opencode run "<message>" -m <provider/model> --format json --dir <wt>` — headless one-shot.
  `--variant high|max|minimal` = provider reasoning effort (optional knob).
- `opencode models [provider]` — lists available model ids (the picker's data source). Confirmed
  output spans tiers: `deepseek-v4-flash-free`, `gemini-3.1-pro`, `claude-opus-4-8`, `gpt-5`, etc.
- `opencode stats` — token/cost statistics (a fallback token source if `--format json` is thin).
- `opencode providers`/`auth` — credential management.

## Critical nuance: CLI-headless ≠ MODEL-headless

The CLI being headless-capable does NOT guarantee a given MODEL reliably builds a slice headless.
A model can run headless yet (a) describe code instead of writing files, (b) stall/over-think in
one non-interactive turn, (c) be throttled (free tiers), or (d) ignore the "write files, don't
talk" framing — passing the CLI exit but producing an empty/garbage diff. The ONLY honest way to
know is to OBSERVE a model complete a real slice. So headless capability is tracked as
**evidence-backed status**, promoted by a validation harness, not asserted.

## Components

Five components + one targeted refactor. Everything else (protocol/judge/ledger/DAG/orchestrator/
`--step`/worktree) is unchanged.

### 1. `OpenCodeExecutor` — the seam  (`src/cld/executors/opencode.py`)
Satisfies the `Executor` protocol (`run(task, workdir, feedback) -> ExecutorResult`), mirroring
`GeminiExecutor`:
- argv: `opencode run "<prompt>" -m <provider/model> --format json --dir <cwd>` (+ `--variant`
  if a reasoning effort is configured). Windows: resolve `opencode.cmd` like the `gemini.cmd`
  fix, with an `OPENCODE_CLI_CMD` override.
- Runs via the **injected runner** (unit-testable, no live calls).
- `rc != 0` → `ExecutorResult(ok=False, raw_log=...)`. Missing CLI → clear "install via
  `npm i -g opencode-ai`" message, `ok=False` (never crashes a build).
- success → `parse_opencode_usage(raw)` + the shared `capture_diff`.

### 2. `parse_opencode_usage(raw_json) -> dict[str,int]` — pure
OpenCode's `--format json` shape differs from Gemini's `stats.models.*.tokens`. Written against
the REAL captured output (see Validation, task 1), not a guess. Returns `{}` on unparseable input
(best-effort; tokens are observability, not correctness — and for $0/flat models, irrelevant to
cost). Fallback: shell to `opencode stats` if `--format json` token data proves unreliable.

### 3. Model catalog  (`src/cld/models.py`) — the picker's brain
- `list_models(runner) -> list[str]` — parse `opencode models` into ids.
- `MODEL_METADATA` — curated table of recommended models:
  `{id, provider, cost_class, capability_class, headless_status, rework_risk, note, last_validated}`
  - `cost_class`: `free | flat | cheap-metered | premium-metered`
  - `capability_class`: `workhorse | heavy | quick`
  - `headless_status`: `proven | likely | untested | known-bad`
  - Seeded from evidence: Gemini 3.1 Pro = `flat / workhorse / proven`; others `likely`/`untested`.
  - Curation is DATA (edit the table to refresh), not a live benchmark scraper.
- `recommend(*, available_ids, job=None) -> list[Recommendation]` — pure: FILTER (only ids in
  `available_ids` AND `headless_status in {proven, likely}` for the recommended tier; `untested`
  offered-but-flagged; `known-bad` hidden) → BUCKET by job (workhorse/heavy/quick/free) → ANNOTATE
  (cost_class + headless_status + the one-line "why"). Pure & test-pinnable.

### 4. Validation harness  (`src/cld/validate.py`)
`validate_model(model, *, executor_runner, git_runner) -> ValidationResult`:
1. spin a throwaway temp git repo + a TRIVIAL known-answer slice (contract: "write `add(a,b)` in
   `calc.py` so `tests/test_calc.py` passes"; committed failing test = the objective bar).
2. dispatch that slice to OpenCode with `-m <model>`.
3. run the real acceptance test (scoped — Bug B fix applies via the shared runner).
4. `ValidationResult(model, passed, attempts, note, raw)`.
Promotes the model's `headless_status`: passed→`proven`, failed→`known-bad`, error→`untested(note)`.
Cheap (one tiny slice), verify-don't-trust (real test as judge). Validating a PREMIUM-metered
model triggers the same "bills real $" confirmation as picking one (no silent spend to validate gpt-5).

### 5. SKILL.md picker behavior — the UX
When the agent helps start a build (or the user asks "which model?"):
- `list_models` → `recommend()` → present the **bucketed shortlist** (5-10), each line:
  `<executor:provider/model> · <cost_class> · <headless_status> · <why>`.
- **Default pre-selected:** the proven $0/flat workhorse (Gemini) — "just go" needs no decision.
- **Cost guardrail:** picking a `premium-metered` model triggers an explicit "this bills real $
  per dispatch — proceed?" confirmation. `untested` carries a "may not complete builds reliably"
  warning.
- The choice flows into the existing `--executor opencode:<provider/model>` (already parses), and
  optionally a per-slice `executor:` for "use the heavy model on this one hard slice."

Example shown to the user:
```
Recommended executors (installed + available):
  WORKHORSE (default)
  ▸ gemini:gemini-3.1-pro-preview      · $0 flat · proven   · best $/passing-slice; our 14/14 workhorse
  HEAVY (hard slices, worth more $)
    opencode:anthropic/claude-opus-4-8 · premium ⚠ · likely · top capability; confirms cost on pick
  QUICK / BUDGET
    opencode:deepseek-v4-flash-free    · free ⚠   · untested· cheap; validate before trusting
Pick one [default: gemini workhorse]:
```

### Refactor (targeted, justified): shared `capture_diff`
`GeminiExecutor` and `OpenCodeExecutor` share identical post-dispatch logic
(`git add --intent-to-add`, `git diff HEAD`, parse `files_changed`). Extract into a shared
`capture_diff(runner, cwd) -> tuple[str, list[str]]` (e.g. `src/cld/executors/_capture.py`) so
both reuse it (DRY; prevents drift). Existing gemini tests must stay green (proves the extraction
is behavior-preserving).

## Build approach (same proven method as the original, ~5–7 slices)

Claude architects + judges; Gemini implements the pure slices; Claude writes the seam + live
validation. Once `OpenCodeExecutor` works, **dogfood a later slice TO OpenCode** to prove it as
an executor (e.g. have OpenCode build the picker logic or a utility) — the "OpenCode dogfoods
itself" moment, only possible after the adapter exists (no chicken-and-egg).

- DOGFOOD (Gemini): `parse_opencode_usage`, `list_models`, `recommend` (pure logic).
- CLAUDE-DIRECT: `OpenCodeExecutor` seam, the shared `capture_diff` refactor, the SKILL.md picker
  behavior, the live OpenCode validation dispatch.
- OPENCODE self-dogfood: one later, suitable slice once its executor is proven.

## Error handling

| Failure | Behavior |
|---|---|
| `opencode` not installed / not on PATH | dispatch `ok=False` with install hint; `list_models` → `[]`; picker degrades to "Gemini only". Never crashes. |
| `opencode models` fails/empty | recommender falls back to the proven Gemini default; picker says so. |
| model dispatch fails/times out | same as any executor: `ok=False` → judge fails → existing retry/feedback. The Bug-B per-judge timeout guards a hung test. |
| `parse_opencode_usage` unparseable | returns `{}` (best-effort, never raises). |
| validating a premium model | gated behind the "bills real $" confirmation (no silent spend). |

## Testing (unit tests use fakes; live dispatches are explicit, not in default suite)

- `OpenCodeExecutor` (fake runner): correct argv (`run`, `-m provider/model`, `--format json`,
  `--dir`), token parse, diff capture, `ok=False` on nonzero/missing-CLI. (Mirrors `test_gemini.py`.)
- `parse_opencode_usage`: fixture = the REAL captured JSON from the task-1 live dispatch.
- `list_models` / `recommend`: fake `opencode models` output; assert only-available + status-gated
  filtering, bucketing, annotation, default selection.
- `validate_model`: real-git harness (B1.1) + fake-pass and fake-fail executors; assert
  `proven` vs `known-bad` promotion.
- shared `capture_diff` refactor: existing gemini tests stay green (behavior-preserving).
- Live (explicit): task-1 OpenCode validation dispatch (captures JSON + first promotion); the
  OpenCode self-dogfood slice.

## Boundaries (YAGNI)

- NOT a live benchmark/auto-ranking engine — curation is human-authored metadata refreshed by
  evidence, not scraped benchmarks.
- NOT orchestrator-autonomous model selection — the USER picks.
- NOT adding claude/cursor/codex executors — OpenCode only; pattern left open for them.
- NOT changing the core (protocol/judge/ledger/DAG/orchestrator/`--step`) — OpenCode is ADDED to
  the registry as a third entry alongside the existing `gemini` and `composer`. The `composer`
  stub STAYS (it's the documented worked-example of a pluggable adapter); OpenCode does not
  replace it. `KNOWN_EXECUTORS` becomes `("gemini", "composer", "opencode")`.
