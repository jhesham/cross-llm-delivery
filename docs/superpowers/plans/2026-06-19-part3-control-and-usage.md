# Sub-plan 3 — Control surface + usage (final of spec #1)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md before stopping. **Read the MASTER plan's Global Constraints first** (`2026-06-19-complexity-routing-MASTER.md`). Builds on Sub-plans 1 + 2 (the `complexity` field, the trust vocab, `resolve_tier_model`/`plan_rungs`, the orchestrator `rung_planner` ladder + `needs_repair`/gate-4 all exist).

**Goal:** Make the routing framework *usable*: wire the real `rung_planner` into the driver so the ladder actually runs, render the one-screen routing plan, support the gate-4 repair handoff, show per-provider usage with complexity/rung columns, and document the lead-agent control flow (run-modes + repair loop) in the skill.

**Spec:** `2026-06-19-complexity-routing-and-slice-simplification-design.md` (Parts D, E).

**Design note (a deliberate spec realization):** Part D's run-modes (1 advise / 2 autonomous / 3 review-each / 4 adjust) and the one-screen approval are **lead-agent behaviors**, not engine code — because the orchestrator-repair is a HANDOFF to the lead agent (gate 4), and `run_delivery.py` runs non-interactively under the agent's Bash tool. So the modes live in SKILL.md (T5). The spec's "`--autonomous` flag" is realized as a SKILL.md mode the user signals in chat, **not** a CLI flag (a CLI flag would be a no-op — the engine always exits at gate 4; whether to ask-before-repair is the lead agent's behavior). The CODE in this sub-plan: the plan renderer (T1), the real `rung_planner` wiring (T2), the `--mark-repaired` handoff hook (T3), and per-provider usage (T4).

**Order:** T1 → T2 → T3 → T4 → T5.

**Builder routing:** T1 = DOGFOOD-eligible/standard (pure render). T2, T3 = Claude/standard (driver wiring). T4 = standard. T5 = Claude (prose + global sync).

---

## Task 1: `render_routing_plan` — the one-screen plan table  [standard]

A pure renderer: given the slices + the build provider + evidence + available ids, show each slice's complexity and its **recommended** model (its entry rung), marked `[rec]` (or `[you]` when pinned by a tag), with a `!` flag on `complex` slices.

**Files:** Modify `src/cld/models.py`; Test `tests/test_models.py`.

**Interfaces:**
- Produces: `render_routing_plan(slices, *, provider, evidence, available_ids) -> str`. ASCII/cp1252-safe.
  Uses `plan_rungs` for each slice; the recommended model = the FIRST rung's spec.

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_render_routing_plan_basics():
    from cld.models import render_routing_plan
    from cld.executors.base import SliceTask
    slices = [
        SliceTask(id="S1", brief="b", files=["a"], acceptance_test_path="t.py", complexity="easy"),
        SliceTask(id="S2", brief="b", files=["b"], acceptance_test_path="t.py", complexity="complex"),
        SliceTask(id="S3", brief="b", files=["c"], acceptance_test_path="t.py",
                  executor="opencode:opencode/claude-opus-4-8"),   # pinned
    ]
    out = render_routing_plan(slices, provider="gemini", evidence={}, available_ids=[])
    assert "S1" in out and "S2" in out and "S3" in out
    # easy/standard slices recommend the workhorse for the build provider (gemini default)
    assert "gemini:gemini-3.1-pro-preview" in out
    # complex slice flagged
    assert "!" in out
    # pinned slice shows its tag + [you]; auto-routed show [rec]
    assert "opencode:opencode/claude-opus-4-8" in out
    assert "[you]" in out and "[rec]" in out
    out.encode("cp1252")   # safe


