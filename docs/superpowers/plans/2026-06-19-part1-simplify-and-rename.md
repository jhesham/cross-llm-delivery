# Sub-plan 1 — Foundation (simplify + rename + complexity field)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md before stopping. **Read the MASTER plan's Global Constraints first** (`2026-06-19-complexity-routing-MASTER.md`).

**Goal:** Put the neutral status vocabulary in place, delete the unused slice complexity (sub-slices + the old forced per-slice picker), and add the `complexity` data field — leaving a simpler, green engine ready for the routing ladder (sub-plan 2).

**Spec:** `docs/superpowers/specs/2026-06-19-complexity-routing-and-slice-simplification-design.md` (Parts A, B-vocab, F).

**Order:** **T1 + T2 (rename) first**, then T3 / T4 / T5 (independent of each other).

**Builder routing:** T1, T2 = Claude (touches trust logic; rename with strong test pins). T3, T4 = Claude (multi-file structural removals). T5 = DOGFOOD-eligible (pure parse logic) or Claude.

---

## Task 1: Rename status vocab in the catalog + recommend/browse  [Claude]

Rename the model-status strings in `src/cld/models.py` only: `proven`→`verified`, `known-bad`→`revalidate`. `likely`/`untested` are unchanged. Behavior must stay identical (a `revalidate` model is hidden exactly as `known-bad` was; the default workhorse still resolves).

**Files:**
- Modify: `src/cld/models.py` (the `MODEL_METADATA` `headless_status` values; every `"proven"` / `"known-bad"` string literal in `recommend` and `browse_models`)
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: catalog entries + `recommend`/`browse_models` using statuses `verified`/`likely`/`untested`/`revalidate`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_models.py`)

```python
def test_catalog_uses_verified_not_proven():
    from cld.models import MODEL_METADATA
    g = MODEL_METADATA["gemini:gemini-3.1-pro-preview"]
    assert g.headless_status == "verified"
    # no entry may carry the old vocabulary
    assert all(m.headless_status != "proven" for m in MODEL_METADATA.values())
    assert all(m.headless_status != "known-bad" for m in MODEL_METADATA.values())


def test_recommend_hides_revalidate_via_evidence():
    from cld.models import recommend
    recs = recommend(
        available_ids=["opencode/deepseek-v4-flash-free"],
        evidence={"opencode/deepseek-v4-flash-free": "revalidate"},
    )
    assert "opencode/deepseek-v4-flash-free" not in [r.id for r in recs]


def test_recommend_default_workhorse_still_resolves():
    from cld.models import recommend
    recs = recommend(available_ids=["gemini:gemini-3.1-pro-preview"])
    assert any(r.is_default and r.headless_status == "verified" for r in recs)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_models.py -k "verified or revalidate or default_workhorse" -q -p no:warnings`
Expected: FAIL (catalog still says `proven`; `recommend` still filters on `known-bad`).

- [ ] **Step 3: Implement**

In `src/cld/models.py`:
- In every `MODEL_METADATA` entry, change `headless_status="proven"` → `"verified"`. (Currently only `gemini:gemini-3.1-pro-preview`.) Leave `likely`/`untested` entries as-is.
- In `recommend`: change the skip guard `if status == "known-bad":` → `if status == "revalidate":`; and the default-candidate checks `rec.headless_status == "proven"` → `== "verified"` (both occurrences).
- In `browse_models`: change any `"known-bad"` comparison → `"revalidate"` and any `"proven"` → `"verified"`.
- Grep to be exhaustive: `grep -n '"proven"\|"known-bad"' src/cld/models.py` must return nothing after.

- [ ] **Step 4: Run + full suite**

Run: `python -m pytest tests/test_models.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS. (Existing tests that asserted old strings: update them to the new vocab — search `tests/` for `"proven"`/`"known-bad"` and fix to `"verified"`/`"revalidate"`.)

- [ ] **Step 5: Commit**

