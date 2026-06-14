# Part 4 — Sub-slices (one level) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md. **Depends on Parts 1 + 3 (picker + per-slice review).**

**Goal:** A slice may contain one level of `## SUBSLICE:` units, each with its own files/test/deps and its own optional executor/effort tag. Sub-slices run as ordered children under their parent; each is independently routed (tag / default / review-mode prompt) and recorded in the ledger attributed to the parent. The parent is "done" only when all its sub-slices are accepted.

**Architecture:** `load_slices` parses sub-slices onto `SliceTask.subslices` (each a SliceTask with `parent_id`). The orchestrator, before running a slice, expands it: if it has sub-slices, run them as ordered children (each via the same `deliver_slice` + `_executor_for` path), and mark the parent done iff all children accepted. Ledger keys children `parent/sub`. The Part-3 review prompt fires per sub-slice when the mode is on.

**Tech Stack:** Python 3.11+ stdlib, pytest fakes.

**Spec:** `docs/superpowers/specs/2026-06-14-scalable-picker-and-cursor-design.md` (Part 4)

**Builder routing:** T1 plan parse = DOGFOOD (Gemini, pure). T2 SliceTask fields = CLAUDE. T3 orchestrator child-execution = CLAUDE (structural, careful). T4 ledger attribution + usage nesting = CLAUDE. T5 SKILL.md + authoring-plans note + global sync = CLAUDE.

---

## File Structure
- **Modify `src/cld/executors/base.py`** — `SliceTask.subslices: list` + `parent_id: str | None`.
- **Modify `src/cld/plan/slice.py`** — parse `## SUBSLICE:` under a `## SLICE:`; round-trip.
- **Modify `src/cld/orchestrator.py`** — expand a slice with sub-slices into ordered child runs;
  parent done-iff-all-children.
- **Modify `src/cld/usage.py`** — render sub-slice rows nested/attributed under the parent.
- **Modify `skill/SKILL.md` + `skill/references/authoring-plans.md`** — sub-slice syntax; sync global.
- Tests: `tests/test_slice.py`, `tests/executors/test_base.py`, `tests/test_orchestrator_parallel.py`, `tests/test_usage.py`.

Reused: `deliver_slice`, `_executor_for`, `slice_pick_fn` (Part 3), ledger usage fields.

---

## Task 1: Parse `## SUBSLICE:` in load_slices  [DOGFOOD — Gemini]

**Files:** Modify `src/cld/plan/slice.py`, `src/cld/executors/base.py` (minimal — fields needed
first); Test `tests/test_slice.py` (append)

> NOTE: this task needs the `subslices`/`parent_id` fields to exist. Do Task 2's field-add FIRST
> if the dogfood needs them — OR include the two-line dataclass change in this task's brief. To keep
> the dogfood pure-logic, **fields are added in Task 2 which runs BEFORE this in execution order**;
> reorder so Task 2 (fields, CLAUDE) is done first, then this Task 1 (parse, dogfood). (Execution
> order: T2 → T1 → T3 → T4 → T5. Numbered by topic, not run-order; the controller runs T2 first.)

- [ ] **Step 1: Write the failing test (append)**
```python
SUB_PLAN = """## SLICE: P1
brief: parent
files: src/p.py
acceptance_test_path: tests/test_p.py
deps:

## SUBSLICE: P1a
brief: child a
files: src/a.py
acceptance_test_path: tests/test_p.py::test_a
executor: cursor:composer-2.5

## SUBSLICE: P1b
brief: child b
files: src/b.py
acceptance_test_path: tests/test_p.py::test_b

## SLICE: P2
brief: standalone
files: src/q.py
acceptance_test_path: tests/test_q.py
deps: P1
"""


def test_subslices_parsed_under_parent():
    s = {x.id: x for x in load_slices(SUB_PLAN)}
    assert set(s) == {"P1", "P2"}            # subslices are NOT top-level slices
    assert [c.id for c in s["P1"].subslices] == ["P1a", "P1b"]
    assert s["P1"].subslices[0].parent_id == "P1"
    assert s["P1"].subslices[0].executor == "cursor:composer-2.5"
    assert s["P1"].subslices[1].executor is None
    assert s["P2"].subslices == []


def test_subslices_round_trip():
    md = slices_to_markdown(load_slices(SUB_PLAN))
    s = {x.id: x for x in load_slices(md)}
    assert [c.id for c in s["P1"].subslices] == ["P1a", "P1b"]
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_slice.py -k subslice -q -p no:warnings`
Expected: FAIL (subslices empty / attr error).

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**
Brief: edit `src/cld/plan/slice.py` so `load_slices` handles `## SUBSLICE: <id>` blocks: a
SUBSLICE line starts a sub-slice belonging to the most recent `## SLICE:`; its fields (brief,
files, acceptance_test_path, deps, executor) parse like a slice; build it via `_dict_to_slice`
with `parent_id` = the parent's id and append to the parent's `subslices` list. SUBSLICEs are NOT
added to the top-level `slices` list. `slices_to_markdown` emits each slice's `## SUBSLICE:` blocks
(with their fields, incl. executor when set) after the parent's lines. stdlib only. (The
`subslices`/`parent_id` fields already exist on SliceTask from Task 2.)

