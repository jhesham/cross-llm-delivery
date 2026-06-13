# Per-Slice Executor Selection — Implementation Plan (Feature 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each slice run on its own executor/model (a `## SLICE:` `executor:` line), curate the picker's main shortlist (add kimi-k2.6 + claude-sonnet-4-6), and document the picker-frequency discipline (choose once per build, never re-prompt per slice).

**Architecture:** Add an optional `executor` field to `SliceTask`, parse it in `slice.py`, and make `run_plan_parallel` resolve an executor PER SLICE via an injected `executor_factory(spec)->executor` (falling back to the build default). Catalog additions are pure `MODEL_METADATA` edits. Picker-frequency + the bounded agent-proposal rule are SKILL.md prose.

**Tech Stack:** Python 3.11+ stdlib, pytest with fakes (no live LLM in the suite).

**Spec:** `docs/superpowers/specs/2026-06-13-multi-llm-build-controls-design.md` (Feature 1)

**Builder routing (dogfood method):** T1 catalog = DOGFOOD (Gemini — pure data). T2 slice.py parse = DOGFOOD (Gemini — pure). T3 SliceTask field, T4 executor_factory seam, T5 per-slice resolution in run_plan_parallel, T6 run_delivery wiring, T7 SKILL.md = CLAUDE (seams + behavior). Each dogfood: Claude authors the failing test + brief, dispatches, judges with independent pytest.

---

## File Structure

- **Modify `src/cld/models.py`** — add `opencode/kimi-k2.6` + `opencode/claude-sonnet-4-6` to `MODEL_METADATA`.
- **Modify `src/cld/executors/base.py`** — `SliceTask` gains `executor: str | None = None`.
- **Modify `src/cld/plan/slice.py`** — parse an `executor:` line; round-trip in `slices_to_markdown`.
- **Modify `src/cld/orchestrator.py`** — `run_plan_parallel` gains `executor_factory` and resolves per-slice; `_run_one` builds the slice's executor.
- **Modify `skill/scripts/run_delivery.py`** — pass an `executor_factory` (built from `parse_executor_spec`+`get_executor`) into `run_plan_parallel`.
- **Modify `skill/SKILL.md`** — picker-frequency discipline + bounded agent-proposal rule + the new shortlist; sync global.
- Tests: `tests/test_models.py`, `tests/test_slice.py` (or existing slice test), `tests/test_orchestrator_parallel.py`, `tests/test_run_delivery.py`.

Reused as-is: `parse_executor_spec`, `get_executor` (raises ValueError listing KNOWN_EXECUTORS), `recommend`, the cost-confirm + `resolve_and_validate` gates (agent-layer).

---

## Task 1: Catalog — add kimi-k2.6 + claude-sonnet-4-6  [DOGFOOD — Gemini]

**Files:**
- Modify: `src/cld/models.py` (`MODEL_METADATA`)
- Test: `tests/test_models.py` (append)

- [ ] **Step 1: Write the failing test (append to tests/test_models.py)**

```python
def test_catalog_has_kimi_and_sonnet_shortlist_entries():
    # Picker main shortlist additions (ids verified against live `opencode models`:
    # kimi-k2.6 and claude-sonnet-4-6 exist; kimi-k2.7 / claude-sonnet-2.6 do NOT).
    kimi = MODEL_METADATA["opencode/kimi-k2.6"]
    assert kimi.capability_class == "heavy"
    assert kimi.cost_class == "cheap-metered"
    assert kimi.headless_status == "untested"   # never cleanly validated -> validate-first

    sonnet = MODEL_METADATA["opencode/claude-sonnet-4-6"]
    assert sonnet.capability_class == "heavy"
    assert sonnet.cost_class == "premium-metered"
    assert sonnet.headless_status == "likely"


def test_recommend_surfaces_kimi_and_sonnet():
    recs = recommend(available_ids=[
        "opencode/kimi-k2.6", "opencode/claude-sonnet-4-6", "opencode/gemini-3.1-pro",
    ])
    ids = [r.id for r in recs]
    assert "opencode/kimi-k2.6" in ids
    assert "opencode/claude-sonnet-4-6" in ids
    # the proven gemini workhorse is still the default
    assert any(r.is_default and r.id == "gemini:gemini-3.1-pro-preview" for r in recs)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_models.py -k "kimi_and_sonnet" -q -p no:warnings`
