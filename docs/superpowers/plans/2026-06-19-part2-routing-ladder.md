# Sub-plan 2 — Routing + escalation ladder

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md before stopping. **Read the MASTER plan's Global Constraints first** (`2026-06-19-complexity-routing-MASTER.md`). Builds on Sub-plan 1 (the `complexity` field + the `verified/likely/untested/revalidate` vocab already exist).

**Goal:** Route each slice to the cheapest *viable* cheap-tier model by its complexity, and escalate on failure along a single ladder: **quick → workhorse → orchestrator-handoff**. The expensive model is never an executor; a workhorse failure yields a `needs_repair` handoff (gate code 4) for the lead agent to fix — built in Sub-plan 3.

**Spec:** `2026-06-19-complexity-routing-and-slice-simplification-design.md` (Parts B, C).

**Architecture decision (important):** the **orchestrator stays catalog-agnostic.** All catalog/evidence/tier logic lives in `models.py` and is handed to the orchestrator as an injected `rung_planner(task) -> list[(rung_name, spec, budget)]` (mirroring the existing `executor_factory` injection). The orchestrator just *walks* the rungs. Wiring the real planner into the driver + the one-screen UI is **Sub-plan 3** — this sub-plan unit-tests the ladder with fake planners and the resolvers directly.

**Order:** T1 → T2 → T3 → T4 → T5 → T6.

**Builder routing:** T1, T4 = cheap (data/field). T2, T3 = DOGFOOD-eligible / standard (pure logic). T5, T6 = Claude/standard (structural).

---

## Task 1: `tier` field on the catalog  [cheap]

Add an executor-tier tag to each catalogued model. **`tier` is distinct from `capability_class`** — e.g. Cursor's Composer 2.5 is `capability_class="heavy"` but is a **workhorse-tier executor**; premium models (Opus/Sonnet) are NOT executor tiers at all (`tier=None` → the orchestrator's domain, never auto-routed).

**Files:**
- Modify: `src/cld/models.py` (`ModelInfo` + every `MODEL_METADATA` entry)
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `ModelInfo.tier: str | None` ∈ {`"quick"`, `"workhorse"`, `None`}; `TIERS = ("quick", "workhorse")`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_models.py`)

```python
def test_modelinfo_has_tier_and_values_are_valid():
    from cld.models import MODEL_METADATA, TIERS
    assert TIERS == ("quick", "workhorse")
    for info in MODEL_METADATA.values():
        assert info.tier in ("quick", "workhorse", None)


def test_catalog_tier_assignments():
    from cld.models import MODEL_METADATA as M
    assert M["gemini:gemini-3.1-pro-preview"].tier == "workhorse"
    assert M["opencode/deepseek-v4-flash-free"].tier == "quick"
    assert M["opencode/deepseek-v4-pro"].tier == "workhorse"
    assert M["opencode/gemini-3.1-pro"].tier == "workhorse"
    assert M["cursor:composer-2.5"].tier == "workhorse"      # heavy capability, workhorse ROLE
    # premium models are NOT executor tiers (orchestrator domain)
    assert M["opencode/claude-opus-4-8"].tier is None
    assert M["opencode/claude-sonnet-4-6"].tier is None
```

- [ ] **Step 2: Run red** — `python -m pytest tests/test_models.py -k "tier" -q -p no:warnings` → FAIL (no `tier`/`TIERS`).

- [ ] **Step 3: Implement**
  - Add `tier: str | None = None` to the `ModelInfo` dataclass (it is `@dataclass(frozen=True)`; a defaulted field is fine, place it after `last_validated` or anywhere after the required fields).
  - Add module constant near `KNOWN_PROVIDERS`: `TIERS = ("quick", "workhorse")`.
  - Set `tier=` on each `MODEL_METADATA` entry per the assignments above:
    - `gemini:gemini-3.1-pro-preview` → `"workhorse"`
    - `opencode/claude-opus-4-8` → `None`
    - `opencode/deepseek-v4-flash-free` → `"quick"`
    - `opencode/deepseek-v4-pro` → `"workhorse"`
    - `opencode/gemini-3.1-pro` → `"workhorse"`
    - `opencode/kimi-k2.6` → `"workhorse"`
    - `opencode/kimi-k2.7` → `"workhorse"`
    - `opencode/claude-sonnet-4-6` → `None`
    - `cursor:composer-2.5` → `"workhorse"`

- [ ] **Step 4: Green + full suite** — `python -m pytest tests/test_models.py -q -p no:warnings && python -m pytest -p no:warnings -q`.

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_models.py
git commit -m "feat(catalog): add executor tier (quick/workhorse/None) to ModelInfo + entries"
```