```bash
git add src/cld/models.py tests/test_models.py
git commit -m "refactor(models): status vocab proven->verified, known-bad->revalidate (catalog + recommend/browse)"
```

---

## Task 2: Rename + auto-migrate status in evidence + validate  [Claude]

Rename the verdict strings in `src/cld/evidence.py` and `src/cld/validate.py`, and **migrate legacy verdicts on load** so existing `~/.cld/validation-evidence.json` files (which contain `known-bad`/`proven`) keep working — mapped to `revalidate`/`verified`.

**Files:**
- Modify: `src/cld/evidence.py` (`_load` migration; `record` accepts new values)
- Modify: `src/cld/validate.py` (`ValidationResult.status`, `validate_model`, `resolve_and_validate` strings + messages)
- Test: `tests/test_evidence.py` (create if absent), `tests/test_validate.py`

**Interfaces:**
- Consumes: the renamed catalog statuses from Task 1.
- Produces: `EvidenceStore` reads/writes `verified`/`revalidate`; legacy values auto-migrated on load. `validate_model` returns status `verified`/`revalidate`/`untested`. `resolve_and_validate` uses the new vocab.

- [ ] **Step 1: Write the failing tests**

`tests/test_evidence.py` (append/create):
```python
import json
from cld.evidence import EvidenceStore


def test_legacy_verdicts_migrate_on_load(tmp_path):
    p = tmp_path / "ev.json"
    p.write_text(json.dumps({
        "opencode/kimi-k2.6": {"status": "known-bad", "note": "x", "validated_at": "t"},
        "gemini:gemini-3.1-pro-preview": {"status": "proven", "note": "", "validated_at": "t"},
    }), encoding="utf-8")
    st = EvidenceStore(path=p).statuses()
    assert st["opencode/kimi-k2.6"] == "revalidate"
    assert st["gemini:gemini-3.1-pro-preview"] == "verified"


def test_records_new_vocab_roundtrip(tmp_path):
    p = tmp_path / "ev.json"
    s = EvidenceStore(path=p)
    s.record("m/x", "revalidate", note="failed our slice")
    s.record("m/y", "verified")
    st = EvidenceStore(path=p).statuses()
    assert st == {"m/x": "revalidate", "m/y": "verified"}
```

`tests/test_validate.py` (append):
```python
def test_validate_model_uses_new_vocab(tmp_path):
    # a fake executor that produces NO passing code -> revalidate (not "known-bad")
    from cld.validate import validate_model
    from cld.executors.base import ExecutorResult

    class _Noop:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="", files_changed=[], raw_log="")

    def git(args, cwd):
        import subprocess
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return (p.returncode, (p.stdout or "") + (p.stderr or ""))

    res = validate_model("fake", executor=_Noop(), git_runner=git, base_dir=str(tmp_path))
    assert res.status == "revalidate"   # was "known-bad"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_evidence.py tests/test_validate.py -k "migrate or new_vocab" -q -p no:warnings`
Expected: FAIL (migration absent; `validate_model` returns `known-bad`).

- [ ] **Step 3: Implement**

In `src/cld/evidence.py` `_load`, after parsing the dict, migrate each record's `status`:
```python
        _MIGRATE = {"proven": "verified", "known-bad": "revalidate"}
        for rec in data.values():
            if isinstance(rec, dict) and rec.get("status") in _MIGRATE:
                rec["status"] = _MIGRATE[rec["status"]]
        return data
```
(Migration is read-time; the file is rewritten with new values on the next `record`.)

In `src/cld/validate.py`:
- `validate_model`: the pass return uses `status="verified"` (was `"proven"`); the fail return uses `status="revalidate"` (was `"known-bad"`); executor-error/dispatch-fail stays `"untested"`.
- `resolve_and_validate`: replace every `"proven"`→`"verified"` and `"known-bad"`→`"revalidate"` (the early evidence-record checks, the `status in (...)` checks, the `evidence_store.record(...)` calls, and the `ResolveResult(...)` statuses). Update user-facing messages: e.g. `"{spec}: NOT headless-capable..."` → `"{spec}: did not complete our validation slice — re-validate or pick another model."`; `"known-bad in catalog"` → `"marked revalidate in catalog"`; `"marked known-bad this session"` → `"marked revalidate this session"`.
- Grep gate: `grep -rn '"proven"\|"known-bad"' src/cld/validate.py src/cld/evidence.py` returns nothing after.

