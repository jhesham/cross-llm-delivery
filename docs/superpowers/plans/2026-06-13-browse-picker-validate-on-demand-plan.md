# Browse Picker + Headless Validate-on-Demand — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user browse ALL available OpenCode models (grouped by provider) from the picker, with any unproven pick validated against a real trivial slice before the build — cost-gated, session-only known-bad marks, and a "please wait" progress message.

**Architecture:** Two pure additions to `src/cld/models.py` (`BrowseItem`+`browse_models`, `render_browse_list`) keep the single-source-of-truth guard (chat dialogs render these lines verbatim). A fully-injectable gate `resolve_and_validate` lives in `src/cld/validate.py` next to the `validate_model` (T8) harness it wraps. `recommend()` gains a `session_known_bad` filter so a failed model is hidden when the picker is re-presented. No executor/judge/orchestrator core changes.

**Tech Stack:** Python 3.11+ stdlib (dataclasses), pytest with fakes only (no live LLM in the suite).

**Spec:** `docs/superpowers/specs/2026-06-13-browse-picker-validate-on-demand-design.md`

**Builder routing (dogfood method):** T1 `browse_models` = DOGFOOD (Gemini). T2 `render_browse_list` = DOGFOOD (OpenCode `opencode/deepseek-v4-flash-free` — proved itself building `recommend()` last build). T3 `resolve_and_validate` gate = CLAUDE. T4 `recommend(session_known_bad=...)` = CLAUDE (tiny). T5 SKILL.md + global sync = CLAUDE. For each dogfood: Claude authors the failing test + brief, dispatches, judges with independent pytest.

---

## File Structure

- **Modify `src/cld/models.py`** — add `KNOWN_PROVIDERS`, `BrowseItem`, `_provider_of`, `browse_models`, `render_browse_list`; add `session_known_bad` param to `recommend`. (Spec places the browse units here — same module as the catalog/shortlist they extend.)
- **Modify `src/cld/validate.py`** — add `ResolveResult` + `resolve_and_validate` (the gate wraps `validate_model`, which already lives here; files that change together live together).
- **Create `tests/test_browse.py`** — browse grouping/annotation/rendering tests.
- **Create `tests/test_resolve_validate.py`** — gate tests (all paths, fakes only).
- **Modify `tests/test_models.py`** — `recommend(session_known_bad=...)` test (append).
- **Modify `skill/SKILL.md`** — browse flow + validate-on-demand rules; sync to `~/.claude/skills/cross-llm-delivery/SKILL.md` (the `cld` package needs no sync — editable install).

Existing pieces reused as-is: `MODEL_METADATA`, `DEFAULT_WORKHORSE_ID`, `_spec_for` (takes any object with `.id` — works for `BrowseItem`), `validate_model` + `ValidationResult` (T8).

**Deliberately omitted (YAGNI, per spec "secondary"):** a "browse all" entry inside the CLI `pick_executor` prompt — the CLI shortlist already lists every available model the catalog knows, and `run_delivery.py` accepts any `--executor opencode:<id>` directly. The browse flow is a chat-surface need.

---

## Task 1: `BrowseItem` + `browse_models`  [DOGFOOD — Gemini]

