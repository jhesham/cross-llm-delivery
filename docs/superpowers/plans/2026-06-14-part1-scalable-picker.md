# Part 1 — Scalable Picker + Effort Axis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md before stopping.

**Goal:** A unified model index with an effort axis, a headless-only filter (default on), executor→provider→model→effort drill-down rendering, top-N-per-provider curation, and fuzzy search — built and tested against the current 46 OpenCode models (Cursor feeds it in Part 2).

**Architecture:** Everything new lives in `src/cld/models.py` (the picker's single source of truth) as pure functions over a new `ModelChoice` dataclass. No executor/orchestrator changes in Part 1. The chat/CLI surfaces render VERBATIM from these functions (the no-improvising guard).

**Tech Stack:** Python 3.11+ stdlib, pytest with fakes (no live CLI calls).

**Spec:** `docs/superpowers/specs/2026-06-14-scalable-picker-and-cursor-design.md` (Part 1)

**Builder routing:** T1 `ModelChoice`+`_provider_of` expansion = CLAUDE (core type). T2 `build_model_index` = DOGFOOD (Gemini). T3 `browse_filter` = DOGFOOD (Gemini). T4 `rank_provider_models` (effort collapse) = DOGFOOD (Gemini). T5 nav render fns = CLAUDE (the verbatim-guard surface). T6 `search_models` = DOGFOOD (Gemini). T7 `spec_with_effort` + `parse_executor_spec @effort` = CLAUDE (spec contract). T8 SKILL.md + global sync = CLAUDE.

---

## File Structure
- **Modify `src/cld/models.py`** — add `ModelChoice`, expand `KNOWN_PROVIDERS`/`_provider_of`,
  `build_model_index`, `browse_filter`, `rank_provider_models`, nav render fns, `search_models`,
  `spec_with_effort`.
- **Modify `skill/scripts/run_delivery.py`** — extend `parse_executor_spec` for `@effort`.
- **Create `tests/test_model_index.py`** — index/filter/rank/search/effort tests.
- **Modify `skill/SKILL.md`** — browse drill-down + search + effort + headless-filter rules; sync global.

Reused: `EvidenceStore.statuses()` (overlay), existing `list_models`, `MODEL_METADATA`, `_spec_for`.

---

## Task 1: `ModelChoice` dataclass + expanded provider detection  [CLAUDE]

**Files:** Modify `src/cld/models.py`; Test `tests/test_model_index.py` (create)

- [ ] **Step 1: Write the failing test**
```python
# tests/test_model_index.py
from cld.models import ModelChoice, _provider_of


def test_modelchoice_fields():
    c = ModelChoice(spec="cursor:composer-2.5", executor="cursor", provider="other",
                    model="composer-2.5", label="Composer 2.5", cost_class="cheap-metered",
                    headless_status="untested", efforts=["low", "high"], default_effort="high")
    assert c.spec == "cursor:composer-2.5" and c.efforts == ["low", "high"]
    assert c.default_effort == "high"


def test_provider_of_recognizes_more_providers():
    assert _provider_of("opencode/grok-build-0.1") == "grok"
    assert _provider_of("opencode/kimi-k2.6") == "kimi"
    assert _provider_of("opencode/qwen3.5-plus") == "qwen"
    assert _provider_of("opencode/glm-5") == "glm"
    assert _provider_of("opencode/minimax-m2.5") == "minimax"
    assert _provider_of("opencode/claude-opus-4-8") == "claude"
    assert _provider_of("opencode/big-pickle") == "other"
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_model_index.py -q -p no:warnings`
Expected: FAIL — `cannot import name 'ModelChoice'`.

- [ ] **Step 3: Implement**
In `src/cld/models.py`, expand the provider tuple and add the dataclass:
```python
KNOWN_PROVIDERS = ("claude", "gpt", "gemini", "deepseek", "grok", "kimi", "qwen", "glm", "minimax")


@dataclass
class ModelChoice:
    spec: str
    executor: str
    provider: str
    model: str
    label: str
    cost_class: str
    headless_status: str
    efforts: list = field(default_factory=list)
    default_effort: str | None = None
```
(`field` is already imported in models.py via `from dataclasses import dataclass, field`? If not,
ensure the import includes `field`.) Leave `_provider_of` logic as-is — expanding `KNOWN_PROVIDERS`
is enough since it already returns the token if in the tuple else "other".

- [ ] **Step 4: Run to verify it passes + full suite**
Run: `python -m pytest tests/test_model_index.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS; full suite green (~228).

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_model_index.py
git commit -m "feat(picker): ModelChoice dataclass + expanded provider detection"
```

---

## Task 2: `build_model_index`  [DOGFOOD — Gemini]

**Files:** Modify `src/cld/models.py`; Test `tests/test_model_index.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
from cld.models import build_model_index


def test_build_index_merges_opencode_and_gemini_with_evidence():
    idx = build_model_index(
        opencode_ids=["opencode/deepseek-v4-pro", "opencode/gpt-5"],
        cursor_models=[],  # part 2 supplies these
        evidence={"opencode/deepseek-v4-pro": "proven"})
    by_spec = {c.spec: c for c in idx}
    # gemini workhorse always present (catalog)
    assert "gemini:gemini-3.1-pro-preview" in by_spec
    # opencode ids present, evidence overlay applied
    ds = by_spec["opencode:opencode/deepseek-v4-pro"]
    assert ds.executor == "opencode" and ds.provider == "deepseek"
    assert ds.headless_status == "proven"  # from evidence overlay
    # an uncatalogued opencode id -> untested/metered-unknown, provider classified
    gpt = by_spec["opencode:opencode/gpt-5"]
    assert gpt.provider == "gpt" and gpt.headless_status == "untested"
    assert gpt.cost_class == "metered-unknown"


def test_build_index_no_cursor_has_empty_efforts():
    idx = build_model_index(opencode_ids=["opencode/gpt-5"], cursor_models=[], evidence={})
    gpt = next(c for c in idx if c.spec == "opencode:opencode/gpt-5")
    assert gpt.efforts == [] and gpt.default_effort is None  # opencode plain = no effort axis here
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_model_index.py -k build_index -q -p no:warnings`
Expected: FAIL — `cannot import name 'build_model_index'`.

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**
Brief (locked Gemini form): add `build_model_index(*, opencode_ids, cursor_models, evidence)
-> list[ModelChoice]` to `src/cld/models.py`, stdlib only, until the build_index tests pass:
- Start an empty list. Always include the gemini workhorse from `MODEL_METADATA`
  (`gemini:gemini-3.1-pro-preview`) as a ModelChoice (executor="gemini", provider="gemini",
  model/label from the catalog entry, its cost_class, headless_status via evidence-or-catalog,
  efforts=[], default_effort=None).
- For each opencode id: spec = `f"opencode:{id}"`, executor="opencode",
  provider=`_provider_of(id)`, model=id split after the last "/", label=model. If the id is in
  MODEL_METADATA use its cost_class/headless_status (then apply evidence overlay); else
  cost_class = "free" if id endswith "-free" else "metered-unknown", headless_status="untested".
  Apply evidence overlay (evidence.get(id) wins over the static status). efforts=[], default=None.
- `cursor_models` param: a list of (id, label) tuples — for Part 1 it's empty; if provided, group
  by base model (Part 2 fills this in; for now, if non-empty, create one ModelChoice per tuple
  with executor="cursor", provider=_provider_of(id), efforts=[], default=None). Keep it simple;
  Part 2 will replace the cursor branch with effort grouping.
- Skip any id whose resolved headless_status == "known-bad".
- Return the list.
Dispatch via gemini CLI, judge with independent pytest.

- [ ] **Step 4: Judge — run independently**
Run: `python -m pytest tests/test_model_index.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit (dogfood merge)**
```bash
git add src/cld/models.py tests/test_model_index.py
git commit -m "feat(picker): build_model_index unified index (Gemini-built, Claude-judged)"
```

---

## Task 3: `browse_filter` (headless-only default ON)  [DOGFOOD — Gemini]

**Files:** Modify `src/cld/models.py`; Test `tests/test_model_index.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
from cld.models import browse_filter


def _choice(spec, status):
    return ModelChoice(spec=spec, executor="opencode", provider="gpt", model="m",
                       label="m", cost_class="metered-unknown", headless_status=status)


def test_browse_filter_default_hides_untested_and_known_bad():
    cs = [_choice("a", "proven"), _choice("b", "likely"),
          _choice("c", "untested"), _choice("d", "known-bad")]
    kept = [c.spec for c in browse_filter(cs)]  # default headless_only=True
    assert kept == ["a", "b"]


def test_browse_filter_show_all_keeps_untested_but_not_known_bad():
    cs = [_choice("a", "proven"), _choice("c", "untested"), _choice("d", "known-bad")]
    kept = [c.spec for c in browse_filter(cs, headless_only=False)]
    assert kept == ["a", "c"]  # known-bad always hidden
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_model_index.py -k browse_filter -q -p no:warnings`
Expected: FAIL — `cannot import name 'browse_filter'`.

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**
Brief: add `browse_filter(choices, *, headless_only=True) -> list[ModelChoice]` to models.py:
always drop `headless_status == "known-bad"`; when headless_only is True ALSO drop everything
except `proven`/`likely`. Return the filtered list, order preserved. stdlib only.

- [ ] **Step 4: Judge**
Run: `python -m pytest tests/test_model_index.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_model_index.py
git commit -m "feat(picker): browse_filter headless-only default (Gemini-built, Claude-judged)"
```

---

## Task 4: `rank_provider_models` (effort-collapse, top-N)  [DOGFOOD — Gemini]

**Files:** Modify `src/cld/models.py`; Test `tests/test_model_index.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
from cld.models import rank_provider_models


def test_rank_orders_proven_first_and_caps():
    cs = [_choice(f"m{i}", "untested") for i in range(15)]
    cs.insert(7, _choice("PROVEN", "proven"))
    cs.insert(3, _choice("LIKELY", "likely"))
    ranked = rank_provider_models(cs, n=5)
    assert ranked[0].spec == "PROVEN"      # proven first
    assert ranked[1].spec == "LIKELY"      # then likely
    assert len(ranked) == 5                # capped


def test_rank_is_base_models_only_no_effort_rows():
    # base models already have efforts as a list; ranking must NOT split them into rows
    base = ModelChoice(spec="cursor:claude-opus-4-8", executor="cursor", provider="claude",
                       model="claude-opus-4-8", label="Opus 4.8", cost_class="metered-unknown",
                       headless_status="likely", efforts=["low", "medium", "high"], default_effort="high")
    ranked = rank_provider_models([base], n=12)
    assert len(ranked) == 1 and ranked[0].efforts == ["low", "medium", "high"]
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_model_index.py -k rank -q -p no:warnings`
Expected: FAIL — `cannot import name 'rank_provider_models'`.

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**
Brief: add `rank_provider_models(choices, *, n=12) -> list[ModelChoice]`: stable-sort the choices
by headless_status priority (proven=0, likely=1, untested=2, anything else=3), preserving input
order within a tier; return the first n. Do NOT expand efforts into separate entries — each
ModelChoice already represents one base model with its efforts list intact. stdlib only.
(Note: effort GROUPING happens in build_model_index/Part 2; this function only ranks+caps base
choices.)

- [ ] **Step 4: Judge**
Run: `python -m pytest tests/test_model_index.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_model_index.py
git commit -m "feat(picker): rank_provider_models proven-first top-N (Gemini-built, Claude-judged)"
```

---

## Task 5: Navigation render functions  [CLAUDE]

**Files:** Modify `src/cld/models.py`; Test `tests/test_model_index.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
from cld.models import (render_executor_level, render_provider_level,
                        render_model_level, render_effort_level)


def _idx():
    return build_model_index(
        opencode_ids=["opencode/deepseek-v4-pro", "opencode/gpt-5"], cursor_models=[],
        evidence={"opencode/deepseek-v4-pro": "proven"})


def test_executor_level_lists_executors_and_search():
    lines, ordered = render_executor_level(_idx())
    blob = "\n".join(lines)
    assert "gemini" in blob and "opencode" in blob
    assert any("Search" in l for l in lines)
    assert "gemini" in ordered and "opencode" in ordered


def test_provider_level_lists_providers_under_executor():
    lines, ordered = render_provider_level(_idx(), executor="opencode")
    assert "deepseek" in ordered and "gpt" in ordered
    assert any("Search" in l for l in lines)


def test_model_level_topN_plus_more_and_search():
    lines, ordered = render_model_level(_idx(), executor="opencode", provider="deepseek")
    assert any("deepseek-v4-pro" in l for l in lines)
    assert any("Search" in l for l in lines)
    # round-trip: each numbered line maps to ordered[n-1].spec
    import re
    for l in lines:
        m = re.match(r"\s*(\d+)\)\s+(\S+)", l)
        if m:
            assert m.group(2) == ordered[int(m.group(1)) - 1].spec


def test_effort_level_only_when_efforts_present():
    base = ModelChoice(spec="cursor:claude-opus-4-8", executor="cursor", provider="claude",
                       model="claude-opus-4-8", label="Opus", cost_class="metered-unknown",
                       headless_status="likely", efforts=["low", "high"], default_effort="high")
    lines, ordered = render_effort_level(base)
    assert ordered == ["low", "high"]
    assert any("high" in l and "default" in l.lower() for l in lines)  # default marked
    # a model with no efforts -> empty (caller skips the effort step)
    plain = ModelChoice(spec="opencode:opencode/gpt-5", executor="opencode", provider="gpt",
                        model="gpt-5", label="gpt-5", cost_class="metered-unknown",
                        headless_status="untested")
    lines2, ordered2 = render_effort_level(plain)
    assert ordered2 == []


def test_nav_render_cp1252_safe():
    for fn_lines in (render_executor_level(_idx())[0],
                     render_provider_level(_idx(), executor="opencode")[0],
                     render_model_level(_idx(), executor="opencode", provider="gpt")[0]):
        "\n".join(fn_lines).encode("cp1252")
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_model_index.py -k "level or nav_render" -q -p no:warnings`
Expected: FAIL — `cannot import name 'render_executor_level'`.

- [ ] **Step 3: Implement (Claude — this is the verbatim-guard surface, so author directly)**
Add to `src/cld/models.py`:
```python
def render_executor_level(index):
    execs = []
    for c in index:
        if c.executor not in execs:
            execs.append(c.executor)
    lines = ["Choose an executor:"]
    for i, e in enumerate(execs, 1):
        n = sum(1 for c in index if c.executor == e)
        lines.append(f"  {i}) {e}   ({n} models)")
    lines.append("  S) Search models...")
    return lines, execs


def render_provider_level(index, *, executor):
    provs = []
    for c in index:
        if c.executor == executor and c.provider not in provs:
            provs.append(c.provider)
    provs.sort()
    lines = [f"{executor} - choose a provider:"]
    for i, p in enumerate(provs, 1):
        n = sum(1 for c in index if c.executor == executor and c.provider == p)
        lines.append(f"  {i}) {p}   ({n})")
    lines.append("  S) Search models...")
    return lines, provs


def render_model_level(index, *, executor, provider, headless_only=True, n=12):
    pool = [c for c in index if c.executor == executor and c.provider == provider]
    pool = browse_filter(pool, headless_only=headless_only)
    ranked = rank_provider_models(pool, n=n)
    lines = [f"{executor}/{provider} - choose a model:"]
    ordered = []
    for i, c in enumerate(ranked, 1):
        ordered.append(c)
        eff = f"  efforts: {','.join(c.efforts)}" if c.efforts else ""
        warn = "  (!) untested" if c.headless_status == "untested" else ""
        lines.append(f"  {i}) {c.spec:42s} {c.cost_class:16s} {c.headless_status:8s}{eff}{warn}")
    if len(pool) > len(ranked):
        lines.append(f"  M) More... ({len(pool) - len(ranked)} more)")
    lines.append("  S) Search models...")
    return lines, ordered


def render_effort_level(choice):
    if not choice.efforts:
        return [], []
    lines = [f"{choice.label} - choose effort:"]
    for i, e in enumerate(choice.efforts, 1):
        mark = "  (default)" if e == choice.default_effort else ""
        lines.append(f"  {i}) {e}{mark}")
    return lines, list(choice.efforts)
```

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/test_model_index.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_model_index.py
git commit -m "feat(picker): executor/provider/model/effort drill-down render fns"
```

---

## Task 6: `search_models` (fuzzy, labeled by source)  [DOGFOOD — Gemini]

**Files:** Modify `src/cld/models.py`; Test `tests/test_model_index.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
from cld.models import search_models


def test_search_compo_matches_only_via_substring():
    idx = build_model_index(opencode_ids=["opencode/deepseek-v4-pro"],
                            cursor_models=[("composer-2.5", "Composer 2.5")], evidence={})
    res = search_models(idx, "compo", headless_only=False)
    assert any("composer" in c.model.lower() for c in res)
    assert all("composer" in (c.model + c.label).lower() for c in res)


def test_search_31_matches_multiple_routings_labeled():
    idx = build_model_index(opencode_ids=["opencode/gemini-3.1-pro"], cursor_models=[], evidence={})
    res = search_models(idx, "3.1", headless_only=False)
    specs = {c.spec for c in res}
    assert "gemini:gemini-3.1-pro-preview" in specs  # google direct
    assert "opencode:opencode/gemini-3.1-pro" in specs  # via opencode
    # each carries its executor so they disambiguate
    assert {c.executor for c in res} >= {"gemini", "opencode"}


def test_search_respects_headless_filter_and_empty():
    idx = build_model_index(opencode_ids=["opencode/gpt-5"], cursor_models=[], evidence={})
    assert search_models(idx, "gpt-5", headless_only=True) == []  # untested hidden
    assert search_models(idx, "zzz-nomatch", headless_only=False) == []
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_model_index.py -k search -q -p no:warnings`
Expected: FAIL — `cannot import name 'search_models'`.

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**
Brief: add `search_models(index, query, *, headless_only=True) -> list[ModelChoice]`:
lowercase query; first apply `browse_filter(index, headless_only=headless_only)`; keep choices
where the lowercased query is a substring of any of `spec, provider, executor, model, label`
(joined/checked individually). Rank results: exact `model`-id match first, then `model` startswith
query, then other substring matches; within a tier keep input order. Return the ranked list ([]
if none). stdlib only.

- [ ] **Step 4: Judge**
Run: `python -m pytest tests/test_model_index.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_model_index.py
git commit -m "feat(picker): search_models fuzzy substring over id/provider/executor (Gemini-built, Claude-judged)"
```

---

## Task 7: `spec_with_effort` + `parse_executor_spec` `@effort`  [CLAUDE]

**Files:** Modify `src/cld/models.py` (spec_with_effort), `skill/scripts/run_delivery.py` (parse);
Test `tests/test_model_index.py` + `tests/test_run_delivery.py`

- [ ] **Step 1: Write the failing tests**
Append to `tests/test_model_index.py`:
```python
from cld.models import spec_with_effort


def test_spec_with_effort_appends_at_marker():
    base = ModelChoice(spec="cursor:claude-opus-4-8", executor="cursor", provider="claude",
                       model="claude-opus-4-8", label="Opus", cost_class="metered-unknown",
                       headless_status="likely", efforts=["low", "medium"], default_effort="medium")
    assert spec_with_effort(base, "low") == "cursor:claude-opus-4-8@low"
    # choosing the default effort omits the @marker (= CLI default)
    assert spec_with_effort(base, "medium") == "cursor:claude-opus-4-8"
    # no effort / None -> bare spec
    assert spec_with_effort(base, None) == "cursor:claude-opus-4-8"
```
Append to `tests/test_run_delivery.py`:
```python
def test_parse_executor_spec_splits_effort_marker():
    assert parse_executor_spec("cursor:claude-opus-4-8@low") == (
        "cursor", {"model": "claude-opus-4-8", "effort": "low"})
    assert parse_executor_spec("opencode:opencode/gpt-5@high") == (
        "opencode", {"model": "opencode/gpt-5", "effort": "high"})
    # no @ -> unchanged behavior (back-compat)
    assert parse_executor_spec("gemini:gemini-3.1-pro-preview") == (
        "gemini", {"model": "gemini-3.1-pro-preview"})
```

- [ ] **Step 2: Run to verify both fail**
Run: `python -m pytest tests/test_model_index.py -k spec_with_effort tests/test_run_delivery.py -k effort_marker -q -p no:warnings`
Expected: FAIL (ImportError / wrong tuple).

- [ ] **Step 3: Implement**
In `src/cld/models.py`:
```python
def spec_with_effort(choice, effort) -> str:
    """The choice's base spec, plus @<effort> UNLESS effort is None or the CLI default
    (default = bare spec, so the CLI's own default applies)."""
    if not effort or effort == choice.default_effort:
        return choice.spec
    return f"{choice.spec}@{effort}"
```
In `skill/scripts/run_delivery.py`, extend `parse_executor_spec` to split a trailing `@effort`
BEFORE the existing name/model parsing:
```python
def parse_executor_spec(spec: str) -> tuple[str, dict]:
    spec = (spec or "gemini").strip()
    effort = None
    if "@" in spec:
        spec, effort = spec.rsplit("@", 1)
        spec, effort = spec.strip(), effort.strip() or None
    # ... existing colon / slash parsing produces (name, kwargs) ...
    name, kwargs = _parse_name_model(spec)   # refactor existing body into this helper
    if effort:
        kwargs["effort"] = effort
    return name, kwargs
```
(Refactor the existing colon/slash logic into a `_parse_name_model(spec)` helper that returns
`(name, kwargs)`; the public function wraps it with the `@effort` split. Keep all existing
behavior identical when there's no `@`.)

- [ ] **Step 4: Run both + full suite**
Run: `python -m pytest tests/test_model_index.py tests/test_run_delivery.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS (existing parse_executor_spec tests still green — back-compat).

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py skill/scripts/run_delivery.py tests/test_model_index.py tests/test_run_delivery.py
git commit -m "feat(picker): @effort spec form — spec_with_effort + parse_executor_spec split"
```

---

## Task 8: SKILL.md drill-down + search + effort rules; global sync  [CLAUDE]

**Files:** Modify `skill/SKILL.md`

- [ ] **Step 1: Replace the browse section with the scalable flow**
In `skill/SKILL.md`, in the picker section, update the "Browse all models…" rules to describe:
the **executor → provider → model → effort** drill-down (render each level verbatim from
`render_executor_level`/`render_provider_level`/`render_model_level`/`render_effort_level`);
the **headless-only default** with a "show all (incl. untested)" toggle; the **Search…** entry at
every level (`search_models`, free-text in chat, results labeled `<model> — <provider> via
<executor>`); and **effort selection** (after a model, if it has efforts, pick one — default
pre-selected; maps to the spec via `@effort`). Reinforce the no-improvising guard for all new
render fns. Add a one-line example for search ("compo"→Composer; "3.1"→all gemini-3.1 routings).

- [ ] **Step 2: Sync global + verify**
```bash
cp skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
diff -q skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
```
Expected: no diff.

- [ ] **Step 3: Full suite (integration gate)**
Run: `python -m pytest -p no:warnings -q`
Expected: green.

- [ ] **Step 4: Commit + advance STATUS**
```bash
git add skill/SKILL.md
git commit -m "docs(skill): scalable browse — drill-down + search + effort + headless-filter"
```
Update STATUS.md: Part 1 done; Next task = Part 2 Task 1.

---

## Done criteria (Part 1)
- `build_model_index` unifies opencode + gemini (+ cursor in Part 2) into `ModelChoice` records
  with provider classification, evidence overlay, and effort fields.
- `browse_filter` defaults to headless-only; `rank_provider_models` surfaces base models proven-first, capped.
- Drill-down render fns (executor/provider/model/effort) round-trip picks to specs, cp1252-safe.
- `search_models` does fuzzy substring matching, labeled by source, filter-respecting ("compo"/"3.1").
- `@effort` spec form parses + round-trips; back-compatible.
- SKILL.md documents the flow; global synced; full suite green.