def test_render_routing_plan_shows_complexity():
    from cld.models import render_routing_plan
    from cld.executors.base import SliceTask
    out = render_routing_plan(
        [SliceTask(id="S1", brief="b", files=["a"], acceptance_test_path="t.py", complexity="easy")],
        provider="gemini", evidence={}, available_ids=[])
    assert "easy" in out
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** `render_routing_plan` in `models.py`. For each slice: `rungs = plan_rungs(slice, provider=provider, evidence=evidence, available_ids=available_ids)`; `rec = rungs[0][1]` (spec); `mark = "[you]" if slice.executor else "[rec]"`; `flag = " !" if slice.complexity == "complex" else ""`. Render a header line + one aligned row per slice, e.g. `f"  {sid:6} {complexity:9} -> {rec:42} {mark}{flag}"`. ASCII only. Return the joined string.
- [ ] **Step 4: Green + full suite.**
- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_models.py
git commit -m "feat(routing): render_routing_plan — one-screen per-slice plan table"
```

---

## Task 2: Wire the real `rung_planner` into the driver  [Claude — the keystone]

Build a `rung_planner` from catalog + evidence + available-ids + the build provider, and pass it into BOTH `run_plan_parallel` call sites so the SP2 ladder actually runs in real builds.

**Files:** Modify `skill/scripts/run_delivery.py`; Test `tests/test_run_delivery.py`.

**Interfaces:**
- Produces: `build_rung_planner(default_spec: str, *, evidence: dict | None = None, max_retries: int = 2) -> Callable[[SliceTask], list[tuple[str,str,int]]]`.
- Helpers: `_provider_of_spec(spec) -> str` (executor name from a spec: `"gemini"`/`"gemini:x"`→`gemini`; `"opencode:..."`→`opencode`; `"cursor:..."`→`cursor`; unknown→`gemini`), and `_available_ids_for(provider) -> list[str]` (opencode→`list_models(_default_runner)`; cursor→ids from `list_cursor_models`; else `[]`; guard all exceptions → `[]`).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_run_delivery.py`)