---

## Task 2: `resolve_tier_model` — cheapest viable model in a tier  [DOGFOOD-eligible]

A pure resolver: given a provider + tier, return the cheapest **viable** model id, applying the Sub-plan-1 trust rules.

**Files:** Modify `src/cld/models.py`; Test `tests/test_models.py`.

**Interfaces:**
- Produces: `resolve_tier_model(provider: str, tier: str, *, evidence: dict, available_ids: list[str]) -> str | None`.
  Returns a **spec string** (the same form `--executor` accepts: gemini ids as-is, opencode ids prefixed `opencode:`, cursor ids as-is). `None` when no model fits.

**Viability rules (from Sub-plan 1 Part B):**
- Effective status = `evidence.get(catalog_id, info.headless_status)`.
- **Skip** `revalidate` entirely.
- Prefer `verified`/`likely`; include `untested` **only if** no `verified`/`likely` exists in that (provider, tier) — the caller validates untested before trusting.
- Consider only catalog models whose `tier == tier` and `provider == provider` (use `_provider_of(id)`), AND that are in `available_ids` OR equal to `DEFAULT_WORKHORSE_ID` (the flat workhorse is always available — it runs via the Gemini CLI, not the opencode list).
- Among the chosen viability bucket, pick the **cheapest** by cost rank `{"free":0,"flat":0,"cheap-metered":1,"metered-unknown":2,"premium-metered":3}`, tie-broken by id (stable).

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_resolve_tier_model_picks_cheapest_viable():
    from cld.models import resolve_tier_model
    # opencode workhorse tier: deepseek-v4-pro + gemini-3.1-pro (both cheap-metered, likely),
    # kimi-k2.6 revalidate (skip). Cheapest-then-id => deepseek-v4-pro.
    spec = resolve_tier_model(
        "opencode", "workhorse",
        evidence={"opencode/kimi-k2.6": "revalidate"},
        available_ids=["opencode/deepseek-v4-pro", "opencode/gemini-3.1-pro", "opencode/kimi-k2.6"],
    )
    assert spec == "opencode:opencode/deepseek-v4-pro"


def test_resolve_tier_model_gemini_default_always_available():
    from cld.models import resolve_tier_model
    # provider gemini, workhorse: the flat workhorse resolves even with empty available_ids
    spec = resolve_tier_model("gemini", "workhorse", evidence={}, available_ids=[])
    assert spec == "gemini:gemini-3.1-pro-preview"


def test_resolve_tier_model_skips_revalidate_returns_none():
    from cld.models import resolve_tier_model
    spec = resolve_tier_model(
        "opencode", "quick",
        evidence={"opencode/deepseek-v4-flash-free": "revalidate"},
        available_ids=["opencode/deepseek-v4-flash-free"],
    )
    assert spec is None    # the only quick model is revalidate -> nothing viable


def test_resolve_tier_model_untested_only_when_nothing_better():
    from cld.models import resolve_tier_model
    # kimi-k2.7 is untested workhorse; with no verified/likely available it's returned
    spec = resolve_tier_model(
        "opencode", "workhorse", evidence={},
        available_ids=["opencode/kimi-k2.7"],
    )
    assert spec == "opencode:opencode/kimi-k2.7"