- [ ] **Step 4: Judge**
Run: `python -m pytest tests/test_slice.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/plan/slice.py tests/test_slice.py
git commit -m "feat(subslice): parse + round-trip ## SUBSLICE: under a slice (Gemini-built, Claude-judged)"
```

---

## Task 2: `SliceTask.subslices` + `parent_id` fields  [CLAUDE — run FIRST]

**Files:** Modify `src/cld/executors/base.py`; Test `tests/executors/test_base.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
def test_slicetask_subslices_and_parent_id_default_empty():
    t = SliceTask(id="P", brief="b", files=["x"], acceptance_test_path="t.py")
    assert t.subslices == [] and t.parent_id is None
    child = SliceTask(id="Pa", brief="b", files=["y"], acceptance_test_path="t.py", parent_id="P")
    assert child.parent_id == "P"
    parent = SliceTask(id="P2", brief="b", files=["x"], acceptance_test_path="t.py",
                       subslices=[child])
    assert parent.subslices[0].id == "Pa"
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/executors/test_base.py -k subslices -q -p no:warnings`
Expected: FAIL — unexpected kwargs.

- [ ] **Step 3: Implement**
In `src/cld/executors/base.py`, add to `SliceTask` (after `executor`):
```python
    parent_id: str | None = None
    subslices: list = field(default_factory=list)
```

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/executors/test_base.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS (additive, backward-compatible).

- [ ] **Step 5: Commit**
```bash
git add src/cld/executors/base.py tests/executors/test_base.py
git commit -m "feat(subslice): SliceTask gains parent_id + subslices fields"
```

---

## Task 3: Orchestrator runs sub-slices as ordered children  [CLAUDE]

**Files:** Modify `src/cld/orchestrator.py`; Test `tests/test_orchestrator_parallel.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
def test_parent_runs_subslices_each_with_own_executor(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    ran = []
    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, task, workdir, feedback=None):
            ran.append((task.id, self.spec))
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")

    parent = SliceTask(id="P", brief="b", files=["p"], acceptance_test_path="t.py", subslices=[
        SliceTask(id="Pa", brief="b", files=["a"], acceptance_test_path="t.py",
                  parent_id="P", executor="cursor:composer-2.5"),
        SliceTask(id="Pb", brief="b", files=["b"], acceptance_test_path="t.py", parent_id="P"),
    ])
    p = str(tmp_path / "l.json")
    ledger = Ledger(p)
    res = run_plan_parallel(
        [parent], ledger,
        executor_factory=lambda spec: _Rec(spec), default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed")
    d = dict(ran)
    assert d["Pa"] == "cursor:composer-2.5"   # child tag honored
    assert d["Pb"] == "gemini"                # untagged child -> default
    # parent done iff all children accepted
    assert "P" in res.completed
    # children recorded in ledger keyed under the parent
    led = Ledger.load(p)
    assert led.get("P/Pa") is not None and led.get("P/Pb") is not None


def test_failed_subslice_fails_only_itself_and_parent_incomplete(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult
    class _Mix:
        def run(self, task, workdir, feedback=None):
            ok = task.id != "Pb"   # Pb fails
            return ExecutorResult(ok=ok, diff="", files_changed=[], raw_log="")
    parent = SliceTask(id="P", brief="b", files=["p"], acceptance_test_path="t.py", subslices=[
        SliceTask(id="Pa", brief="b", files=["a"], acceptance_test_path="t.py", parent_id="P"),
        SliceTask(id="Pb", brief="b", files=["b"], acceptance_test_path="t.py", parent_id="P"),
    ])
    res = run_plan_parallel(
        [parent], Ledger(str(tmp_path / "l.json")),
        executor=_Mix(),
        judge_fn=lambda **kw: type("J", (), {"passed": kw.get("files_changed") is not None, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed")
    assert "P" not in res.completed   # parent NOT complete (a child failed)
    assert "P" in res.failed
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_orchestrator_parallel.py -k subslice -q -p no:warnings`
Expected: FAIL (sub-slices not executed; parent treated as a leaf).

- [ ] **Step 3: Implement (Claude — structural; keep it minimal & careful)**
In `src/cld/orchestrator.py`, in `_run_one(task)` (and the `run_plan` equivalent): if
`task.subslices` is non-empty, run them as ORDERED children instead of delivering the parent
directly:
```python
        if task.subslices:
            all_ok = True
            for child in task.subslices:
                child_res = deliver_slice(
                    child, executor=_executor_for(child),
                    judge_fn=judge_fn, max_retries=max_retries,
                    workdir=<child worktree or task.id/child.id>, test_runner=test_runner)
                # record child in ledger keyed f"{task.id}/{child.id}" with its model/effort
                with ledger_lock:
                    ledger.set(f"{task.id}/{child.id}",
                               status=DONE if child_res.accepted else FAILED,
                               attempts=child_res.attempts,
                               model=child_res.model, token_usage=child_res.token_usage)
                    ledger.save()
                all_ok = all_ok and child_res.accepted
            # synthesize a parent DeliverResult: accepted iff all children accepted
            return DeliverResult(accepted=all_ok, attempts=1, final=None, history=[],
                                 files_changed=[], diff_lines=0, model=None, token_usage={})
        # ... existing leaf-slice path unchanged ...
```
(Use the existing worktree pattern for each child when `repo_dir`/`git_runner` are set — one
worktree per child, `slice-<parent>-<child>`. Keep the leaf path exactly as today. Children use
`_executor_for(child)` so tag / default / Part-3 review all apply per sub-slice. `_process` then
records the PARENT as completed/failed based on the synthesized result, as it does today.)

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/test_orchestrator_parallel.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS (leaf slices behave exactly as before; sub-slice parents run children).