Expected: FAIL — `KeyError: 'opencode/kimi-k2.6'`.

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**

Dispatch (locked form): `GEMINI_CLI_TRUST_WORKSPACE=true gemini -p "<brief>" -m gemini-3.1-pro-preview --yolo --skip-trust -o json`.
Brief — add two entries to `MODEL_METADATA` in `src/cld/models.py`, touching nothing else, stdlib only, until `tests/test_models.py` passes (do not edit tests):

```python
    "opencode/kimi-k2.6": ModelInfo(
        id="opencode/kimi-k2.6",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="heavy",
        headless_status="untested",
        rework_risk="medium",
        note="strong model; never cleanly validated headless — validate before trusting",
    ),
    "opencode/claude-sonnet-4-6": ModelInfo(
        id="opencode/claude-sonnet-4-6",
        provider="opencode",
        cost_class="premium-metered",
        capability_class="heavy",
        headless_status="likely",
        rework_risk="low",
        note="capable Anthropic Sonnet via OpenCode; bills real money",
    ),
```

- [ ] **Step 4: Judge — run independently**

Run: `python -m pytest tests/test_models.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: all PASS; full suite green.

- [ ] **Step 5: Commit (merge of the dogfood)**

```bash
git add src/cld/models.py tests/test_models.py
git commit -m "feat(catalog): add kimi-k2.6 + claude-sonnet-4-6 to picker shortlist (Gemini-built, Claude-judged)"
```

---

## Task 2: `SliceTask.executor` field  [CLAUDE]

**Files:**
- Modify: `src/cld/executors/base.py` (`SliceTask`)
- Test: `tests/executors/test_base.py` (create if absent, else append)

- [ ] **Step 1: Write the failing test**

```python
# tests/executors/test_base.py
from cld.executors.base import SliceTask


def test_slicetask_has_optional_executor_field():
    t = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    assert t.executor is None  # defaults to None (use build default)
    t2 = SliceTask(id="T2", brief="b", files=["x"], acceptance_test_path="t.py",
                   executor="opencode:opencode/claude-sonnet-4-6")
    assert t2.executor == "opencode:opencode/claude-sonnet-4-6"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/executors/test_base.py -q -p no:warnings`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'executor'`.

- [ ] **Step 3: Add the field**

In `src/cld/executors/base.py`, add to `SliceTask` (after `deps`):

```python
@dataclass
class SliceTask:
    id: str
    brief: str
    files: list[str]
    acceptance_test_path: str
    deps: list[str] = field(default_factory=list)
    executor: str | None = None  # optional per-slice executor spec; None -> build default
```

- [ ] **Step 4: Run to verify it passes + full suite**

Run: `python -m pytest tests/executors/test_base.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS (the new optional field is backward-compatible).

- [ ] **Step 5: Commit**

```bash
git add src/cld/executors/base.py tests/executors/test_base.py
git commit -m "feat(slice): SliceTask gains optional per-slice executor field"
```

---

## Task 3: Parse `executor:` in slice.py  [DOGFOOD — Gemini]

**Files:**
- Modify: `src/cld/plan/slice.py`
- Test: `tests/test_slice.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_slice.py
from cld.plan.slice import load_slices, slices_to_markdown

PLAN = """## SLICE: T1
brief: do a
files: src/a.py
acceptance_test_path: tests/test_a.py
deps:

## SLICE: T2
brief: do b
files: src/b.py
acceptance_test_path: tests/test_b.py
executor: opencode:opencode/claude-sonnet-4-6
deps: T1
"""


def test_executor_field_parsed_when_present_else_none():
    s = {x.id: x for x in load_slices(PLAN)}
    assert s["T1"].executor is None
    assert s["T2"].executor == "opencode:opencode/claude-sonnet-4-6"