```

- [ ] **Step 2: Run red** — FAIL (no `resolve_tier_model`).

- [ ] **Step 3: Implement** in `models.py`. Reuse `_provider_of`, `MODEL_METADATA`, `DEFAULT_WORKHORSE_ID`, and `_spec_for`-style prefixing (opencode ids → `opencode:<id>`; ids already containing `:` returned as-is). Pseudostructure:
```python
_COST_RANK = {"free": 0, "flat": 0, "cheap-metered": 1, "metered-unknown": 2, "premium-metered": 3}

def _spec_of_catalog_id(cid: str) -> str:
    return f"opencode:{cid}" if cid.startswith("opencode/") else cid

def resolve_tier_model(provider, tier, *, evidence, available_ids) -> str | None:
    avail = set(available_ids) | {DEFAULT_WORKHORSE_ID}
    cands = []
    for cid, info in MODEL_METADATA.items():
        if info.tier != tier or _provider_of(cid) != provider:
            continue
        if cid not in avail:
            continue
        status = (evidence or {}).get(cid, info.headless_status)
        if status == "revalidate":
            continue
        cands.append((cid, info, status))
    if not cands:
        return None
    trusted = [c for c in cands if c[2] in ("verified", "likely")]
    pool = trusted or cands           # untested only if no trusted
    pool.sort(key=lambda c: (_COST_RANK.get(c[1].cost_class, 9), c[0]))
    return _spec_of_catalog_id(pool[0][0])
```

- [ ] **Step 4: Green + full suite.**

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_models.py
git commit -m "feat(routing): resolve_tier_model — cheapest viable model in a provider tier"
```

---

## Task 3: `COMPLEXITY_ROUTING` + `plan_rungs`  [standard]

Map complexity → entry rung + budget, and produce the ordered rung list a slice will climb.

**Files:** Modify `src/cld/models.py`; Test `tests/test_models.py`.

**Interfaces:**
- Produces:
  - `COMPLEXITY_ROUTING = {"easy": ("quick", 1), "standard": ("workhorse", 2), "complex": ("workhorse", 1)}`
  - `plan_rungs(task, *, provider, evidence, available_ids, max_retries=2) -> list[tuple[str, str, int]]`
    Each tuple is `(rung_name, spec, budget)`, cheap rungs only, in climb order. Rules:
    - A **tagged** slice (`task.executor`) pins it: a single rung `("workhorse", task.executor, max_retries)` (no auto-routing, no quick rung).
    - Untagged: entry tier from `COMPLEXITY_ROUTING[task.complexity]`. Climb chain: `easy` → `[quick, workhorse]`; `standard`/`complex` → `[workhorse]`. For each tier in the chain, `resolve_tier_model(...)`; include it only if non-None and not already added; budget = the complexity's budget for the entry tier, and `2` (standard budget) for any higher fallback tier.
    - If nothing resolves (no viable cheap model), return `[("workhorse", _fallback_spec, max_retries)]` where `_fallback_spec` = `DEFAULT_WORKHORSE_ID` for a gemini-ish provider else the provider's tier-less best guess — simplest: `DEFAULT_WORKHORSE_ID`. (Keeps the build moving; the workhorse default is always available.)

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_complexity_routing_table():
    from cld.models import COMPLEXITY_ROUTING
    assert COMPLEXITY_ROUTING["easy"] == ("quick", 1)
    assert COMPLEXITY_ROUTING["standard"] == ("workhorse", 2)
    assert COMPLEXITY_ROUTING["complex"] == ("workhorse", 1)


def _task(cid="S", complexity="standard", executor=None):
    from cld.executors.base import SliceTask
    return SliceTask(id=cid, brief="b", files=["x"], acceptance_test_path="t.py",
                     complexity=complexity, executor=executor)


