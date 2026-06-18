# Complexity-Based Model Routing + Slice Simplification — MASTER Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement each sub-plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Turn "which model builds which slice" into a first-class, cost-saving, trust-aware framework, and simplify the slice model — per spec `docs/superpowers/specs/2026-06-19-complexity-routing-and-slice-simplification-design.md` (spec #1).

**Architecture:** The lead agent assesses each slice's complexity while planning and routes *building* to cheap headless executors on an escalation ladder (quick → workhorse → orchestrator). The expensive model is never an executor — it only intervenes, as a handoff back to the lead agent, to surgically repair the hard remainder the cheap models can't finish.

**Tech Stack:** Python 3.11+ stdlib only; pytest fakes; no new runtime deps.

## Global Constraints

(Every task implicitly includes these — copied from the spec + repo conventions.)

- **Python 3.11+, standard library only.** No new runtime dependencies.
- **Trunk-based:** work on `master`, commit per task. Do NOT create branches.
- **Test command:** `python -m pytest <args> -q -p no:warnings`. A repo teardown plugin can swallow the summary line — confirm via dot count / exit 0 when needed.
- **Windows discipline:** any subprocess uses `encoding="utf-8", errors="replace"`.
- **Output is cp1252-safe** where it's *new* output (no fancy glyphs in code we add). (Existing files may already contain glyphs; don't introduce more.)
- **Status vocabulary is exactly** `verified` / `likely` / `untested` / `revalidate`. **Never** use "known-bad", "proven", "bad", or any quality claim about a named vendor model. All status language is scoped to *our* validation in *our* harness.
- **Complexity vocabulary is exactly** `easy` / `standard` / `complex`. Default `standard`.
- **The expensive model is never an executor.** Routing only ever selects cheap tiers (`quick`, `workhorse`); the `orchestrator` rung is a handoff to the lead agent, not a model dispatch.
- **No false blacklisting:** a real-slice judge failure never writes a durable `revalidate` verdict; only the dedicated trivial-slice gate (`validate_model`) does.
- After any task that changes `skill/SKILL.md`, `skill/scripts/run_delivery.py`, or `skill/references/*`, **sync the global copy** at `~/.claude/skills/cross-llm-delivery/...` and verify with `diff -q`.

---

## Sub-plans (build in order)

Each sub-plan ships a working, tested engine on its own.

### Sub-plan 1 — Foundation (`2026-06-19-part1-simplify-and-rename.md`)
Subtractive + rename + data-field. Leaves a simpler, green engine with the new vocab and the
`complexity` field parsed but not yet driving routing.
- **T1** — Status rename in the catalog + `recommend`/`browse_models` (`models.py`): `proven`→`verified`, `known-bad`→`revalidate`; `likely`/`untested` unchanged. Behavior identical.
- **T2** — Status rename + auto-migration in `evidence.py` + `validate.py` (incl. `resolve_and_validate`/`ValidationResult`): stored `proven`→`verified`, `known-bad`→`revalidate` migrated losslessly on load; all messages updated.
- **T3** — Remove sub-slices: `SliceTask.subslices`/`parent_id`, `## SUBSLICE:` parse + round-trip, orchestrator `_run_subslices`, usage nesting; delete their tests.
- **T4** — Remove old per-slice-pick: `slice_pick_fn` (orchestrator) + `make_slice_pick_fn`/`--per-slice-pick` (run_delivery); delete their tests.
- **T5** — Add `SliceTask.complexity` (`easy`/`standard`/`complex`, default `standard`) + parse optional `complexity:` in `slice.py` + round-trip. Data only; nothing routes on it yet.