- [ ] **Step 4: Run + full suite**

Run: `python -m pytest tests/test_evidence.py tests/test_validate.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS. (Fix any existing validate/evidence tests asserting old strings.)

- [ ] **Step 5: Commit**

```bash
git add src/cld/evidence.py src/cld/validate.py tests/test_evidence.py tests/test_validate.py
git commit -m "refactor(evidence,validate): new status vocab + lossless legacy migration on load"
```

---

## Task 3: Remove sub-slices  [Claude]

Delete the one-level sub-slice feature entirely (Part 4): the `SliceTask` fields, the `## SUBSLICE:` parse + round-trip, the orchestrator child-execution path, and the usage nesting.

**Files:**
- Modify: `src/cld/executors/base.py` (drop `parent_id`, `subslices`)
- Modify: `src/cld/plan/slice.py` (drop `## SUBSLICE:` handling; `_dict_to_slice` drops `parent_id`/`subslices`; `slices_to_markdown` drops the subslice emission)
- Modify: `src/cld/orchestrator.py` (drop `_run_subslices` + the `if task.subslices:` dispatch at the top of `_run_one`)
- Modify: `src/cld/usage.py` (drop the `children_by_parent` nesting; render a flat row per ledger entry)
- Tests: delete the sub-slice tests in `tests/test_slice.py`, `tests/executors/test_base.py`, `tests/test_orchestrator_parallel.py`, `tests/test_usage.py`

- [ ] **Step 1: Write the failing test** (proves sub-slice syntax is gone) — append to `tests/test_slice.py`:

```python
def test_subslice_marker_is_not_special_anymore():
    # "## SUBSLICE:" lines must no longer create children; only top-level slices parse.
    from cld.plan.slice import load_slices
    md = ("## SLICE: P1\nbrief: p\nfiles: a.py\nacceptance_test_path: t.py\ndeps:\n\n"
          "## SUBSLICE: P1a\nbrief: c\nfiles: b.py\nacceptance_test_path: t.py\n")
    slices = load_slices(md)
    assert [s.id for s in slices] == ["P1"]          # P1a is NOT parsed as anything
    assert not hasattr(slices[0], "subslices")        # field removed
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_slice.py -k subslice_marker_is_not -q -p no:warnings`
Expected: FAIL (`subslices` still exists / `## SUBSLICE:` still parsed).

- [ ] **Step 3: Implement the removals**

- `executors/base.py`: delete the `parent_id` and `subslices` lines from `SliceTask`.
- `plan/slice.py`: delete the `elif line.startswith("## SUBSLICE:")` branch and any `current_subslice` handling; restore `_dict_to_slice` to NOT pass `parent_id`/`subslices`; restore `slices_to_markdown` to emit only `## SLICE:` blocks (delete the `for sub in s.subslices:` emission and the `_append_slice_fields` subslice use if it was only for that — keep the shared field-emitter if still used by the slice path).
- `orchestrator.py`: delete the nested `_run_subslices` function and the `if task.subslices: return _run_subslices(task)` guard at the top of `_run_one` (and the worker-thread NOTE comment specific to it if now stale).
- `usage.py`: in `render_usage_table`, delete the `children_by_parent` grouping + the `ordered`/`is_child` indentation logic; iterate `ledger.entries.values()` and emit one flat row each (keep the build-total sum + the account blocks).

- [ ] **Step 4: Delete now-obsolete tests, then run full suite**