def test_plan_rungs_easy_climbs_quick_then_workhorse():
    from cld.models import plan_rungs
    rungs = plan_rungs(_task(complexity="easy"), provider="opencode", evidence={},
                       available_ids=["opencode/deepseek-v4-flash-free", "opencode/deepseek-v4-pro"])
    assert [r[0] for r in rungs] == ["quick", "workhorse"]
    assert rungs[0][1] == "opencode:opencode/deepseek-v4-flash-free" and rungs[0][2] == 1
    assert rungs[1][1] == "opencode:opencode/deepseek-v4-pro" and rungs[1][2] == 2


def test_plan_rungs_standard_workhorse_only():
    from cld.models import plan_rungs
    rungs = plan_rungs(_task(complexity="standard"), provider="gemini", evidence={}, available_ids=[])
    assert [r[0] for r in rungs] == ["workhorse"]
    assert rungs[0][1] == "gemini:gemini-3.1-pro-preview" and rungs[0][2] == 2


def test_plan_rungs_complex_workhorse_budget_1():
    from cld.models import plan_rungs
    rungs = plan_rungs(_task(complexity="complex"), provider="gemini", evidence={}, available_ids=[])
    assert rungs == [("workhorse", "gemini:gemini-3.1-pro-preview", 1)]


def test_plan_rungs_tagged_slice_pins_single_rung():
    from cld.models import plan_rungs
    rungs = plan_rungs(_task(executor="opencode:opencode/claude-opus-4-8"),
                       provider="opencode", evidence={}, available_ids=[], max_retries=2)
    assert rungs == [("workhorse", "opencode:opencode/claude-opus-4-8", 2)]
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** `COMPLEXITY_ROUTING` + `plan_rungs` per the interface above (reuse `resolve_tier_model`). De-dupe specs across rungs; honor the tagged-pin rule.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_models.py
git commit -m "feat(routing): COMPLEXITY_ROUTING + plan_rungs (complexity -> ordered cheap rungs)"
```

---

## Task 4: Ledger fields for routing  [cheap]

Add the per-slice routing record. Backward-compatible (old ledgers load with defaults).

**Files:** Modify `src/cld/ledger.py`; Test `tests/test_ledger.py`.

**Interfaces:**
- `LedgerEntry` gains: `complexity: str | None = None`, `chosen_by: str | None = None` (`"rec"`/`"you"`), `final_rung: str | None = None` (`"quick"`/`"workhorse"`/`"orchestrator"`), `intervened: bool = False`. `Ledger.set` accepts each; `load`/`save` round-trip them.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_ledger.py`)

```python
def test_ledger_records_routing_fields(tmp_path):
    from cld.ledger import Ledger
    p = str(tmp_path / "l.json")
    led = Ledger(p)
    led.set("T1", status="done", model="opencode:opencode/deepseek-v4-pro",
            complexity="standard", chosen_by="rec", final_rung="workhorse", intervened=False)
    led.set("T2", status="done", final_rung="orchestrator", intervened=True)
    led.save()
    r = Ledger.load(p)
    a = r.get("T1"); b = r.get("T2")
    assert a.complexity == "standard" and a.chosen_by == "rec" and a.final_rung == "workhorse"
    assert a.intervened is False
    assert b.final_rung == "orchestrator" and b.intervened is True


def test_old_ledger_loads_with_routing_defaults(tmp_path):
    import json
    from cld.ledger import Ledger
    p = str(tmp_path / "o.json")
    with open(p, "w") as f:
        json.dump({"T1": {"status": "done", "attempts": 1}}, f)
    e = Ledger.load(p).get("T1")
    assert e.complexity is None and e.chosen_by is None and e.final_rung is None and e.intervened is False
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — mirror how `effort` is handled across the dataclass field, `load` (`.get`), `set` (apply-if-not-None; for `intervened` accept a bool and apply when not None), and `save` (serialize all four). Note `intervened` default is `False` (a bool, not None) — in `set`, apply it when the kwarg is not None.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add src/cld/ledger.py tests/test_ledger.py
git commit -m "feat(ledger): record complexity/chosen_by/final_rung/intervened (backward-compatible)"
```