### Sub-plan 2 — Routing + escalation ladder (`2026-06-19-part2-routing-ladder.md`)
The behavioral core.
- **T1** — Catalog tier tags: add `tier` (`quick`/`workhorse`) to `ModelInfo`/catalog entries.
- **T2** — `resolve_tier_model(provider, tier, *, evidence, available_ids) -> str | None`: cheapest **viable** (`verified`/`likely`, evidence-overlaid) model in a provider's tier; `untested` only if nothing better (caller validates); skip `revalidate`/unavailable.
- **T3** — Complexity → entry rung map + retry budgets (`easy`→quick/1, `standard`→workhorse/2, `complex`→workhorse/1).
- **T4** — Escalation ladder in `deliver_slice`/orchestrator: on budget exhaustion climb quick→workhorse; a workhorse exhaustion yields a new `needs_repair` outcome (NOT `failed`).
- **T5** — New `needs_repair` slice status + gate code `4` in `summary.classify_gate`/`summarize_layer`; `--step` returns 4 when any slice needs orchestrator repair.
- **T6** — Record per slice in the ledger: `complexity`, `chosen_by` (`rec`/`you`), `model`, `final_rung` (`quick`/`workhorse`/`orchestrator`), `intervened` (bool).

### Sub-plan 3 — Control surface + usage (`2026-06-19-part3-control-and-usage.md`)
The UX + guidance + reporting.
- **T1** — One-screen routing-plan render (`models.py`): given slices (with complexity) + provider catalog + evidence, produce the plan table (per-slice rec model, `[rec]`/`[you]`, `!` complex flag).
- **T2** — Run-mode selection in `run_delivery.py`: modes 1 advise / 2 autonomous / 3 review-each / 4 adjust; `--autonomous` upfront; persist the chosen mode in the ledger/run-config; resumes keep it.
- **T3** — The orchestrator-repair handoff loop in `SKILL.md`: how the lead agent reacts to gate code 4 (surgical fix on the failing files, commit, re-invoke), advise vs autonomous behavior. Global sync.
- **T4** — Per-provider usage reporters: split the bundled account block in `usage.py` into modular per-provider reporters rendered only for providers in play; add `complexity`/`final_rung` columns to the ledger table; remove sub-slice nesting.
- **T5** — Complexity rubric in `skill/references/authoring-plans.md` (easy/standard/complex signals; default-to-standard rule). Global sync.

---

## Shared interfaces (names + types used across sub-plans)

Later tasks rely on these exact names; define them as specified.

```python
# cld/executors/base.py
@dataclass
class SliceTask:
    id: str
    brief: str
    files: list[str]
    acceptance_test_path: str
    deps: list[str] = field(default_factory=list)
    executor: str | None = None
    complexity: str = "standard"      # NEW: "easy" | "standard" | "complex"
    # REMOVED: parent_id, subslices

# cld/models.py
TIERS = ("quick", "workhorse")        # executor tiers; "heavy" is the orchestrator, not a tier
def resolve_tier_model(provider: str, tier: str, *, evidence: dict, available_ids: list[str]) -> str | None: ...
def render_routing_plan(slices, *, provider, catalog_for, evidence) -> str: ...

# complexity -> (entry_tier, retry_budget)
COMPLEXITY_ROUTING = {
    "easy":     ("quick",     1),
    "standard": ("workhorse", 2),
    "complex":  ("workhorse", 1),
}

# ledger entry gains: complexity:str|None, chosen_by:str|None, final_rung:str|None, intervened:bool=False
# slice status set gains: "needs_repair"
# summary.classify_gate gate codes: 0 layer all-passed | 2 failed/deferred | 3 build complete | 4 needs orchestrator repair
```

**Status vocab** (all sub-plans): `verified` / `likely` / `untested` / `revalidate`.
**Evidence migration** (T1/T2 of sub-plan 1): on load, map legacy `proven`→`verified`, `known-bad`→`revalidate`.

---

## Build order + caveats

- **Sub-plan 1 → 2 → 3**, strictly. Sub-plan 2's ladder needs sub-plan 1's `complexity` field + renamed statuses; sub-plan 3's UI needs sub-plan 2's resolver + recording.
- **Within sub-plan 1:** do **T1 + T2 (rename) before** anything else so the new vocab is in place; T3/T4 (removals) and T5 (complexity field) are independent of each other.
- **One sitting per sub-plan** (recorded execution preference); pause + update `STATUS.md` between sub-plans.
- Dogfood candidates (pure-logic, fully test-pinnable) — flagged per task in each sub-plan; behavior-critical/structural tasks (ladder, handoff, run-modes) are Claude-authored.
- **This is spec #1.** The C1 per-provider split is spec #2 — do NOT start it here.
