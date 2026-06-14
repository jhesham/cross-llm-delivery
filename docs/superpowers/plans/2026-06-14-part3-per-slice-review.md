# Part 3 — Opt-in Per-Slice Review Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md. **Depends on Part 1 (picker) + the shipped per-slice `executor_factory`.**

**Goal:** An opt-in mode where the lead agent revisits executor/model/effort at each slice start. OFF by default (the S1b "pick once, stick" rule stays). When ON, the chosen spec applies to that slice only and is recorded in the ledger.

**Architecture:** `run_plan_parallel` gains an optional `slice_pick_fn(task, default_spec) -> spec` callback; `_executor_for` calls it when present AND the slice has no explicit tag. A tagged slice always wins (no prompt). The driver gains `--per-slice-pick` and wires a picker-backed callback; SKILL.md documents the mode. The chosen spec already flows to the ledger via Plan-2's usage threading (model recorded), extended to also record effort.

**Tech Stack:** Python 3.11+ stdlib, pytest fakes.

**Spec:** `docs/superpowers/specs/2026-06-14-scalable-picker-and-cursor-design.md` (Part 3)

**Builder routing:** All CLAUDE (orchestrator seam + driver wiring + SKILL.md — behavior-critical, must preserve the S1b fix exactly).

---

## File Structure
- **Modify `src/cld/orchestrator.py`** — `slice_pick_fn` param + `_executor_for` hook (both `run_plan` and `run_plan_parallel`).
- **Modify `src/cld/ledger.py`** — `LedgerEntry.effort` field (so per-slice effort is recorded).
- **Modify `skill/scripts/run_delivery.py`** — `--per-slice-pick` flag + a callback that drives the picker per untagged slice.
- **Modify `skill/SKILL.md`** — the mode's rules; sync global.
- Tests: `tests/test_orchestrator_parallel.py`, `tests/test_ledger.py`, `tests/test_run_delivery.py`.

Reused: `_executor_for`/`executor_factory` (shipped), `build_model_index`/`pick_executor` (Part 1).

---

## Task 1: `slice_pick_fn` hook in the orchestrator  [CLAUDE]

**Files:** Modify `src/cld/orchestrator.py`; Test `tests/test_orchestrator_parallel.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
def test_slice_pick_fn_used_for_untagged_only(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    picked = []
    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, task, workdir, feedback=None):
            picked.append((task.id, self.spec))
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")

    def slice_pick(task, default_spec):
        # the review-mode callback: choose opencode for everything it's asked about
        return "opencode:opencode/deepseek-v4-pro"

    slices = [
        SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py"),  # untagged
        SliceTask(id="T2", brief="b", files=["y"], acceptance_test_path="t.py",
                  executor="cursor:composer-2.5"),                                 # tagged
    ]
    ledger = Ledger(str(tmp_path / "l.json"))
    run_plan_parallel(
        slices, ledger,
        executor_factory=lambda spec: _Rec(spec), default_spec="gemini",
        slice_pick_fn=slice_pick,
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    d = dict(picked)
    assert d["T1"] == "opencode:opencode/deepseek-v4-pro"  # untagged -> pick_fn chose
    assert d["T2"] == "cursor:composer-2.5"                # tagged -> tag wins, no prompt


def test_no_slice_pick_fn_is_current_behavior(tmp_path):
    # default (no callback) = pick-once-stick (S1b fix preserved)
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult
    seen = []
    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, t, w, feedback=None):
            seen.append(self.spec); return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")
    run_plan_parallel(
        [SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py")],
        Ledger(str(tmp_path / "l.json")),
        executor_factory=lambda s: _Rec(s), default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed")
    assert seen == ["gemini"]  # no pick_fn -> build default
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_orchestrator_parallel.py -k "slice_pick" -q -p no:warnings`
Expected: FAIL — `unexpected keyword argument 'slice_pick_fn'`.

- [ ] **Step 3: Implement**
In `src/cld/orchestrator.py`, add `slice_pick_fn: Callable | None = None` to BOTH `run_plan` and
`run_plan_parallel` signatures (keyword-only, default None). Update `_executor_for` (and the
`run_plan` equivalent):
```python
    def _executor_for(task):
        if task.executor:                       # explicit tag wins, no prompt
            spec = task.executor
        elif slice_pick_fn is not None:          # review mode: ask per untagged slice
            spec = slice_pick_fn(task, default_spec) or default_spec
        else:
            spec = default_spec                  # pick-once-stick (S1b fix)
        if executor_factory is not None:
            return executor_factory(spec)
        return executor
```
(Apply the same shape in `run_plan`'s loop. Record `spec` on the task or a local so Task 2 can
persist it — simplest: have `_executor_for` return `(executor_obj, spec)` OR stash the resolved
spec; keep it minimal — a local dict `resolved_spec[task.id] = spec` used by the ledger write is fine.)

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/test_orchestrator_parallel.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS (existing tests green — `slice_pick_fn=None` is current behavior).

- [ ] **Step 5: Commit**
```bash
git add src/cld/orchestrator.py tests/test_orchestrator_parallel.py
git commit -m "feat(orchestrator): slice_pick_fn hook for opt-in per-slice executor review"
```

---

## Task 2: Record per-slice effort in the ledger  [CLAUDE]

**Files:** Modify `src/cld/ledger.py`, `src/cld/orchestrator.py`; Test `tests/test_ledger.py`

