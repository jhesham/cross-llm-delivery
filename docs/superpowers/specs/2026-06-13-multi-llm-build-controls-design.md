# Multi-LLM Build Controls — Design (3 features, 1 spec)

**Date:** 2026-06-13
**Status:** Design approved (brainstorming), pending writing-plans
**Author:** Claude (Opus 4.8) + jhesham@hotmail.com

## Problem & Goal

Three related improvements to the cross-llm-delivery engine, all touching the
executor / ledger / picker surfaces. Bundled in one design because they overlap (per-slice
executor selection needs the ledger to record which model ran; the usage view reads that),
but delivered as **three independent plans** sequenced **quick-wins-first**.

1. **Picker frequency** — the executor picker re-triggers per slice / re-dispatch (seen live
   on S1b), interrupting builds. It should be chosen ONCE per build and stick.
2. **Per-slice executor by complexity** — route each slice to a model matched to its
   difficulty (hard → stronger/metered, simple → the $0 flat workhorse), so most slices stay
   free and only genuinely hard ones spend.
3. **Unified usage view** — one `/cross-llm-delivery-usage` (CLI + VS Code) showing LLM usage
   for a build, instead of launching multiple CLIs / web portals.

## Decisions (locked in brainstorming)

| Decision | Choice |
|---|---|
| Structure | ONE spec, THREE independently-executable plans |
| Sequencing | Quick-wins-first: A (picker freq) → B (per-slice executor) → C (usage view) |
| Per-slice: who decides | Plan-author writes `executor:` per slice; lead agent MAY propose an upgrade at dispatch; user confirms |
| Per-slice: cost gate | Per-escalation cost-confirm; an untested metered model also runs validate-on-demand first |
| Usage scope | BOTH per-build (ledger) + account aggregate (`opencode stats`), side by side |
| Usage refresh | On-demand snapshot (re-invoke to refresh); markdown so CLI + VS Code render identically |

## Shared foundation (the keystone)

**Ledger enrichment** unblocks both per-slice tracking and the usage view. `LedgerEntry` gains
`model`, `token_usage`, `cost`. The data ALREADY flows: `deliver_slice` surfaces
`token_usage` (orchestrator.py:101), executors parse it (`parse_token_usage`,
`parse_opencode_usage`). It just isn't persisted today. This lands in Feature C's plan (it's
the foundation of the view) but is referenced by B.

## Current-state facts (verified 2026-06-13)

- `SliceTask` (`src/cld/executors/base.py`): `id, brief, files, acceptance_test_path, deps`.
  NO executor/model field.
- `LedgerEntry` (`src/cld/ledger.py`): `slice_id, status, commit, attempts`. NO usage fields.
- `run_plan_parallel` takes ONE `executor`; `deliver_slice(executor=...)` already returns
  `token_usage`.
- `parse_executor_spec` (`run_delivery.py`) parses `name:model`, tolerant of the slash form
  (`opencode/<m>`), defaults to gemini. `get_executor(name, **kw)` raises ValueError listing
  KNOWN_EXECUTORS on an unknown name.
- SKILL.md ALREADY promises a per-slice `executor:` field ("heavy model on this one slice") —
  but `slice.py` does NOT parse it. Feature B closes this over-promise.
- `opencode stats` prints aggregate $/tokens; `opencode export <id>` is per-session JSON
  (NB: `opencode export` with no id BLOCKS on a prompt — always pass an id). Gemini CLI has no
  usage flag (flat-rate quota %-screen only).

---

## Feature A — Picker frequency (quick win, ~SKILL.md only)

**Behavior:** the executor is chosen ONCE per build (the first dispatch). That choice persists
for ALL slices and re-dispatches in the build. The agent re-prompts ONLY when the user
explicitly says "change executor" (or starts a new build). A per-slice `executor:` tag or an
agent-proposed escalation (Feature B) is a deliberate exception, not a re-prompt.

**Data flow:** SKILL.md rule change only. "Stick" relies on the agent's existing conversation
context for the build (it already knows the `--executor` it chose and passes it on each `--step`
invocation) — no new persisted state. If a future build runs across context loss, the resolved
executor is recoverable from the last `--step` command / the agent simply re-confirms once. No
engine code.

**Error handling:** none (behavioral guidance).