def test_executor_round_trips_through_markdown():
    s = load_slices(PLAN)
    md = slices_to_markdown(s)
    reparsed = {x.id: x for x in load_slices(md)}
    assert reparsed["T2"].executor == "opencode:opencode/claude-sonnet-4-6"
    # a slice with no executor must NOT emit a stray 'executor:' line
    assert reparsed["T1"].executor is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_slice.py -q -p no:warnings`
Expected: FAIL — `T2.executor` is None (parser ignores the line).

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**

Brief — edit `src/cld/plan/slice.py` (stdlib only; don't touch tests), until `tests/test_slice.py` passes:
- In `load_slices`, add an `elif key == "executor": current_slice["executor"] = val` branch
  (alongside `brief`/`acceptance_test_path`).
- In `_dict_to_slice`, pass `executor=d.get("executor")` to `SliceTask(...)`.
- In `slices_to_markdown`, emit `executor: <val>` ONLY when `s.executor` is set (no stray line
  when None), placed before the `deps:` line.

- [ ] **Step 4: Judge — run independently**

Run: `python -m pytest tests/test_slice.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: all PASS; full suite green.

- [ ] **Step 5: Commit (merge of the dogfood)**

```bash
git add src/cld/plan/slice.py tests/test_slice.py
git commit -m "feat(slice): parse + round-trip per-slice executor: field (Gemini-built, Claude-judged)"
```

---

## Task 4: `executor_factory` seam + default in run_plan_parallel  [CLAUDE]

**Files:**
- Modify: `src/cld/orchestrator.py` (`run_plan_parallel` signature)
- Test: `tests/test_orchestrator_parallel.py` (append)

- [ ] **Step 1: Write the failing test**

This task ONLY establishes the new kwargs (the factory is actually *invoked* in Task 5). So the
test asserts the kwargs are accepted and the run still completes — not that the factory is called.

```python
def test_run_plan_parallel_accepts_executor_factory(tmp_path):
    # Additive, backward-compatible: run_plan_parallel accepts executor_factory + default_spec.
    # (Per-slice invocation of the factory is verified in the next task.)
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    class _Exec:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")

    slices = [SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py")]
    ledger = Ledger(str(tmp_path / "l.json"))
    res = run_plan_parallel(
        slices, ledger,
        executor=_Exec(),                 # legacy default still honored this task
        executor_factory=None,            # kwarg ACCEPTED (not yet exercised)
        default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    assert "T1" in res.completed  # run completed without error; new kwargs accepted
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_orchestrator_parallel.py -k executor_factory -q -p no:warnings`
Expected: FAIL — `run_plan_parallel() got an unexpected keyword argument 'executor_factory'`.

- [ ] **Step 3: Add the parameter + default-spec plumbing**

In `src/cld/orchestrator.py`, change the `run_plan_parallel` signature to accept BOTH the
legacy `executor` and a new `executor_factory` + `default_spec`:

```python
def run_plan_parallel(
    slices: list[SliceTask],
    ledger: Ledger,
    *,
    executor: Any = None,
    executor_factory: Callable[[str], Any] | None = None,
    default_spec: str = "gemini",
    judge_fn: Callable,
    max_retries: int = 2,
    max_workers: int = 4,
    quota_check: Callable[[], int] | None = None,
    quota_threshold: int = 95,
    repo_dir: str | None = None,
    git_runner: Callable[[list[str], str], tuple[int, str]] | None = None,
    test_runner: Callable[[str], str] | None = None,
) -> PlanResult:
```

Then add, right after `result = PlanResult()`:

```python
    # Per-slice executor resolution. If a factory is given, build each slice's executor
    # from its tag (or the build default). Else fall back to the single legacy executor.
    def _executor_for(task: SliceTask):
        if executor_factory is not None:
            return executor_factory(task.executor or default_spec)
        return executor
```

(Leave `_run_one` calling `executor=...` for now — Task 5 wires `_executor_for` into it.)

- [ ] **Step 4: Run to verify it passes + full file**

Run: `python -m pytest tests/test_orchestrator_parallel.py -q -p no:warnings`
Expected: PASS — the new kwargs are accepted, the run completes via the legacy `executor`,
and all existing parallel tests still pass (signature change is additive/backward-compatible).

- [ ] **Step 5: Commit**

```bash
git add src/cld/orchestrator.py tests/test_orchestrator_parallel.py
git commit -m "feat(orchestrator): run_plan_parallel accepts executor_factory + default_spec"
```

---

## Task 5: Resolve executor PER SLICE in _run_one  [CLAUDE]