```python
def test_provider_of_spec():
    import skill.scripts.run_delivery as rd
    assert rd._provider_of_spec("gemini") == "gemini"
    assert rd._provider_of_spec("gemini:gemini-3.1-pro-preview") == "gemini"
    assert rd._provider_of_spec("opencode:opencode/deepseek-v4-pro") == "opencode"
    assert rd._provider_of_spec("cursor:composer-2.5") == "cursor"


def test_build_rung_planner_untagged_uses_provider_workhorse():
    import skill.scripts.run_delivery as rd
    from cld.executors.base import SliceTask
    planner = rd.build_rung_planner("gemini", evidence={})
    rungs = planner(SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py",
                              complexity="standard"))
    assert rungs == [("workhorse", "gemini:gemini-3.1-pro-preview", 2)]


def test_build_rung_planner_tagged_pins():
    import skill.scripts.run_delivery as rd
    from cld.executors.base import SliceTask
    planner = rd.build_rung_planner("gemini", evidence={})
    rungs = planner(SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py",
                              executor="opencode:opencode/claude-opus-4-8"))
    assert rungs == [("workhorse", "opencode:opencode/claude-opus-4-8", 2)]
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** in `run_delivery.py`:
  - `_provider_of_spec(spec)`: strip an `@effort` suffix if present; take the part before the first `:`; lowercase; return it if in `KNOWN_EXECUTORS` else `"gemini"`.
  - `_available_ids_for(provider)`: `opencode` → `from cld.models import list_models; from cld.executors.opencode import _default_runner; list_models(runner=_default_runner)`; `cursor` → `from cld.models import list_cursor_models; [i for i, _ in list_cursor_models(runner=...)]` (use the cursor default runner; guard); else `[]`. Wrap in try/except → `[]`.
  - `build_rung_planner(default_spec, *, evidence=None, max_retries=2)`: resolve `provider = _provider_of_spec(default_spec)`; `evidence = evidence if evidence is not None else (lambda: __import__("cld.evidence", fromlist=["EvidenceStore"]).EvidenceStore().statuses())()` — simpler: `from cld.evidence import EvidenceStore; evidence = EvidenceStore().statuses()` when None; `available = _available_ids_for(provider)`; return a closure `planner(task)` that calls `from cld.models import plan_rungs; return plan_rungs(task, provider=provider, evidence=evidence, available_ids=available, max_retries=max_retries)`. (Tagged slices short-circuit inside `plan_rungs`, so the build provider is harmless for them.)
  - In `main`, add `rung_planner=build_rung_planner(args.executor or "gemini")` to BOTH `run_plan_parallel(...)` calls (the `--step` branch and the full-run branch).
- [ ] **Step 4: Green + full suite + global sync** (run_delivery.py changed):
```bash
cp skill/scripts/run_delivery.py ~/.claude/skills/cross-llm-delivery/scripts/run_delivery.py
diff -q skill/scripts/run_delivery.py ~/.claude/skills/cross-llm-delivery/scripts/run_delivery.py
python -m pytest -p no:warnings -q
```
- [ ] **Step 5: Commit**
```bash
git add skill/scripts/run_delivery.py tests/test_run_delivery.py
git commit -m "feat(driver): build + wire rung_planner so the escalation ladder runs in real builds"
```

---

## Task 3: `--mark-repaired` handoff hook  [Claude]

The gate-4 repair handoff needs a clean way for the lead agent to record that it has fixed a `needs_repair` slice — so a re-run of `--step` skips it (the SP2 review flagged: `needs_repair` is not terminal in `is_done`, so it would otherwise be re-dispatched).

**Files:** Modify `skill/scripts/run_delivery.py`; Test `tests/test_run_delivery.py`.

**Interfaces:** new CLI option `--mark-repaired <slice_id>` that sets the slice `status=done`, `intervened=True`, `final_rung="orchestrator"` in the ledger and exits 0. No plan dispatch.

- [ ] **Step 1: Write the failing test** (append)

```python
def test_mark_repaired_marks_slice_done(tmp_path):
    import skill.scripts.run_delivery as rd
    from cld.ledger import Ledger
    p = str(tmp_path / "l.json")
    led = Ledger(p); led.set("T1", status="needs_repair", complexity="complex"); led.save()
    rc = rd.main(["dummy-plan.md", "--ledger", p, "--mark-repaired", "T1"])
    assert rc == 0
    e = Ledger.load(p).get("T1")
    assert e.status == "done" and e.intervened is True and e.final_rung == "orchestrator"
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** in `run_delivery.py`:
  - Add `p.add_argument("--mark-repaired", default=None, metavar="SLICE_ID", help="Mark a needs_repair slice as repaired by the orchestrator (status=done, intervened) and exit. Use after fixing a gate-4 slice, before re-running --step.")`.
  - Handle it EARLY in `main` (right after `args = p.parse_args(argv)`, before reading the plan file — it must not require the plan to exist): if `args.mark_repaired`: `from cld.ledger import Ledger, DONE; led = Ledger.load(args.ledger); led.set(args.mark_repaired, status=DONE, intervened=True, final_rung="orchestrator"); led.save(); print(f"marked {args.mark_repaired} repaired (done).")`; `return 0`.
- [ ] **Step 4: Green + full suite + global sync.**
- [ ] **Step 5: Commit**
```bash
git add skill/scripts/run_delivery.py tests/test_run_delivery.py
git commit -m "feat(driver): --mark-repaired hook for the gate-4 orchestrator handoff"
```

---

## Task 4: Per-provider usage reporters + complexity/rung columns  [standard]

Split the bundled account block into modular per-provider reporters (rendered only for providers in play), and add `complexity`/`final_rung` columns to the per-slice table.

**Files:** Modify `src/cld/usage.py`; Test `tests/test_usage.py`.