Delete: `test_subslices_parsed_under_parent`, `test_subslices_round_trip` (test_slice.py); `test_slicetask_subslices_and_parent_id_default_empty`, `test_slicetask_subslices_default_not_shared` (test_base.py); `test_parent_runs_subslices_each_with_own_executor`, `test_failed_subslice_fails_only_itself_and_parent_incomplete`, `test_resolved_spec_recorded_in_ledger_per_slice`'s subslice parts, `test_empty_subslices_list_runs_as_leaf`, `test_failed_child_id_in_parent_detail`, `test_effort_recorded_from_spec_suffix` if it relies on subslices (keep effort recording test if it doesn't) (test_orchestrator_parallel.py); `test_usage_nests_subslices_under_parent`, `test_usage_nesting_robust_to_out_of_order_entries`, `test_usage_orphan_child_without_parent_still_rendered` (test_usage.py).

Run: `python -m pytest -p no:warnings -q`
Expected: PASS (leaf behavior unchanged; no subslice references remain). Grep gate: `grep -rn "subslice\|SUBSLICE\|parent_id" src/cld` returns nothing.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(slice): remove sub-slices (fields, parse, orchestrator path, usage nesting)"
```

---

## Task 4: Remove the old forced per-slice picker  [Claude]

Delete the Part-3 per-slice review hook: `slice_pick_fn` (orchestrator) and `make_slice_pick_fn` / `--per-slice-pick` (run_delivery). (Its concept returns, opt-in, in sub-plan 3 — but the old implementation goes now.)

**Files:**
- Modify: `src/cld/orchestrator.py` (drop `slice_pick_fn` param from `run_plan`/`run_plan_parallel`; `_resolve_spec` reverts to `tag > default_spec`)
- Modify: `skill/scripts/run_delivery.py` (drop `make_slice_pick_fn`, the `--per-slice-pick` arg, and the `slice_pick_fn=...` wiring at both `run_plan_parallel` call sites)
- Tests: delete the per-slice-pick tests in `tests/test_run_delivery.py` and `tests/test_orchestrator_parallel.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_run_delivery.py`:

```python
def test_per_slice_pick_removed():
    import skill.scripts.run_delivery as rd
    assert not hasattr(rd, "make_slice_pick_fn")
    # --per-slice-pick no longer a recognised flag
    import pytest
    with pytest.raises(SystemExit):
        rd.main(["plan.md", "--per-slice-pick"])
```
(If the test harness imports run_delivery differently, mirror the existing import style in that file.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_run_delivery.py -k per_slice_pick_removed -q -p no:warnings`
Expected: FAIL (`make_slice_pick_fn` still present; flag still accepted).

- [ ] **Step 3: Implement the removals**

- `orchestrator.py`: remove `slice_pick_fn` from both signatures; in `_resolve_spec` delete the `elif slice_pick_fn is not None:` branch so it reads: tag wins, else `default_spec`. Remove the worker-thread NOTE comment about interactive pick_fn (now moot).
- `run_delivery.py`: delete `make_slice_pick_fn`; delete the `p.add_argument("--per-slice-pick", ...)` line; delete `slice_pick_fn=make_slice_pick_fn(args.per_slice_pick)` from both `run_plan_parallel(...)` calls; drop the now-unused `import threading` if nothing else uses it.

- [ ] **Step 4: Delete obsolete tests + global sync + full suite**

Delete from `tests/test_run_delivery.py`: `test_per_slice_pick_off_returns_none`, `test_per_slice_pick_on_returns_callable`, `test_per_slice_pick_non_interactive_falls_back_to_default`, `test_per_slice_pick_interactive_uses_picker`, `test_per_slice_pick_interactive_empty_falls_back`. Delete from `tests/test_orchestrator_parallel.py`: `test_slice_pick_fn_used_for_untagged_only`, `test_slice_pick_fn_none_return_falls_back_to_default` (keep `test_no_slice_pick_fn_is_current_behavior` only if it still passes without the param — otherwise delete).