**Files:**
- Modify: `src/cld/models.py`
- Test: `tests/test_browse.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_browse.py
"""browse_models: group ALL available ids by provider, annotate from the catalog,
default uncatalogued models to untested, infer cost from the id, self-include the
flat-rate Gemini-CLI workhorse, and honor session known-bad marks."""

from cld.models import DEFAULT_WORKHORSE_ID, BrowseItem, browse_models

IDS = [
    "opencode/claude-opus-4-8",         # catalogued (premium-metered/heavy/likely)
    "opencode/gpt-5.2",                 # uncatalogued -> untested, metered-unknown
    "opencode/deepseek-v4-flash-free",  # catalogued (free/quick/untested)
    "opencode/nemotron-3-ultra-free",   # uncatalogued, -free suffix, unknown provider
    "opencode/gemini-3.1-pro",          # catalogued (cheap-metered/workhorse/likely)
    "opencode/big-pickle",              # uncatalogued, unknown provider -> other
]


def _ids(group):
    return [i.id for i in group]


def test_groups_by_provider_token():
    g = browse_models(IDS)
    assert "opencode/claude-opus-4-8" in _ids(g["claude"])
    assert "opencode/gpt-5.2" in _ids(g["gpt"])
    assert "opencode/deepseek-v4-flash-free" in _ids(g["deepseek"])
    assert "opencode/gemini-3.1-pro" in _ids(g["gemini"])
    # unknown providers collapse into "other"
    assert "opencode/big-pickle" in _ids(g["other"])
    assert "opencode/nemotron-3-ultra-free" in _ids(g["other"])


def test_uncatalogued_default_untested_and_cost_inferred():
    g = browse_models(IDS)
    gpt = next(i for i in g["gpt"] if i.id == "opencode/gpt-5.2")
    assert isinstance(gpt, BrowseItem)
    assert gpt.in_catalog is False
    assert gpt.headless_status == "untested"
    assert gpt.cost_class == "metered-unknown"
    nem = next(i for i in g["other"] if "nemotron" in i.id)
    assert nem.cost_class == "free"  # -free suffix


def test_catalogued_items_copy_metadata():
    g = browse_models(IDS)
    opus = next(i for i in g["claude"] if "opus-4-8" in i.id)
    assert opus.in_catalog is True
    assert opus.cost_class == "premium-metered"
    assert opus.headless_status == "likely"


def test_workhorse_always_self_included():
    g = browse_models([])  # OpenCode down -> still offers the flat-rate workhorse
    assert list(g.keys()) == ["gemini"]
    assert _ids(g["gemini"]) == [DEFAULT_WORKHORSE_ID]
    wh = g["gemini"][0]
    assert wh.in_catalog is True and wh.headless_status == "proven"


def test_group_order_catalogued_first_then_alpha():
    g = browse_models(IDS)
    # claude/deepseek/gemini have catalogued items -> first (alpha); gpt/other after
    assert list(g.keys()) == ["claude", "deepseek", "gemini", "gpt", "other"]


def test_session_known_bad_filtered_out():
    g = browse_models(IDS, session_known_bad={"opencode/gpt-5.2"})
    assert "gpt" not in g or "opencode/gpt-5.2" not in _ids(g["gpt"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_browse.py -q -p no:warnings`
Expected: FAIL — `ImportError: cannot import name 'BrowseItem' from 'cld.models'`.

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**

Dispatch with the locked CLI form (`GEMINI_CLI_TRUST_WORKSPACE=true gemini -p "<brief>" -m gemini-3.1-pro-preview --yolo --skip-trust -o json`). Brief — add to `src/cld/models.py`, touching nothing else, stdlib only, until `tests/test_browse.py` passes (do not edit the test file):