**Interfaces:**
- `render_usage_table(ledger, oc_stats, *, cursor_about=None)` — unchanged signature; now emits columns `| Slice | Complexity | Model | Rung | Tokens | Cost |` and the account blocks via helpers.
- New module-level helpers: `opencode_account_block(oc_stats) -> list[str]` and `cursor_account_block(cursor_about) -> list[str]` (each returns the block's lines; the table calls them, rendering OpenCode only when stats present, Cursor only when a `cursor:` slice ran).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_usage.py`)

```python
def test_usage_table_has_complexity_and_rung_columns():
    from cld.usage import render_usage_table
    class E:
        def __init__(s, sid, model, tu, cost=None, complexity=None, final_rung=None):
            s.slice_id, s.model, s.token_usage, s.cost = sid, model, tu, cost
            s.complexity, s.final_rung = complexity, final_rung
    class L:
        def __init__(s, e): s._e = {x.slice_id: x for x in e}
        @property
        def entries(s): return s._e
    out = render_usage_table(L([
        E("S1", "gemini:gemini-3.1-pro-preview", {"total": 100}, 0.0, "standard", "workhorse"),
        E("S2", "opencode:opencode/deepseek-v4-pro", {"total": 50}, 0.01, "complex", "orchestrator"),
    ]), {})
    assert "Complexity" in out and "Rung" in out
    assert "standard" in out and "workhorse" in out
    assert "complex" in out and "orchestrator" in out
    assert "150" in out          # build total tokens
    out.encode("cp1252")


def test_usage_account_blocks_are_separate_helpers():
    from cld.usage import opencode_account_block, cursor_account_block
    oc = opencode_account_block({"total_cost": 5.64, "input": "1.3M"})
    assert any("5.64" in ln for ln in oc)
    cur = cursor_account_block({"tier": "Pro", "model": "Composer 2.5"})
    assert any("Pro" in ln for ln in cur)


def test_usage_handles_missing_routing_fields_gracefully():
    # entries without complexity/final_rung (older builds) render with a placeholder, no crash
    from cld.usage import render_usage_table
    class E:
        def __init__(s):
            s.slice_id, s.model, s.token_usage, s.cost = "X", "gemini:gemini-3.1-pro-preview", {"total": 1}, None
            s.complexity = None; s.final_rung = None
    class L:
        def __init__(s, e): s._e = {x.slice_id: x for x in e}
        @property
        def entries(s): return s._e
    out = render_usage_table(L([E()]), {})
    assert "X" in out
    out.encode("cp1252")
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** in `usage.py`:
  - Extract `opencode_account_block(oc_stats)` (the existing `## OpenCode account` lines) and `cursor_account_block(cursor_about)` (the existing `## Cursor account` lines) as module functions returning `list[str]`.
  - `render_usage_table`: header `| Slice | Complexity | Model | Rung | Tokens | Cost |` + separator; per entry use `getattr(entry, "complexity", None) or "-"` and `getattr(entry, "final_rung", None) or "-"`; guard `entry.model or "-"` (avoid `.startswith` on None — compute `has_cursor_slice` with `(entry.model or "").startswith("cursor:")`); keep the build-total sum. Append `opencode_account_block(oc_stats)`; append `cursor_account_block(cursor_about)` only when `cursor_about` and `has_cursor_slice`. ASCII-safe (use `-` not em-dash; if any existing line used a non-ASCII char, replace with ASCII).
- [ ] **Step 4: Green + full suite.** (Update the existing `test_renders_combined_markdown_table` / `test_cursor_block_only_when_cursor_slice_present` if the added columns shift their assertions — keep their intent; the entries in those tests lack complexity/final_rung so they should render `-`.)
- [ ] **Step 5: Commit**
```bash
git add src/cld/usage.py tests/test_usage.py
git commit -m "feat(usage): per-provider account reporters + complexity/rung columns"
```

---

## Task 5: SKILL.md control flow + authoring-plans rubric + global sync  [Claude]

Document the lead-agent control surface (the one-screen plan, run-modes, the gate-4 repair loop) and the complexity rubric.

**Files:** Modify `skill/SKILL.md`, `skill/references/authoring-plans.md`.

- [ ] **Step 1: SKILL.md — the routing control flow.** Add a section (near the picker/`--step` content) covering:
  - **The one-screen routing plan.** After slicing + assessing complexity, present the plan ONCE using `cld.models.render_routing_plan(slices, provider=, evidence=EvidenceStore().statuses(), available_ids=...)` (paste it verbatim, like the picker). Each slice shows complexity + recommended model + `[rec]`/`[you]` + `!` for complex.
  - **Run-modes (how the user controls it):** 1) **advise (default)** — at gate 4, ask before the orchestrator repairs; 2) **autonomous** — the user said "fix things yourself / don't interrupt", so repair without asking; 3) **review each slice** — the user wants to revisit per slice; 4) **adjust first** — pin a slice's model (set its `executor:` tag → `[you]`) before running. The mode is the lead agent's behavior, carried in the conversation; there is NO CLI flag for it.
  - **The gate-4 repair loop:** when `--step` exits **4**, the summary lists the `! NEEDS REPAIR` slice(s). The lead agent (the orchestrator): in advise mode, asks first; then surgically fixes the failing files in the repo, commits, and runs `run_delivery.py <plan> --mark-repaired <slice_id> --ledger <...>` for each, THEN re-invokes `--step` to continue. Cheap escalation (quick→workhorse) is automatic and never reaches the agent; only a workhorse failure does.
  - Reinforce: cheap routing + cheap escalation are automatic and free; the only gated spend is the orchestrator repair.