**Testing:** SKILL.md prose; no unit test (it's instruction, not code). Acceptance = the rule
is unambiguous and names the S1b re-prompt failure mode.

---

## Feature B — Per-slice executor by complexity

### Layer 1 — explicit `executor:` field (deterministic)
- `slice.py` parses an optional `executor:` line in a `## SLICE:` block onto a new
  `SliceTask.executor: str | None = None` field.
- `run_plan_parallel` resolves per slice: `spec = slice.executor or build_default` →
  `parse_executor_spec(spec)` → `get_executor(name, **kw)` → that executor runs THAT slice.
  Slices in one parallel layer may use DIFFERENT executors concurrently (construct per slice,
  not one shared object).

### Layer 2 — agent proposal (adaptive)
- At dispatch, the lead agent MAY assess a slice as harder than its tag and propose an upgrade
  (using the catalog's `capability_class` tiers via `recommend`). The USER confirms. This lives
  in the lead-agent / SKILL.md layer; the orchestrator just honors the resolved spec.

### Cost & headless gates (per escalation)
- Routing a slice to a metered model (`cost_class` in cheap/premium/metered-unknown) hits the
  existing cost-confirm BEFORE that slice dispatches.
- If that metered model is `untested`, run `resolve_and_validate` first (validate-on-demand).
- The $0 flat workhorse stays the silent default; spending is always explicit.

**Data flow:** `slice.py` → `SliceTask.executor` → orchestrator per-slice resolution →
`get_executor`. Gates in the agent/SKILL layer.

**Error handling:** unknown `executor:` value → that slice fails clearly (surface
`get_executor`'s ValueError), build continues (other slices unaffected); absent/empty →
build default. Metered escalation without confirm → do not dispatch.

**Testing:**
- `slice.py` parses `executor:` (present / absent / with-model / malformed).
- `SliceTask` carries `executor`; defaults to None.
- `run_plan_parallel` builds per-slice executors: in one layer, assert slice T1 used executor X
  and T2 used executor Y (fake executor factory recording which ran which).
- unknown spec for a slice → that slice FAILED (not a crash); sibling slices still run.
- backward-compat: a plan with no `executor:` lines behaves exactly as today.

---

## Feature C — Unified usage view

### Ledger enrichment (foundational, lands here)
- `LedgerEntry` gains `model: str | None`, `token_usage: dict[str,int]`, `cost: float | None`,
  written on slice completion from the `token_usage` already in `deliver_slice`. (Cost is set
  where the provider reports it — OpenCode JSONL carries `part.cost`; Gemini is flat $0.)
- Backward-compat: old ledger files without these fields load with defaults.

### The view (`run_delivery.py --usage` + `cross-llm-delivery-usage` skill)
- Renders ONE markdown table combining:
  - **Per-build** (from the enriched ledger): per-slice model + tokens + cost, plus build totals.
  - **OpenCode account aggregate** (`opencode stats`, parsed): total cost + tokens.
  - **Gemini** (best-effort): labeled "flat-rate ($0 marginal)"; quota % if cleanly available,
    else omitted.
- On-demand snapshot; re-invoke to refresh. Markdown renders identically in CLI and VS Code
  (the extension already shows agent markdown — no separate VS Code build needed for v1).

**Data flow:** `deliver_slice` token_usage → ledger write → `--usage` reads ledger + shells
`opencode stats` + best-effort Gemini → markdown table.

**Error handling:** `opencode stats` fails/absent → ledger-only table + "OpenCode stats
unavailable" note (never crash). Gemini unqueryable → flat-rate label. Cost absent for a
provider → show tokens, blank cost. Old ledgers load fine.

**Testing:**
- `LedgerEntry` round-trips the new fields; OLD ledger JSON (without them) still loads.
- usage renderer: fake enriched ledger + fake `opencode stats` text → asserts the combined
  table (per-slice rows, build totals, account total).
- degraded: `opencode stats` missing → ledger-only + note; cost absent → tokens-only row.
- output is cp1252-encodable (the Windows-console rule).

---

## Cross-cutting

- Every subprocess uses `encoding="utf-8", errors="replace"` (learned repeatedly this project).
- All rendered text is cp1252-safe (ASCII markers; no glyphs that crash the Windows console).
- `opencode export` must always be called WITH a session id (no-id form blocks on a prompt).
- Keep the usage source list pluggable for a future codex/cursor executor.

## Build approach (per the project's dogfood method)

Three plans, each sliced TDD with builder tags (Claude for seams/SKILL.md/gates; Gemini or
OpenCode dogfood for pure-logic slices like the stats parser, the table renderer, the
`executor:` parser). Quick-wins-first sequencing: A → B → C. Ledger enrichment is C's first
slice but is the shared keystone.

## Boundaries (YAGNI)

- NOT a live-updating VS Code webview in v1 — markdown snapshot renders in both surfaces.
  Rich webview is a later feature only if the snapshot proves the need.
- NOT a token→$ price table for providers that don't report cost — show tokens where there's no
  cost, real $ where the provider gives it (OpenCode).
- NOT auto-spending: every metered escalation is user-confirmed.
- NOT changing the core protocol/judge/DAG — additions to slice.py, ledger.py, the orchestrator's
  per-slice resolution, run_delivery.py, and SKILL.md.