- [ ] **Step 5: Commit**
```bash
git add src/cld/orchestrator.py tests/test_orchestrator_parallel.py
git commit -m "feat(subslice): orchestrator runs sub-slices as ordered children; parent done iff all accepted"
```

---

## Task 4: Usage view attributes sub-slices under the parent  [CLAUDE]

**Files:** Modify `src/cld/usage.py`; Test `tests/test_usage.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
def test_usage_nests_subslices_under_parent():
    from cld.usage import render_usage_table
    class E:
        def __init__(s, sid, model, tu, cost=None):
            s.slice_id, s.model, s.token_usage, s.cost = sid, model, tu, cost
    class L:
        def __init__(s, e): s._e = {x.slice_id: x for x in e}
        @property
        def entries(s): return s._e
    out = render_usage_table(L([
        E("P", "gemini:gemini-3.1-pro-preview", {"total": 0}),
        E("P/Pa", "cursor:composer-2.5", {"total": 50}, 0.0),
        E("P/Pb", "opencode:opencode/deepseek-v4-pro", {"total": 80}, 0.01),
    ]), {})
    # child rows present and recognizable as children of P
    assert "P/Pa" in out and "P/Pb" in out
    assert "cursor:composer-2.5" in out and "opencode:opencode/deepseek-v4-pro" in out
    # build total includes children
    assert "130" in out  # 50 + 80 (+0)
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_usage.py -k nests_subslices -q -p no:warnings`
Expected: PASS already if the table just iterates entries? — verify: if it already passes (the
table iterates all ledger entries incl. `P/Pa`), then this task is mostly a DISPLAY refinement
(indent children under parent). If it fails, implement below.

- [ ] **Step 3: Implement (display nesting)**
In `src/cld/usage.py` `render_usage_table`: when rendering rows, detect child keys (containing
`/`), and render them indented under their parent row (sort so a parent's children follow it).
The build-total tokens sum already counts every entry (children included) — keep that. Keep ASCII/
cp1252-safe.

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/test_usage.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/usage.py tests/test_usage.py
git commit -m "feat(usage): nest sub-slice rows under their parent in the usage table"
```

---

## Task 5: SKILL.md + authoring-plans sub-slice docs; global sync  [CLAUDE]

**Files:** Modify `skill/SKILL.md`, `skill/references/authoring-plans.md`

- [ ] **Step 1: Document the `## SUBSLICE:` syntax**
In `skill/references/authoring-plans.md` (and a pointer in SKILL.md): a `## SLICE:` may contain
one level of `## SUBSLICE: <id>` blocks (same fields + optional `executor:`/`@effort`). Sub-slices
run as ordered children under the parent; the parent completes only when ALL sub-slices are
accepted; each sub-slice is independently routed (tag / build default / per-slice review when on)
and shows nested in `--usage`. ONE level only (no sub-sub-slices). Use sub-slices to split one
logical slice across different models/efforts.

- [ ] **Step 2: Sync global + verify**
```bash
cp skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
cp skill/references/authoring-plans.md ~/.claude/skills/cross-llm-delivery/references/authoring-plans.md
diff -q skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
diff -q skill/references/authoring-plans.md ~/.claude/skills/cross-llm-delivery/references/authoring-plans.md
```
Expected: no diffs.

- [ ] **Step 3: Full suite (final integration gate for the whole feature)**
Run: `python -m pytest -p no:warnings -q`
Expected: green.

- [ ] **Step 4: Commit + advance STATUS**
```bash
git add skill/SKILL.md skill/references/authoring-plans.md
git commit -m "docs(subslice): ## SUBSLICE: authoring syntax + usage nesting"
```
Update STATUS.md: Part 4 done → WHOLE FEATURE complete (all 4 parts shipped).

---

## Done criteria (Part 4)
- `## SUBSLICE:` parses into `SliceTask.subslices` with `parent_id`; round-trips.
- Orchestrator runs sub-slices as ordered children, each via `_executor_for` (tag/default/review);
  parent done iff all children accepted; a failed child fails only itself + leaves parent incomplete.
- Ledger records children keyed `parent/child` with model+effort+tokens; usage view nests them.
- ONE level only. Full suite green; leaf-slice behavior unchanged (backward-compatible).