**Files:**
- Modify: `src/cld/orchestrator.py` (`_run_one`)
- Test: `tests/test_orchestrator_parallel.py` (the per-slice routing test)

- [ ] **Step 1: Write the failing test**

```python
def test_each_slice_uses_its_own_tagged_executor(tmp_path):
    from cld.orchestrator import run_plan_parallel
    from cld.ledger import Ledger
    from cld.executors.base import SliceTask, ExecutorResult

    ran = {}  # slice_id -> spec the executor was built from

    class _Rec:
        def __init__(self, spec): self.spec = spec
        def run(self, task, workdir, feedback=None):
            ran[task.id] = self.spec
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")

    slices = [
        SliceTask(id="T1", brief="b", files=["x"], acceptance_test_path="t.py"),  # default
        SliceTask(id="T2", brief="b", files=["y"], acceptance_test_path="t.py",
                  executor="opencode:opencode/claude-sonnet-4-6"),               # tagged
    ]
    ledger = Ledger(str(tmp_path / "l.json"))
    run_plan_parallel(
        slices, ledger,
        executor_factory=lambda spec: _Rec(spec),
        default_spec="gemini",
        judge_fn=lambda **kw: type("J", (), {"passed": True, "failing_tests": []})(),
        test_runner=lambda *a, **k: "1 passed",
    )
    assert ran["T1"] == "gemini"  # untagged -> build default
    assert ran["T2"] == "opencode:opencode/claude-sonnet-4-6"  # tagged -> its own
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_orchestrator_parallel.py -k each_slice_uses -q -p no:warnings`
Expected: FAIL — `_run_one` still uses the single `executor` (T1/T2 both get it, or a crash since `executor=None`).

- [ ] **Step 3: Wire `_executor_for` into `_run_one`**

In `src/cld/orchestrator.py`, inside `_run_one`, replace the two `executor=executor` arguments
to `deliver_slice` with the per-slice executor:

```python
    def _run_one(task: SliceTask):
        slice_executor = _executor_for(task)
        if repo_dir is not None and git_runner is not None:
            with worktree(repo_dir, f"slice-{task.id}", runner=git_runner) as wt_path:
                res = deliver_slice(
                    task, executor=slice_executor, judge_fn=judge_fn,
                    max_retries=max_retries, workdir=wt_path,
                    test_runner=test_runner,
                )
                if res.accepted:
                    git_runner(["git", "add", "-A"], wt_path)
                    git_runner(
                        ["git", "commit", "-m", f"slice {task.id}: accepted by cld"],
                        wt_path,
                    )
                return res
        return deliver_slice(
            task, executor=slice_executor, judge_fn=judge_fn, max_retries=max_retries,
            test_runner=test_runner,
        )
```

- [ ] **Step 4: Run to verify it passes + full suite**

Run: `python -m pytest tests/test_orchestrator_parallel.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS — T1 used "gemini", T2 used its tag; existing parallel tests still green.

- [ ] **Step 5: Commit**

```bash
git add src/cld/orchestrator.py tests/test_orchestrator_parallel.py
git commit -m "feat(orchestrator): resolve executor per slice (tag or build default)"
```

---

## Task 6: Wire executor_factory in run_delivery.py  [CLAUDE]

**Files:**
- Modify: `skill/scripts/run_delivery.py`
- Test: `tests/test_run_delivery.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_build_executor_factory_resolves_specs():
    # run_delivery exposes a factory that maps a spec -> executor via parse_executor_spec
    # + get_executor, so the orchestrator can build per-slice executors.
    factory = run_delivery.build_executor_factory()
    from cld.executors.gemini import GeminiExecutor
    from cld.executors.opencode import OpenCodeExecutor
    assert isinstance(factory("gemini"), GeminiExecutor)
    assert isinstance(factory("opencode:opencode/claude-sonnet-4-6"), OpenCodeExecutor)
    # tolerant slash form also resolves (no Unknown executor)
    assert isinstance(factory("opencode/deepseek-v4-pro"), OpenCodeExecutor)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_run_delivery.py -k build_executor_factory -q -p no:warnings`
Expected: FAIL — `module 'run_delivery' has no attribute 'build_executor_factory'`.

- [ ] **Step 3: Add the factory + pass it into run_plan_parallel**

In `skill/scripts/run_delivery.py`, add near `parse_executor_spec`:

```python
def build_executor_factory():
    """Return factory(spec) -> executor, resolving a spec via parse_executor_spec +
    get_executor. Used by run_plan_parallel for per-slice executor selection."""
    def factory(spec: str):
        name, kwargs = parse_executor_spec(spec)
        return get_executor(name, **kwargs)
    return factory