- [ ] **Step 2: authoring-plans.md — the complexity rubric.** Add a "Complexity (routing hint)" section: `easy` = boilerplate / one well-specified function, known pattern, no tricky logic or I/O; `standard` = typical module, real logic, a few pieces integrated (the **default when unsure**); `complex` = subtle algorithm / concurrency / gnarly edges / ambiguous spec / high rework risk — "even a good cheap model would likely struggle"; flagged `!` and expects orchestrator repair. State the rule: **never downgrade to save money when unsure — default to `standard`** (a wrong-low guess just causes escalations).
- [ ] **Step 3: Global sync + verify.**
```bash
cp skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
cp skill/references/authoring-plans.md ~/.claude/skills/cross-llm-delivery/references/authoring-plans.md
diff -q skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
diff -q skill/references/authoring-plans.md ~/.claude/skills/cross-llm-delivery/references/authoring-plans.md
```
- [ ] **Step 4: Full suite (integration gate).** `python -m pytest -p no:warnings -q`.
- [ ] **Step 5: Commit + advance STATUS.**
```bash
git add skill/SKILL.md skill/references/authoring-plans.md
git commit -m "docs(skill): routing control flow (one-screen plan, run-modes, gate-4 repair loop) + complexity rubric"
```
Update STATUS.md: Sub-plan 3 done → spec #1 COMPLETE; Next = final whole-feature review, then spec #2 (C1 per-provider split).

---

## Done criteria (Sub-plan 3)
- `render_routing_plan` shows the one-screen per-slice plan (complexity + recommended model + `[rec]`/`[you]` + `!`).
- The real `rung_planner` is wired into both `run_plan_parallel` call sites, so the escalation ladder runs in real builds (untagged slices auto-route by complexity; tagged slices pin).
- `--mark-repaired` lets the lead agent close out a gate-4 handoff so re-runs skip the repaired slice.
- The usage view has complexity/rung columns and modular per-provider account reporters; old entries render `-`, no crash.
- SKILL.md documents the one-screen plan + run-modes + gate-4 repair loop; authoring-plans.md has the complexity rubric; global synced.
- Full suite green. STATUS updated: spec #1 complete; next = final feature review then spec #2.
