# Complexity-Based Model Routing + Slice Simplification — Design

**Date:** 2026-06-19
**Status:** Design approved in brainstorming; pending written-spec review.
**Scope:** This is **spec #1** of two. It changes the *engine* (slice model + model routing).
The **C1 per-provider skill split** is **spec #2** (the follow-on), captured at the end here but
designed separately.

---

## Goal

Make "which model builds which slice" a first-class, cost-saving, trust-aware framework — and
simplify the slice model at the same time. The lead agent (a top-tier model, e.g. Opus) assesses
each slice's complexity while planning, routes the *building* to cheap headless executors, and the
expensive model only ever acts as **orchestrator** — architect, judge, and **surgical repairer** of
the hard remainder the cheap models can't finish. This extends the engine's founding thesis ("cheap
executor types, expensive model architects + judges") with **"+ repairs."**

## Why now (motivation)

A recent build surfaced that the slice machinery had accreted complexity (sub-slices, a forced
per-slice picker) for a "mix models within one build" use case that is, in practice, **rare** (users
overwhelmingly run one provider per build). Meanwhile the genuinely valuable lever — *choosing a
cost-appropriate model per slice* — had only raw ingredients (a capability/cost catalog, per-slice
tags) and no framework to drive it. This spec removes the unused complexity and builds the lever.

---

## Part A — Simplified slice model

A plan is a **flat list of slices**. Each slice =
`id` · `brief` · `files` · `acceptance_test_path` · `deps` · *optional* `complexity` · *optional*
`executor`/`@effort` (a manual pin).

- **`deps` are the only structure.** Numbering (`1`, `3.1`, `3(a)`) is a human label with no engine
  meaning; "3.1 after 3" is expressed as a dep edge, not nesting.
- **Sub-slices are removed.** `## SUBSLICE:` parsing, the orchestrator child-execution path, ledger
  `parent/child` keys, and usage nesting are deleted. Their only purpose (split one slice across
  models) is served better by routing on a flat list, and the use case is rare.
- **The old forced per-slice picker is removed** (`--per-slice-pick`, `slice_pick_fn`). Its *concept*
  returns, opt-in and recommendation-driven, as run-mode 3 in Part D.

Net: the engine drops to a flat, dependency-ordered list of independently-routable slices.

---

## Part B — Trust-aware routing (only viable models are picked)

A tier resolves to the **cheapest *trustworthy* model in that tier**, never just the cheapest.
"Trustworthy" = the catalog's per-model `headless_status`, overlaid by the durable `EvidenceStore`.

### Status vocabulary (neutral, factual — no quality claims about any vendor's model)

The stored/displayed status is one of four. All language is scoped to *our* test in *our* harness:

- **`verified`** — passed our validation gate, or durable evidence on record. Route freely.
- **`likely`** — known-compatible by a strong prior (model families we're confident in, e.g.
  lower-end Google/Claude), catalogued by us. **Routed without forcing validation**, shown with a
  soft note. (This is what distinguishes it from `untested`: trusted-by-prior, skip the ceremony.)
- **`untested`** — no basis either way. Validate-on-demand (or a warning/confirm) before a real slice.
- **`revalidate`** — our last validation did not succeed; re-check (run "validate") before use.

`verified` ≈ `likely` (trusted → route) → `untested` (validate/confirm first) → `revalidate`
(blocked until re-checked). **"known-bad"/"proven" language is removed** (legal/tone). Migration:
existing evidence files auto-migrate `known-bad`→`revalidate`, `proven`→`verified` on load
(one-time, lossless).

### The no-false-blacklist rule

- **Durable `revalidate` verdicts come only from the dedicated trivial-slice validation gate**
  (`validate_model`'s known-answer `add(a,b)` test), never from a real-slice judge failure — a real
  slice can fail because it's *hard*, not because the model is bad.
- A real-slice failure **escalates that slice** (Part C) but **never** marks the model `revalidate`.

---

## Part C — Complexity → routing, and the escalation ladder

### Complexity assessment (3 levels)

The lead agent tags each slice while planning, against the rubric (Part E):

- **`easy`** — boilerplate / one well-specified function, known pattern, no tricky logic or I/O.
- **`standard`** — a typical module: real logic, a few pieces integrated. **Default when unsure.**
- **`complex`** — subtle algorithm, concurrency, gnarly edge cases, ambiguous spec, high rework
  risk. A **signal**: expect orchestrator repair.

### The escalation ladder (one ladder; complexity sets the entry rung)

- **Rung 1 — quick** (cheapest fast model, e.g. gemma / a flash)
- **Rung 2 — workhorse** (each provider's best cheap model: gemini-3.1-pro, Composer 2.5, …)
- **Rung 3 — orchestrator** (the lead agent — surgical repair; see Part D)

| Complexity | Starts on | Retry budget before next rung | Path |
|---|---|---|---|
| `easy` | quick | 1 attempt on quick | quick → workhorse (standard budget) → orchestrator |
| `standard` | workhorse | 2 attempts on workhorse | workhorse → orchestrator |
| `complex` | workhorse | 1 attempt on workhorse | workhorse → orchestrator (sooner) |

(Retry budgets are defaults, configurable; `2` matches today's `max_retries`.) The
**orchestrator only ever intervenes off a *workhorse* failure.** Heavy/premium models are
**never executors** — the expensive pool is spent only on the hard remainder, and only on the
failing delta. Tier→model resolution always runs through the Part B trust filter.

---

## Part D — Control flow (one screen, then it runs)

After the lead agent slices + assesses **all** slices, it presents **one routing-plan screen**:

```
Build plan — provider: <provider>   (N slices)
  S1  plan parser        easy      → gemma             [rec]
  S2  ledger schema      standard  → gemini-3.1-pro    [rec]
  S7  tricky merge       complex   → gemini-3.1-pro    ! expect orchestrator repair
  ...
How should I run it?
  1) Approve & run — ask me before any orchestrator (Opus) repair     [default]
  2) Approve & run — fully autonomous (auto-repair, no stops)
  3) Review at each slice (stop before every slice)
  4) Adjust a slice's model first
```

- **Cheap routing + cheap escalation (quick→workhorse) are always automatic** and free — never
  prompted.
- **The only gated decision is orchestrator repair** (the expensive pool):
  - **1 / advise (default):** the engine pauses and asks before the lead agent repairs.
  - **2 / autonomous (opt-in):** the lead agent repairs and reports after (pre-authorised).
  - The chosen mode is recorded with the run and persists across `--step` resumes.
- **3 / review each slice:** the reincarnated (opt-in) per-slice review, for adapting as results
  come in. Not the default.
- **4 / adjust first:** an *edit action*, not a run-mode. Override a slice's recommended model (or
  complexity) — which **pins** that slice via its `executor:` tag (`[you]` vs `[rec]`) — then return
  to choose 1/2/3.
- **Upfront opt-in for unattended runs:** `--autonomous` (or telling the lead agent "fix things
  yourself") selects mode 2 without the screen blocking.
- **Manual pins always available**, independent of the mode (the auto-router honours an `executor:`
  tag and leaves that slice alone).

### The orchestrator "repair" is a HANDOFF, not a dispatch

The headless engine (a Python process) cannot summon Opus. The **orchestrator is the lead Claude
agent running the skill.** When a workhorse slice exhausts its retries, the engine **stops and
signals** "slice X needs orchestrator repair" (a new `--step` gate code). The **lead agent** then
makes the surgical fix on the failing files (targeted by the judge's signal — which tests failed,
which files), commits, and re-invokes to continue. This is the economical use of the expensive
model: it engages only for the rare hard remainder, never to babysit the build.

---

## Part E — Guidance (the rubric) + reproducibility recording

### Complexity rubric (in `authoring-plans.md`, so assessment is consistent)

- `easy`: pure boilerplate, one function, known pattern, no tricky logic/IO/concurrency.
- `standard`: typical module, real logic, 2–3 pieces integrated, normal test surface. Default.
- `complex`: subtle algorithm / concurrency / gnarly edges / ambiguous spec / high rework risk —
  "even a good cheap model would likely struggle."
- **Never downgrade to save money when unsure** — that just causes escalations later. Default to
  `standard`.

### Recorded per slice (reproducibility + cost transparency)

The ledger records, per slice: assessed `complexity`, who chose the model (`rec`/`you`), the model
used, the **final rung** it succeeded on (quick / workhorse / orchestrator), and whether the
orchestrator intervened. `--usage` shows **complexity → model → final rung**, so it is visible where
the cheap pool sufficed and where the expensive pool was spent.

### Per-provider usage reporting (no bundling)

The per-build ledger table stays in the shared engine (naturally single-provider). The
**account-level block** (today's bundled OpenCode + Cursor stats) is refactored into **modular
per-provider account reporters**, rendered only for the provider in play. (In spec #2 each reporter
moves into its provider's source dir, so each self-contained skill reports only its own usage.)

---

## Part F — Concrete engine changes + removals

- **`executors/base.py` `SliceTask`:** add `complexity` (easy/standard/complex, default standard);
  **remove `subslices` + `parent_id`.**
- **`plan/slice.py`:** parse optional `complexity:`; **remove `## SUBSLICE:` parse + round-trip.**
- **`models.py` catalog:** tag each model with its tier (`quick`/`workhorse`) per provider; add a
  trust-filtered tier→model resolver; "heavy" is no longer an executor tier (it is the orchestrator).
- **`orchestrator.py`:** **remove `_run_subslices` and `slice_pick_fn`;** add the escalation ladder
  (quick→workhorse→orchestrator-handoff) with complexity-driven entry rung + retry budget; emit the
  new "needs orchestrator repair" `--step` gate; record complexity/rung/intervention.
- **`validate.py` / `evidence.py`:** rename status vocab → `verified`/`likely`/`untested`/
  `revalidate`; migrate stored `known-bad`→`revalidate`, `proven`→`verified` on load; update all
  user-facing messages.
- **`run_delivery.py`:** the one-screen plan-approval + run-mode selection (1/2/3/4); **remove
  `--per-slice-pick`;** add `--autonomous`.
- **`usage.py`:** add complexity/rung columns; split account reporting into per-provider reporters;
  **remove sub-slice nesting.**
- **Tests:** delete sub-slice + per-slice-pick suites; add complexity-routing, escalation-ladder,
  status-rename + evidence-migration, and per-provider-usage tests.

---

## Out of scope (this spec)

- **The C1 per-provider skill split** — that is **spec #2** (below).
- Adding new providers/executors.
- Any change to the deterministic judge / DAG / worktree isolation beyond what the ladder needs.

---

## Follow-on — spec #2: C1 per-provider skill split (captured, designed separately)

Decided in this brainstorm, to be specced + built **after** spec #1 (simplify the engine, then
package the simpler engine):

- **C1 = single-source engine, generated self-contained skills.** The engine + shared orchestration
  prose live **once** in the root repo. A **generator/build step** stamps out each self-contained
  `cross-llm-<provider>` skill = shared engine (copied verbatim, never hand-edited in output) +
  that provider's source dir (`providers/<x>/`: adapter, quirks, provider-scoped picker, SKILL.md
  fragment, setup notes, **its own usage reporter**).
- **Engine behaviour stays uniform** across providers (single source); **quirks stay provider-local**
  (the cursor long-prompt issue, opencode `.cmd`→`.exe`, gemini invocation form, etc.).
- **Distribution:** users download at root level (everything) or per-provider level (just the one
  they use). The root is the umbrella repo/engine + an index, not itself a "pick any provider" skill.
- **Per-provider picker** is scoped to that provider's own models (dynamic from its CLI), so the
  big cross-provider drill-down in today's `models.py` largely evaporates per skill.