```

Then in BOTH `run_plan_parallel(...)` call sites in `main` (the `--step` branch and the
full-run branch), replace `executor=executor,` with the factory + default spec:

```python
        result = run_plan_parallel(
            layer_slices, ledger,
            executor_factory=build_executor_factory(),
            default_spec=args.executor or "gemini",
            judge_fn=judge_fn,
            max_workers=args.workers,
            repo_dir=args.repo, git_runner=git_runner,
            test_runner=pytest_test_runner,
        )
```

(Apply the same swap to the non-`--step` call. The local `executor = get_executor(...)`
lines may be removed since the factory now builds them; keep `exec_name, exec_kwargs =
parse_executor_spec(args.executor)` only if still referenced, else drop.)

- [ ] **Step 4: Run to verify it passes + full suite**

Run: `python -m pytest tests/test_run_delivery.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/run_delivery.py tests/test_run_delivery.py
git commit -m "feat(driver): per-slice executor_factory wired into run_plan_parallel"
```

---

## Task 7: SKILL.md — picker discipline + shortlist + per-slice docs  [CLAUDE]

**Files:**
- Modify: `skill/SKILL.md`

- [ ] **Step 1: Add the picker-frequency + per-slice rules**

In `skill/SKILL.md`, in the picker section (after the GUARD paragraph), add:

```markdown
   **Picker frequency — choose ONCE per build, then STICK.** Present the executor picker
   ONCE, before the first dispatch of a build. That choice is the build default and persists
   for ALL slices and re-dispatches. Do NOT re-run the picker per slice or on a plain
   re-dispatch (the S1b interruption bug) — reuse the executor already chosen. Re-run the
   picker ONLY when the user says "change executor" or starts a new build.

   **Per-slice executor (`executor:` tag).** A `## SLICE:` block may carry an optional
   `executor: <name>:<model>` line; that slice runs on that executor SILENTLY (the tag is the
   decision — no prompt). Untagged slices use the build default. You MAY propose an upgrade
   for a slice you assess as genuinely HARD (a high bar — not routine), ONCE, for the user to
   confirm; every other slice stays silent. This must never become a per-slice picker.

   **Gates on any per-slice metered/untested model** (tag or proposal): a metered model hits
   the cost-confirm before that slice dispatches; an untested one runs
   `cld.validate.resolve_and_validate` first. The $0 flat workhorse stays the silent default.
```

- [ ] **Step 2: Update the picker shortlist example to the curated set**

In the picker example block, ensure the main shortlist shows: gemini workhorse (default),
opencode/gemini-3.1-pro, opencode/kimi-k2.6 (untested → "validate first"),
opencode/claude-sonnet-4-6 (metered), and the `Browse all models…` entry. (Render verbatim
from `render_shortlist` at runtime — the example is illustrative.)

- [ ] **Step 3: Sync the global skill + verify**

Run:
```bash
cp skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
diff -q skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
```
Expected: no diff (identical).

- [ ] **Step 4: Full suite (integration gate)**

Run: `python -m pytest -p no:warnings -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs(skill): picker-once-per-build + per-slice executor rules + curated shortlist"
```

---

## Done criteria (Feature 1)

- A `## SLICE:` `executor:` tag routes that slice to its own model; untagged slices use the build default; one parallel layer can mix executors.
- An unknown per-slice spec fails only THAT slice (clear ValueError), not the build.
- The picker's main shortlist includes kimi-k2.6 + claude-sonnet-4-6 + "Browse all"; gemini workhorse stays default.
- SKILL.md makes the picker choose-once-and-stick, with bounded agent proposals that never reintroduce per-slice prompting.
- Metered/untested per-slice picks still pass cost-confirm + validate-on-demand.
- Full suite green; backward-compatible (plans with no `executor:` behave exactly as before).