```python
KNOWN_PROVIDERS = ("claude", "gpt", "gemini", "deepseek")


@dataclass
class BrowseItem:
    id: str
    provider: str
    cost_class: str
    headless_status: str
    in_catalog: bool


def _provider_of(model_id: str) -> str:
    """Provider token: strip 'opencode/' (or take the part after ':'), then the
    leading token up to the first '-' or '.'; unknown providers -> 'other'."""
    name = model_id
    if name.startswith("opencode/"):
        name = name[len("opencode/"):]
    elif ":" in name:
        name = name.split(":", 1)[1]
    token = name.replace(".", "-").split("-", 1)[0].lower()
    return token if token in KNOWN_PROVIDERS else "other"


def browse_models(available_ids, *, session_known_bad=frozenset()) -> Dict[str, List[BrowseItem]]:
    """Group ALL available model ids by provider for the browse picker.

    Catalogued ids copy cost/headless metadata; uncatalogued default to
    untested with cost inferred from the id (-free suffix -> free, else
    metered-unknown). The flat-rate workhorse is always self-included.
    Ids in session_known_bad (and catalog known-bad) are dropped. Group
    order: providers holding catalogued items first, then alphabetical.
    """
    ids = [i for i in available_ids if i not in session_known_bad]
    if DEFAULT_WORKHORSE_ID not in ids and DEFAULT_WORKHORSE_ID not in session_known_bad:
        ids.append(DEFAULT_WORKHORSE_ID)

    groups: Dict[str, List[BrowseItem]] = {}
    for mid in ids:
        info = MODEL_METADATA.get(mid)
        if info is not None and info.headless_status == "known-bad":
            continue
        if info is not None:
            item = BrowseItem(id=mid, provider=_provider_of(mid),
                              cost_class=info.cost_class,
                              headless_status=info.headless_status, in_catalog=True)
        else:
            cost = "free" if mid.endswith("-free") else "metered-unknown"
            item = BrowseItem(id=mid, provider=_provider_of(mid), cost_class=cost,
                              headless_status="untested", in_catalog=False)
        groups.setdefault(item.provider, []).append(item)

    def _key(p: str):
        return (0 if any(i.in_catalog for i in groups[p]) else 1, p)

    return {p: sorted(groups[p], key=lambda i: i.id) for p in sorted(groups, key=_key)}
```