---

## Task 5: The escalation ladder in the orchestrator  [Claude — structural]

Walk the rungs: try each cheap rung in order; first acceptance wins; if all cheap rungs fail, emit a **`needs_repair`** handoff (NOT `failed`). Keep the orchestrator catalog-agnostic via an injected `rung_planner`.

**Files:** Modify `src/cld/orchestrator.py`; Test `tests/test_orchestrator_parallel.py`.

**Interfaces:**
- Consumes: `plan_rungs`-shaped data via an injected callable.
- Produces:
  - `run_plan_parallel(..., rung_planner: Callable[[SliceTask], list[tuple[str,str,int]]] | None = None)`.
  - `PlanResult.needs_repair: list[str]` (new list, like `failed`/`deferred`).
  - `SliceDetail.status` may now be `"needs_repair"`.
  - On a slice handled by the ladder: ledger records `complexity=task.complexity`, `final_rung` = the rung that passed (`"quick"`/`"workhorse"`) or `"orchestrator"` when it ends `needs_repair`.

**Behavior:**
- If `rung_planner is None` → **current behavior unchanged** (single `_executor_for` dispatch with `max_retries`). All existing tests must still pass.
- If provided → for each slice, `rungs = rung_planner(task)`; for each `(rung_name, spec, budget)` in order: build executor via `executor_factory(spec)`, `deliver_slice(..., model=spec, max_retries=budget-1)` (budget = total attempts, so `max_retries = budget - 1`; budget 1 → 0 retries). First `accepted` → record DONE with `final_rung=rung_name`, stop. If a rung fails, climb to the next. If ALL rungs fail → status `needs_repair`, `final_rung="orchestrator"`, append to `result.needs_repair` (NOT `result.failed`). Worktree handling: keep the per-slice worktree collect step for the rung that passes (commit the accepted work); for a needs_repair slice, leave the worktree's last attempt in place is N/A (worktree is removed) — just record the handoff (the lead agent repairs in the real repo in Sub-plan 3).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_orchestrator_parallel.py`)

```python
def test_ladder_climbs_quick_to_workhorse(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    used = []
    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, task, workdir, feedback=None):
            used.append(self.spec)
            ok = self.spec == "wh"           # quick fails, workhorse passes
            return ExecutorResult(ok=ok, diff="", files_changed=["x"], raw_log="")

    def judge(**kw):
        passed = kw["run_tests"]() == "ok"
        return type("J", (), {"passed": passed, "failing_tests": []})()
    def tr(workdir, path=None):
        return "ok" if used and used[-1] == "wh" else "no"

    planner = lambda task: [("quick", "qk", 1), ("workhorse", "wh", 2)]
    p = str(tmp_path / "l.json"); ledger = Ledger(p)
    res = run_plan_parallel(
        [SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py", complexity="easy")],
        ledger, executor_factory=lambda spec: _Rec(spec), default_spec="gemini",
        rung_planner=planner, judge_fn=judge, test_runner=tr)
    assert used == ["qk", "wh"]                 # climbed
    assert "S" in res.completed
    assert ledger.get("S").final_rung == "workhorse"
    assert ledger.get("S").complexity == "easy"


def test_ladder_all_cheap_fail_yields_needs_repair(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult
    class _Fail:
        def __init__(self, spec): pass
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=["x"], raw_log="")
    judge = lambda **kw: type("J", (), {"passed": False, "failing_tests": ["t::x"]})()
    planner = lambda task: [("workhorse", "wh", 1)]
    p = str(tmp_path / "l.json"); ledger = Ledger(p)
    res = run_plan_parallel(
        [SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py", complexity="complex")],
        ledger, executor_factory=lambda s: _Fail(s), default_spec="gemini",
        rung_planner=planner, judge_fn=judge, test_runner=lambda *a, **k: "no")
    assert "S" in res.needs_repair and "S" not in res.failed and "S" not in res.completed
    assert ledger.get("S").status == "needs_repair"
    assert ledger.get("S").final_rung == "orchestrator"


def test_no_rung_planner_is_current_behavior(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult
    seen = []
    class _Ok:
        def __init__(self, spec): seen.append(spec)
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")
    res = run_plan_parallel(
        [SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py")],
        Ledger(str(tmp_path / "l.json")),
        executor_factory=lambda s: _Ok(s), default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed")
    assert seen == ["gemini"] and "S" in res.completed   # unchanged single-dispatch path
```