- [ ] **Step 1: Write the failing test (append to tests/test_ledger.py)**
```python
def test_ledger_records_effort(tmp_path):
    from cld.ledger import Ledger
    p = str(tmp_path / "l.json")
    led = Ledger(p)
    led.set("T1", status="done", model="cursor:claude-opus-4-8", effort="medium")
    led.save()
    e = Ledger.load(p).get("T1")
    assert e.model == "cursor:claude-opus-4-8"
    assert e.effort == "medium"


def test_old_ledger_loads_with_none_effort(tmp_path):
    import json
    from cld.ledger import Ledger
    p = str(tmp_path / "o.json")
    json.dump({"T1": {"status": "done", "attempts": 1}}, open(p, "w"))
    assert Ledger.load(p).get("T1").effort is None
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_ledger.py -k effort -q -p no:warnings`
Expected: FAIL — `set() got an unexpected keyword argument 'effort'`.

- [ ] **Step 3: Implement**
In `src/cld/ledger.py`: add `effort: str | None = None` to `LedgerEntry`; read
`entry_data.get("effort")` in `load`; accept `effort=None` in `set` (apply if not None);
serialize `"effort": entry.effort` in `save`. (Mirror exactly how `model` was added.)
In `src/cld/orchestrator.py`: when writing the ledger for a slice, also pass the resolved effort.
The effort comes from the resolved spec's `@effort` (parse it) OR from the executor object; the
simplest source: split the resolved spec on `@` for the effort. Pass `effort=<that>` in the
`ledger.set(...)` calls alongside `model`.

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/test_ledger.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/ledger.py src/cld/orchestrator.py tests/test_ledger.py
git commit -m "feat(ledger): record per-slice effort (backward-compatible)"
```

---

## Task 3: `--per-slice-pick` flag + callback in run_delivery  [CLAUDE]

**Files:** Modify `skill/scripts/run_delivery.py`; Test `tests/test_run_delivery.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
def test_per_slice_pick_flag_parsed_and_default_off():
    # the flag exists and defaults off
    import argparse
    # build the parser the same way main does by calling main with --help-free args is hard;
    # instead assert the helper that creates the slice_pick callback only activates when on.
    cb_off = run_delivery.make_slice_pick_fn(per_slice=False)
    assert cb_off is None  # off -> no callback (pick-once-stick)
    cb_on = run_delivery.make_slice_pick_fn(per_slice=True)
    assert callable(cb_on)  # on -> a callback is provided
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_run_delivery.py -k per_slice_pick -q -p no:warnings`
Expected: FAIL — `module 'run_delivery' has no attribute 'make_slice_pick_fn'`.

- [ ] **Step 3: Implement**
In `skill/scripts/run_delivery.py`:
- Add the arg: `p.add_argument("--per-slice-pick", action="store_true", help="Review executor/"
  "model/effort at EACH slice start (default off = pick once and stick).")`.
- Add `make_slice_pick_fn(per_slice: bool)`:
  ```python
  def make_slice_pick_fn(per_slice: bool):
      if not per_slice:
          return None
      def pick(task, default_spec):
          # interactive per-slice pick; falls back to default if non-interactive
          if not sys.stdin.isatty():
              return default_spec
          print(f"\n[per-slice] slice {task.id}: choose executor/model "
                f"(enter = keep {default_spec})")
          return prompt_for_executor() or default_spec
      return pick
  ```
- In `main`, pass `slice_pick_fn=make_slice_pick_fn(args.per_slice_pick)` into BOTH
  `run_plan_parallel` call sites (alongside `executor_factory`/`default_spec`).

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/test_run_delivery.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS; `--help` shows `--per-slice-pick`.

- [ ] **Step 5: Sync global + commit**
```bash
cp skill/scripts/run_delivery.py ~/.claude/skills/cross-llm-delivery/scripts/run_delivery.py
git add skill/scripts/run_delivery.py tests/test_run_delivery.py
git commit -m "feat(driver): --per-slice-pick opt-in per-slice executor review"
```

---

## Task 4: SKILL.md per-slice review rules + global sync  [CLAUDE]

**Files:** Modify `skill/SKILL.md`

- [ ] **Step 1: Document the mode**
Add to `skill/SKILL.md` (picker section): **Per-slice review mode.** Default OFF — executor chosen
once, sticks; NEVER prompt per slice (the S1b fix). Enable with `--per-slice-pick` (or the user
saying "review executor per slice"): then at EACH untagged slice start, present the picker (current
choice pre-selected; enter keeps it) to revisit executor/provider/model/effort for THAT slice only.
A slice with an `executor:`/`@effort` TAG is honored silently even in review mode (tag = decision).
The per-slice choice is recorded in the ledger (visible in `--usage`). Reinforce: do NOT prompt
per slice unless the mode is on or the slice is tagged.

- [ ] **Step 2: Sync global + verify**
```bash
cp skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
diff -q skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
```

- [ ] **Step 3: Full suite (integration gate)**
Run: `python -m pytest -p no:warnings -q`

- [ ] **Step 4: Commit + advance STATUS**
```bash
git add skill/SKILL.md
git commit -m "docs(skill): opt-in per-slice review mode rules (S1b fix preserved)"
```
Update STATUS.md: Part 3 done; Next = Part 4 Task 1.

---

## Done criteria (Part 3)
- `slice_pick_fn` is called only for untagged slices when provided; tagged slices win silently;
  no callback = current pick-once-stick behavior (S1b fix intact).
- Per-slice model + effort recorded in the ledger; old ledgers load.
- `--per-slice-pick` (default off) wires the picker-backed callback; non-interactive falls back to default.
- SKILL.md documents OFF/ON unambiguously. Full suite green; backward-compatible.