- [ ] **Step 4: Judge — run independently (never trust the executor's self-report)**

Run: `python -m pytest tests/test_browse.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: all PASS, full suite green.

- [ ] **Step 5: Commit (merge of the dogfood)**

```bash
git add src/cld/models.py tests/test_browse.py
git commit -m "feat(browse): BrowseItem + browse_models grouped catalog view (Gemini-built, Claude-judged)"
```

---

## Task 2: `render_browse_list`  [DOGFOOD — OpenCode deepseek-v4-flash-free]

**Files:**
- Modify: `src/cld/models.py`
- Test: `tests/test_browse.py` (append)

- [ ] **Step 1: Write the failing test (append to tests/test_browse.py)**

```python
from cld.models import render_browse_list


def test_render_numbering_round_trips_to_ids():
    lines, ordered = render_browse_list(browse_models(IDS))
    # every numbered line N) contains the spec of ordered[N-1]
    import re
    for ln in lines:
        m = re.match(r"\s*(\d+)\)\s+(\S+)", ln)
        if not m:
            continue
        n, spec = int(m.group(1)), m.group(2)
        item = ordered[n - 1]
        expected = item.id if item.id.startswith("gemini:") else f"opencode:{item.id}"
        assert spec == expected


def test_render_marks_untested_and_premium():
    lines, _ = render_browse_list(browse_models(IDS))
    blob = "\n".join(lines)
    assert "(!)" in blob          # untested marker present
    assert "$" in blob            # premium (claude-opus) billed marker
    assert "CLAUDE" in blob       # provider headers


def test_render_is_cp1252_safe():
    lines, _ = render_browse_list(browse_models(IDS))
    "\n".join(lines).encode("cp1252")  # raises on a bad glyph
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_browse.py -k render -q -p no:warnings`
Expected: FAIL — `ImportError: cannot import name 'render_browse_list'`.

- [ ] **Step 3: DOGFOOD — dispatch to OpenCode**

Dispatch: `opencode run "<brief>" -m opencode/deepseek-v4-flash-free --format json --dir .`
Brief — add to `src/cld/models.py` below `browse_models`, touching nothing else, stdlib only, until all of `tests/test_browse.py` passes (do not edit the test file):

```python
def render_browse_list(grouped) -> tuple:
    """Render the grouped browse view verbatim (the chat/CLI surfaces copy these
    lines — never hand-type options). Returns (lines, ordered) where a numeric
    pick N maps to ordered[N-1]. ASCII only ($ = billed, (!) = untested)."""
    lines: List[str] = ["All available models (grouped by provider):"]
    ordered: List[BrowseItem] = []
    n = 0
    for provider, items in grouped.items():
        lines.append(f"  {provider.upper()}")
        for it in items:
            n += 1
            ordered.append(it)
            cost = it.cost_class + (" $" if it.cost_class == "premium-metered" else "")
            warn = "  (!) untested" if it.headless_status == "untested" else ""
            lines.append(
                f"    {n}) {_spec_for(it):42s} {cost:18s} {it.headless_status:8s}{warn}"
            )
    return lines, ordered
```

(`_spec_for` already exists in models.py and only reads `.id` — it works on BrowseItem.)

- [ ] **Step 4: Judge — run independently**

Run: `python -m pytest tests/test_browse.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: all PASS, full suite green.

- [ ] **Step 5: Commit (merge of the dogfood)**

```bash
git add src/cld/models.py tests/test_browse.py
git commit -m "feat(browse): render_browse_list verbatim surface (OpenCode-built, Claude-judged)"
```

---

## Task 3: `resolve_and_validate` gate  [CLAUDE]

**Files:**
- Modify: `src/cld/validate.py`
- Test: `tests/test_resolve_validate.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_resolve_validate.py
"""resolve_and_validate: the validate-on-demand gate. Pure orchestration around an
injected validate_fn (wraps validate_model in production) — all fakes here."""

from cld.validate import ResolveResult, ValidationResult, resolve_and_validate


def _gate(spec="opencode:opencode/gpt-5.2", *, status="untested", cost="free",
          verdict=None, confirm=True, session=None):
    out, confirms = [], []

    def confirm_fn(msg):
        confirms.append(msg)
        return confirm

    res = resolve_and_validate(
        spec,
        headless_status_of=lambda s: status,
        cost_class_of=lambda s: cost,
        validate_fn=lambda s: verdict,
        confirm_fn=confirm_fn,
        output_fn=out.append,
        session_known_bad=session,
    )
    return res, out, confirms


def test_proven_and_likely_pass_through_without_validation():
    for st in ("proven", "likely"):
        res, out, confirms = _gate(status=st)
        assert res.proceeded is True and res.validated is False
        assert out == [] and confirms == []


def test_untested_free_validates_with_progress_message_then_proceeds():
    res, out, confirms = _gate(
        verdict=ValidationResult("m", True, "proven", 1))
    assert res.proceeded is True and res.validated is True and res.status == "proven"
    assert confirms == []  # free -> no cost confirm
    # progress message emitted BEFORE the verdict line
    assert "please wait" in out[0].lower() and "validating headless" in out[0].lower()
    assert "proven" in out[1].lower()


def test_untested_metered_requires_confirm_and_decline_stops():
    res, out, confirms = _gate(cost="metered-unknown", confirm=False)
    assert res.proceeded is False and res.validated is False
    assert len(confirms) == 1 and "bill" in confirms[0].lower()
    assert "declined" in res.note


def test_untested_metered_confirmed_validates():
    res, _, confirms = _gate(cost="cheap-metered", confirm=True,
                             verdict=ValidationResult("m", True, "proven", 1))
    assert len(confirms) == 1
    assert res.proceeded is True and res.status == "proven"


def test_known_bad_verdict_declines_and_marks_session():
    session = set()
    res, out, _ = _gate(verdict=ValidationResult("m", False, "known-bad", 1, "bad code"),
                        session=session)
    assert res.proceeded is False and res.validated is True and res.status == "known-bad"
    assert "opencode:opencode/gpt-5.2" in session  # marked for THIS session only
    assert any("not headless" in ln.lower() for ln in out)


def test_session_marked_spec_is_rejected_immediately():
    res, out, _ = _gate(session={"opencode:opencode/gpt-5.2"})
    assert res.proceeded is False and res.validated is False
    assert "session" in res.note


def test_executor_error_is_untested_not_a_verdict():
    res, out, _ = _gate(verdict=ValidationResult("m", False, "untested", 0,
                                                 "executor error: CLI missing"))
    assert res.proceeded is False and res.validated is False and res.status == "untested"
    assert "couldn't validate" in res.note
    assert any("couldn't validate" in ln.lower() for ln in out)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_resolve_validate.py -q -p no:warnings`
Expected: FAIL — `ImportError: cannot import name 'ResolveResult'`.

- [ ] **Step 3: Implement in `src/cld/validate.py` (append below validate_model)**

```python
_METERED = ("cheap-metered", "premium-metered", "metered-unknown")


@dataclass
class ResolveResult:
    spec: str
    status: str          # headless status after resolution
    validated: bool      # did a validation dispatch actually run + conclude
    proceeded: bool      # may the build proceed with this model
    note: str = ""


def resolve_and_validate(spec: str, *, headless_status_of, cost_class_of, validate_fn,
                         confirm_fn, output_fn, session_known_bad=None) -> ResolveResult:
    """Validate-on-demand gate: only proven/likely models pass straight through; an
    untested pick is validated against a real trivial slice first (metered models
    confirm the validation spend), and a known-bad verdict declines the pick and
    marks it for THIS session only (caller re-presents the picker without it)."""
    skb = session_known_bad if session_known_bad is not None else set()
    if spec in skb:
        return ResolveResult(spec, "known-bad", False, False,
                             "marked known-bad this session — pick another model")

    status = headless_status_of(spec)
    if status in ("proven", "likely"):
        return ResolveResult(spec, status, False, True)
    if status == "known-bad":
        skb.add(spec)
        return ResolveResult(spec, "known-bad", False, False, "known-bad in catalog")

    # untested -> validate before allowing the build
    if cost_class_of(spec) in _METERED:
        if not confirm_fn(f"Validating {spec} runs one real dispatch that bills real $ "
                          f"(metered model) — proceed?"):
            return ResolveResult(spec, "untested", False, False,
                                 "validation declined (cost)")

    output_fn(f"Validating headless capability for {spec} — this runs one trivial "
              f"slice (~30s), please wait...")
    vr = validate_fn(spec)
    if vr.status == "proven":
        output_fn(f"{spec}: proven headless-capable.")
        return ResolveResult(spec, "proven", True, True)
    if vr.status == "known-bad":
        output_fn(f"{spec}: NOT headless-capable (built failing or no code). "
                  f"Pick another model.")
        skb.add(spec)
        return ResolveResult(spec, "known-bad", True, False,
                             vr.note or "failed validation")
    output_fn(f"{spec}: couldn't validate ({vr.note}). Not a model verdict — "
              f"you may retry or pick another model.")
    return ResolveResult(spec, "untested", False, False, f"couldn't validate: {vr.note}")
```

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_resolve_validate.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/cld/validate.py tests/test_resolve_validate.py
git commit -m "feat(validate): resolve_and_validate gate — validate-on-demand with cost confirm + session known-bad"
```

---

## Task 4: `recommend(session_known_bad=...)`  [CLAUDE — tiny]

**Files:**
- Modify: `src/cld/models.py` (the `recommend` function)
- Test: `tests/test_models.py` (append)

- [ ] **Step 1: Write the failing test (append to tests/test_models.py)**

```python
def test_recommend_hides_session_known_bad():
    # a model that failed validation this session is hidden on re-present
    recs = recommend(
        available_ids=["opencode/deepseek-v4-flash-free", "opencode/claude-opus-4-8"],
        session_known_bad={"opencode/deepseek-v4-flash-free"},
    )
    ids = [r.id for r in recs]
    assert "opencode/deepseek-v4-flash-free" not in ids
    assert "opencode/claude-opus-4-8" in ids
    # the proven default is still there and still default
    assert any(r.is_default and r.id == "gemini:gemini-3.1-pro-preview" for r in recs)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_models.py -k session_known_bad -q -p no:warnings`
Expected: FAIL — `TypeError: recommend() got an unexpected keyword argument 'session_known_bad'`.

- [ ] **Step 3: Implement — change the `recommend` signature and add the filter**

In `src/cld/models.py`, change:

```python
def recommend(*, available_ids, job=None) -> list[Recommendation]:
    # Always consider the proven default available (it's not an OpenCode model).
    effective_ids = set(available_ids) | {DEFAULT_WORKHORSE_ID}
```

to:

```python
def recommend(*, available_ids, job=None, session_known_bad=frozenset()) -> list[Recommendation]:
    # Always consider the proven default available (it's not an OpenCode model).
    effective_ids = (set(available_ids) | {DEFAULT_WORKHORSE_ID}) - set(session_known_bad)
```

(No other lines change.)

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_models.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/cld/models.py tests/test_models.py
git commit -m "feat(models): recommend() hides session known-bad models on re-present"
```

---

## Task 5: SKILL.md browse + validate-on-demand docs, global sync  [CLAUDE]

**Files:**
- Modify: `skill/SKILL.md` (the "Choosing the executor & model" section)

- [ ] **Step 1: Add the browse + validate-on-demand rules**

In `skill/SKILL.md`, immediately after the existing GUARD paragraph (the one mandating
`render_shortlist`-verbatim options), insert:

```markdown
   **Browsing the full model list.** The shortlist dialog must include a "Browse all models…"
   option. If chosen: present provider groups (claude / gpt / gemini / deepseek / other), then
   the chosen group's models — every option rendered VERBATIM from
   `cld.models.browse_models(available_ids)` → `cld.models.render_browse_list(grouped)` (the
   same no-improvising guard applies; same ids, order, count). UI dialogs cap at 4 options —
   page with a "More…" entry when a group exceeds it. Free-text "Other" stays as the final
   escape hatch; a free-typed id is treated as untested.

   **Validate-on-demand (the headless guarantee).** Before dispatching a build on ANY pick
   whose `headless_status` is not proven/likely — browsed, free-typed, or uncatalogued — run
   `cld.validate.resolve_and_validate(spec, ...)`. It:
   - announces "Validating headless capability for <spec> — this runs one trivial slice
     (~30s), please wait…" before the dispatch, and a verdict line after;
   - on a metered model (cheap-metered / premium-metered / metered-unknown) asks "validating
     bills real $ — proceed?" BEFORE spending; declining means pick again;
   - on `proven`: proceed with the build;
   - on `known-bad` (built failing/no code): decline, mark it known-bad for THIS SESSION ONLY
     (pass the same `session_known_bad` set to `recommend`/`browse_models` so it's hidden),
     and RE-PRESENT the picker so the user picks another model;
   - on an executor error: report "couldn't validate" — not a model verdict; let the user
     retry or pick another.
   Never dispatch a real build on an untested model without this gate.
```

- [ ] **Step 2: Sync the global skill copy and verify identical**

Run:
```bash
cp skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
diff -q skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md
```
Expected: no diff output (identical). The `cld` package needs no sync (editable install).

- [ ] **Step 3: Run the full suite one last time (integration gate)**

Run: `python -m pytest -p no:warnings -q`
Expected: all green (≈173 prior + ~16 new).

- [ ] **Step 4: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs(skill): browse-all flow + validate-on-demand gate rules"
```

---

## Done criteria

- `browse_models` + `render_browse_list` expose ALL available models, grouped, verbatim-renderable (the chat dialog has a real "Browse all…" path; nothing hand-typed).
- An untested pick cannot reach a real build without `resolve_and_validate`: progress message → real-slice proof → proceed only on `proven`.
- Metered validation never spends without an explicit confirm; declining re-presents the picker.
- `known-bad` hides the model for the session (`recommend`/`browse_models` filters) and re-presents — never a permanent blacklist, no catalog writes.
- Full suite green with fakes only; `validate_model` (T8) reused unmodified.