- [ ] **Step 2: Run red** — FAIL (`rung_planner` kwarg / `needs_repair` missing).

- [ ] **Step 3: Implement**
  - Add `needs_repair: list[str] = field(default_factory=list)` to `PlanResult`.
  - Add `rung_planner: Callable | None = None` (keyword-only) to `run_plan_parallel`.
  - Refactor `_run_one(task)`: if `rung_planner is None`, keep the existing body exactly. Else:
    ```python
        rungs = rung_planner(task) or [("workhorse", _resolve_spec(task), max_retries)]
        last = None
        for rung_name, spec, budget in rungs:
            ex = executor_factory(spec) if executor_factory is not None else executor
            if repo_dir is not None and git_runner is not None:
                with worktree(repo_dir, f"slice-{task.id}", runner=git_runner) as wt:
                    res = deliver_slice(task, executor=ex, judge_fn=judge_fn,
                                        max_retries=max(budget - 1, 0), workdir=wt,
                                        test_runner=test_runner, model=spec)
                    if res.accepted:
                        git_runner(["git", "add", "-A"], wt)
                        git_runner(["git", "commit", "-m", f"slice {task.id}: accepted by cld"], wt)
            else:
                res = deliver_slice(task, executor=ex, judge_fn=judge_fn,
                                    max_retries=max(budget - 1, 0), test_runner=test_runner, model=spec)
            last = res
            if res.accepted:
                res.final_rung = rung_name          # see note
                return res
        # all cheap rungs failed -> handoff
        last.final_rung = "orchestrator"
        last.needs_repair = True
        return last
    ```
    Add `final_rung: str | None = None` and `needs_repair: bool = False` fields to `DeliverResult` to carry these out of `_run_one`.
  - In `_process`, after `_run_one`, branch on `deliver_res.needs_repair`: record ledger `status="needs_repair"`, `complexity=task.complexity`, `final_rung="orchestrator"`, append to `result.needs_repair`, `SliceDetail(status="needs_repair", failing_tests=...)`. On accepted: also write `complexity=task.complexity`, `final_rung=deliver_res.final_rung`. On a plain failed (only possible in the no-planner path or an executor exception) keep existing behavior.

- [ ] **Step 4: Green + full suite** — `python -m pytest tests/test_orchestrator_parallel.py -q -p no:warnings && python -m pytest -p no:warnings -q`. Existing no-planner tests must stay green.

- [ ] **Step 5: Commit**
```bash
git add src/cld/orchestrator.py tests/test_orchestrator_parallel.py
git commit -m "feat(orchestrator): escalation ladder (quick->workhorse->needs_repair handoff) via injected rung_planner"
```

---

## Task 6: `needs_repair` gate code 4 in the summary + `--step`  [Claude]

Surface the handoff: a layer with any `needs_repair` slice exits `--step` with code **4** so the lead agent knows to intervene (the repair loop itself is Sub-plan 3).

**Files:** Modify `src/cld/summary.py`, `skill/scripts/run_delivery.py`; Test `tests/test_summary.py` (or wherever summary is tested), `tests/test_run_delivery.py`.

**Interfaces:**
- `classify_gate(result, *, more_layers)` returns **4** when `result.needs_repair` is non-empty (checked BEFORE the `failed`/`deferred` → 2 branch). Otherwise unchanged (0/2/3).
- `summarize_layer` lists `needs_repair` slices distinctly (e.g. `! NEEDS REPAIR`), and the GATE line notes them.