```bash
cp skill/scripts/run_delivery.py ~/.claude/skills/cross-llm-delivery/scripts/run_delivery.py
diff -q skill/scripts/run_delivery.py ~/.claude/skills/cross-llm-delivery/scripts/run_delivery.py
```
Run: `python -m pytest -p no:warnings -q`
Expected: PASS. Grep gate: `grep -rn "slice_pick_fn\|per_slice_pick\|make_slice_pick_fn" src/ skill/` returns nothing.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old forced per-slice picker (slice_pick_fn + --per-slice-pick)"
```

---

## Task 5: Add the `complexity` data field  [DOGFOOD-eligible]

Add `complexity` to `SliceTask` (default `standard`) and parse an optional `complexity:` line in the plan. Data only — nothing routes on it yet (that's sub-plan 2).

**Files:**
- Modify: `src/cld/executors/base.py` (add `complexity: str = "standard"`)
- Modify: `src/cld/plan/slice.py` (parse `complexity:`; emit it in `slices_to_markdown`)
- Test: `tests/executors/test_base.py`, `tests/test_slice.py`

**Interfaces:**
- Produces: `SliceTask.complexity` ∈ {`easy`,`standard`,`complex`}, default `standard`.

- [ ] **Step 1: Write the failing tests**

`tests/executors/test_base.py` (append):
```python
def test_slicetask_complexity_defaults_standard():
    t = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    assert t.complexity == "standard"
    t2 = SliceTask(id="T2", brief="b", files=["x"], acceptance_test_path="t.py", complexity="complex")
    assert t2.complexity == "complex"
```

`tests/test_slice.py` (append):
```python
def test_complexity_parsed_and_defaulted():
    from cld.plan.slice import load_slices
    md = ("## SLICE: A\nbrief: a\nfiles: a.py\nacceptance_test_path: t.py\ncomplexity: easy\ndeps:\n\n"
          "## SLICE: B\nbrief: b\nfiles: b.py\nacceptance_test_path: t.py\ndeps: A\n")
    s = {x.id: x for x in load_slices(md)}
    assert s["A"].complexity == "easy"
    assert s["B"].complexity == "standard"   # omitted -> default


def test_complexity_round_trips():
    from cld.plan.slice import load_slices, slices_to_markdown
    md = "## SLICE: A\nbrief: a\nfiles: a.py\nacceptance_test_path: t.py\ncomplexity: complex\ndeps:\n"
    s = {x.id: x for x in load_slices(slices_to_markdown(load_slices(md)))}
    assert s["A"].complexity == "complex"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/executors/test_base.py tests/test_slice.py -k complexity -q -p no:warnings`
Expected: FAIL (unexpected kwarg / attr missing).

- [ ] **Step 3: Implement**

- `executors/base.py`: add `complexity: str = "standard"` to `SliceTask` (after `executor`).
- `plan/slice.py`: in the field-parsing branch add `elif key == "complexity": current_slice["complexity"] = val`; in `_dict_to_slice` pass `complexity=d.get("complexity", "standard")`; in `slices_to_markdown` emit `complexity:` only when it's not the default (`if s.complexity != "standard": lines.append(f"complexity: {s.complexity}")`) so unchanged plans round-trip cleanly.

- [ ] **Step 4: Run + full suite**

Run: `python -m pytest tests/executors/test_base.py tests/test_slice.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cld/executors/base.py src/cld/plan/slice.py tests/executors/test_base.py tests/test_slice.py
git commit -m "feat(slice): add complexity field (easy/standard/complex, default standard) + parse/round-trip"
```

---

## Done criteria (Sub-plan 1)
- Status vocab is `verified`/`likely`/`untested`/`revalidate` everywhere; legacy evidence files auto-migrate losslessly; no `proven`/`known-bad` strings remain in `src/`.
- Sub-slices and the old forced per-slice picker are fully removed (no references in `src/` or `skill/`); leaf-slice behavior unchanged; global skill copy synced.
- `SliceTask.complexity` exists (default `standard`) and parses/round-trips; nothing routes on it yet.
- Full suite green. Update STATUS.md: Sub-plan 1 done → Next = Sub-plan 2 Task 1.