- [ ] **Step 1: Write the failing tests**

`tests/test_summary.py` (append; mirror existing style — a tiny stand-in result object):
```python
def test_classify_gate_needs_repair_is_4():
    from cld.summary import classify_gate
    class _R:
        completed=["A"]; failed=[]; deferred=[]; needs_repair=["B"]
    assert classify_gate(_R(), more_layers=True) == 4
    assert classify_gate(_R(), more_layers=False) == 4


def test_classify_gate_unchanged_without_needs_repair():
    from cld.summary import classify_gate
    class _Ok:
        completed=["A"]; failed=[]; deferred=[]; needs_repair=[]
    class _Fail:
        completed=[]; failed=["A"]; deferred=[]; needs_repair=[]
    assert classify_gate(_Ok(), more_layers=True) == 0
    assert classify_gate(_Ok(), more_layers=False) == 3
    assert classify_gate(_Fail(), more_layers=True) == 2
```

`tests/test_run_delivery.py` (append): assert the `--step` help/behavior documents gate 4 — minimally, assert `run_delivery` imports/uses `classify_gate` and that the `--step` branch returns its value (a light test: call `main(["--help"])` raises SystemExit; OR assert the gate-code docstring/comment mentions 4). Keep it simple and non-flaky.

- [ ] **Step 2: Run red.**

- [ ] **Step 3: Implement**
  - `summary.classify_gate`: add, as the FIRST check, `if getattr(result, "needs_repair", []): return 4`.
  - `summary.summarize_layer`: count + list `needs_repair` slices (use `getattr(result, "needs_repair", [])` and the per-slice detail status `"needs_repair"`), render a distinct line (ASCII-safe, e.g. `! NEEDS REPAIR  <first failing test>`), and add to the GATE line (e.g. `GATE: N passed, M failed, K need repair.`).
  - `run_delivery.py`: the `--step` branch already `return classify_gate(...)`; update its help text / the `--step` argument help to document exit code **4** = "a slice needs orchestrator repair (lead agent intervenes)". No behavioral wiring of the repair loop here (Sub-plan 3).

- [ ] **Step 4: Green + full suite + global sync** (run_delivery.py changed):
```bash
cp skill/scripts/run_delivery.py ~/.claude/skills/cross-llm-delivery/scripts/run_delivery.py
diff -q skill/scripts/run_delivery.py ~/.claude/skills/cross-llm-delivery/scripts/run_delivery.py
python -m pytest -p no:warnings -q
```

- [ ] **Step 5: Commit**
```bash
git add src/cld/summary.py skill/scripts/run_delivery.py tests/test_summary.py tests/test_run_delivery.py
git commit -m "feat(summary): gate code 4 for needs_repair handoff + --step doc"
```

---

## Done criteria (Sub-plan 2)
- Catalog carries `tier`; `resolve_tier_model` returns the cheapest viable model per provider/tier (trust-aware: skips `revalidate`, untested-only-when-nothing-better, gemini default always available).
- `COMPLEXITY_ROUTING` + `plan_rungs` produce the ordered cheap rungs (easy: quick→workhorse; standard: workhorse/2; complex: workhorse/1; tagged: single pinned rung).
- The orchestrator walks the rungs via an injected `rung_planner`, climbs quick→workhorse, and emits `needs_repair` (final_rung="orchestrator") when all cheap rungs fail; `rung_planner=None` preserves current behavior exactly.
- Ledger records complexity/chosen_by/final_rung/intervened; old ledgers load.
- `--step` returns gate code 4 on a needs_repair handoff; summary surfaces it.
- Full suite green. Update STATUS.md: Sub-plan 2 done → Next = Sub-plan 3.
- **Not in this sub-plan:** the driver building a real `rung_planner` from catalog+evidence, the one-screen approval UI, and the lead-agent repair loop — all Sub-plan 3.
