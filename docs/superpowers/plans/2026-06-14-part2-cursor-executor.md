# Part 2 — CursorExecutor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`). One sitting; commit each task; update STATUS.md before stopping. **Depends on Part 1 (the model index + effort axis).**

**Goal:** Add `cursor-agent` as a 4th executor (mirroring OpenCodeExecutor), feed its models + effort tiers into Part 1's index, resolve the dynamic Composer default, and add the usage-view Cursor account block. Includes the single Composer-via-CLI headless-proof dogfood.

**Architecture:** `src/cld/executors/cursor.py` mirrors `opencode.py` (versioned-path resolution, `-p` headless w/ timeout, `capture_diff`, usage parse). `list_cursor_models`/`resolve_composer_default` live in `models.py` and feed `build_model_index`. Registry + catalog + usage view get cursor entries. No core changes.

**Tech Stack:** Python 3.11+ stdlib, pytest fakes; live cursor-agent calls only in the explicit capture + validate + dogfood slices.

**Spec:** `docs/superpowers/specs/2026-06-14-scalable-picker-and-cursor-design.md` (Part 2)

**Builder routing:** T1 live JSON capture = CLAUDE (one real dispatch — eliminates guessing the shape). T2 `_cursor_cmd` + CursorExecutor seam = CLAUDE. T3 `parse_cursor_usage` = DOGFOOD (Gemini, against the captured fixture). T4 `list_cursor_models` + cursor effort-grouping in build_model_index = DOGFOOD (Gemini). T5 `resolve_composer_default` = DOGFOOD (Gemini). T6 registry + catalog + `_spec_for`/cursor `@effort` = CLAUDE. T7 usage `## Cursor account` block (`parse_cursor_about`) = CLAUDE. T8 SKILL.md + global sync = CLAUDE. **DOGFOOD-COMPOSER: T5 `resolve_composer_default` (small, pure, late-ish, no dependents) → dispatch to `cursor:composer-2.5` via the cursor CLI** instead of Gemini — the headless-proof Composer touchpoint.

---

## File Structure
- **Create `src/cld/executors/cursor.py`** — `CursorExecutor`, `_cursor_cmd`, `_default_runner`, `parse_cursor_usage`.
- **Create `docs/notes/cursor-run-sample.json`** — real `--output-format json` capture (T1 fixture).
- **Modify `src/cld/models.py`** — `list_cursor_models`, `resolve_composer_default`, cursor branch in `build_model_index` (effort grouping), Composer catalog entry, `_spec_for` cursor.
- **Modify `src/cld/executors/__init__.py`** — register `cursor`.
- **Modify `src/cld/usage.py` + `skill/scripts/run_delivery.py`** — `parse_cursor_about` + Cursor account block + `--usage` sources it.
- **Modify `skill/SKILL.md`** — cursor in picker/usage; sync global.
- Tests: `tests/executors/test_cursor.py`, `tests/test_model_index.py`, `tests/test_usage.py`, `tests/executors/test_registry.py`.

Reused: `capture_diff`, `EvidenceStore`, `ModelChoice`/`build_model_index` (Part 1), the OpenCode executor as the template.

---

## Task 1: Capture the real cursor `--output-format json` shape  [CLAUDE — one live dispatch]

**Files:** Create `docs/notes/cursor-run-sample.json`, `docs/notes/cursor-cli-notes.md`

- [ ] **Step 1: Resolve the cursor binary + run one tiny headless dispatch**
```bash
CUR=$(ls -dt /c/Users/Administrator/AppData/Local/cursor-agent/versions/*/ | head -1)cursor-agent.cmd
mkdir -p /tmp/cur-probe && cd /tmp/cur-probe && git init -q
"$CUR" -p --output-format json --force --trust --workspace . "Reply with the single word: ok" \
  > /d/claude_server/cross-llm-delivery/docs/notes/cursor-run-sample.json 2>/dev/null
echo "exit=$?"; wc -c /d/claude_server/cross-llm-delivery/docs/notes/cursor-run-sample.json
```
Expected: exit 0, non-empty JSON.

- [ ] **Step 2: Inspect the shape — where are token counts?**
Read `docs/notes/cursor-run-sample.json`. Determine: is it one JSON object or JSONL events? Where
do input/output token counts live (key path)? Is there a model field, a cost field? Record the
exact token key-path in `docs/notes/cursor-cli-notes.md` (this is the T3 parser contract — write
against the REAL shape, per the OpenCode JSONL lesson).

- [ ] **Step 3: Commit the fixture + notes**
```bash
cd /d/claude_server/cross-llm-delivery
git add docs/notes/cursor-run-sample.json docs/notes/cursor-cli-notes.md
git commit -m "docs(cursor): capture real --output-format json shape + token key-path (T3 fixture)"
```

**Acceptance:** a real cursor JSON sample committed; token key-path documented.

---

## Task 2: `_cursor_cmd` + `CursorExecutor` seam  [CLAUDE]

**Files:** Create `src/cld/executors/cursor.py`; Test `tests/executors/test_cursor.py` (create)

- [ ] **Step 1: Write the failing test**
```python
# tests/executors/test_cursor.py
from cld.executors.base import Executor, ExecutorResult, SliceTask
from cld.executors.cursor import CursorExecutor


class RecordingRunner:
    def __init__(self, responses): self._r = responses; self.calls = []
    def __call__(self, args, cwd):
        self.calls.append((args, cwd))
        joined = " ".join(args)
        for match, rc, out in self._r:
            if match in joined:
                return (rc, out)
        return (0, "")


def _ok_runner(diff="--- a\n+++ b\n+x\n"):
    return RecordingRunner([
        ("cursor", 0, '{"type":"result","tokens":{"input":10,"output":5}}'),
        ("--name-only", 0, "src/x.py\n"),
        ("diff", 0, diff),
    ])


def test_satisfies_protocol():
    assert isinstance(CursorExecutor(runner=_ok_runner()), Executor)


def test_builds_locked_argv():
    runner = _ok_runner()
    ex = CursorExecutor(runner=runner, model="composer-2.5")
    ex.run(SliceTask(id="T", brief="do the thing", files=["src/x.py"],
                     acceptance_test_path="tests/test_x.py"), "/work")
    argv = runner.calls[0][0]
    assert "cursor" in argv[0].lower()
    assert "-p" in argv
    assert "--output-format" in argv and "json" in argv
    assert "--workspace" in argv and "/work" in argv
    assert "--model" in argv and "composer-2.5" in argv
    assert "--force" in argv and "--trust" in argv
    assert "do the thing" in " ".join(argv)


def test_effort_maps_to_model_suffix():
    runner = _ok_runner()
    # effort passed via constructor -> cursor uses the suffixed model id
    ex = CursorExecutor(runner=runner, model="claude-opus-4-8", effort="medium")
    ex.run(SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py"), "/work")
    argv = runner.calls[0][0]
    assert "claude-opus-4-8-medium" in argv  # base + effort suffix


def test_nonzero_dispatch_not_ok():
    runner = RecordingRunner([("cursor", 1, "boom")])
    ex = CursorExecutor(runner=runner)
    res = ex.run(SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py"), "/work")
    assert res.ok is False and "boom" in res.raw_log
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/executors/test_cursor.py -q -p no:warnings`
Expected: FAIL — `No module named 'cld.executors.cursor'`.

- [ ] **Step 3: Implement `cursor.py` (Claude — mirror opencode.py)**
Create `src/cld/executors/cursor.py` modeled on `opencode.py`:
- `_cursor_cmd()`: `CURSOR_AGENT_CMD` override; else on Windows resolve the lexically-latest
  `<LOCALAPPDATA>/cursor-agent/versions/<v>/cursor-agent.cmd` (use `os.environ["LOCALAPPDATA"]`
  + `os.listdir` sorted desc); fallback `"cursor-agent"`.
- `_default_runner(args, cwd)`: subprocess.run with `encoding="utf-8", errors="replace"` (the
  learned decode discipline); return `(rc, out)`.
- `parse_cursor_usage(raw_json)`: STUB returning `{}` for now (T3 replaces it against the fixture).
- `class CursorExecutor`: `__init__(self, *, runner=_default_runner, model="composer-2.5",
  effort=None, timeout=600)`. `run(task, workdir, feedback=None)`:
  - build prompt (same shape as opencode's `_build_prompt`).
  - model id = `f"{self._model}-{self._effort}"` if `self._effort` else `self._model`.
  - argv = `[_cursor_cmd(), "-p", prompt, "--output-format", "json", "--workspace", str(workdir),
    "--model", model_id, "--force", "--trust"]`.
  - run via runner with the **timeout** (wrap subprocess in the timeout; on TimeoutExpired →
    `ExecutorResult(ok=False, diff="", raw_log="cursor dispatch timed out")`). For the injected
    test runner (no real subprocess), the timeout doesn't apply — just call it.
  - `rc != 0` → `ExecutorResult(ok=False, diff="", raw_log=raw)`.
  - success → `token_usage = parse_cursor_usage(raw)`; `diff, files = capture_diff(self._runner, cwd)`;
    return `ExecutorResult(ok=True, diff=diff, files_changed=files, token_usage=token_usage, raw_log=raw)`.
  - NEVER invoke bare (always `-p`).

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/executors/test_cursor.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/executors/cursor.py tests/executors/test_cursor.py
git commit -m "feat(cursor): CursorExecutor seam (-p/--workspace/--model/--force/--trust + effort suffix)"
```

---

## Task 3: `parse_cursor_usage` against the real fixture  [DOGFOOD — Gemini]

**Files:** Modify `src/cld/executors/cursor.py`; Test `tests/executors/test_cursor_usage.py` (create)

- [ ] **Step 1: Write the failing test (against the T1 fixture)**
```python
# tests/executors/test_cursor_usage.py
from pathlib import Path
from cld.executors.cursor import parse_cursor_usage

_SAMPLE = Path(__file__).resolve().parents[2] / "docs" / "notes" / "cursor-run-sample.json"


def test_parses_real_sample_tokens():
    usage = parse_cursor_usage(_SAMPLE.read_text(encoding="utf-8"))
    assert isinstance(usage, dict)
    assert all(isinstance(v, int) for v in usage.values())
    # tighten to the EXACT counts from the captured sample per cursor-cli-notes.md
    assert sum(usage.values()) > 0


def test_unparseable_returns_empty():
    assert parse_cursor_usage("not json") == {}
    assert parse_cursor_usage("") == {}
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/executors/test_cursor_usage.py -q -p no:warnings`
Expected: FAIL — stub returns `{}` so `sum>0` fails.

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**
Brief: implement `parse_cursor_usage(raw_json) -> dict[str,int]` in `src/cld/executors/cursor.py`
per the EXACT token key-path documented in `docs/notes/cursor-cli-notes.md` (single object or
JSONL — follow the notes). Map to input/output/total keys; sum across events if JSONL. Return `{}`
on unparseable (try/except). stdlib only. (When writing the test's exact-count assertion, read the
real numbers from the sample per the notes.)

- [ ] **Step 4: Judge**
Run: `python -m pytest tests/executors/test_cursor_usage.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/executors/cursor.py tests/executors/test_cursor_usage.py
git commit -m "feat(cursor): parse_cursor_usage against real fixture (Gemini-built, Claude-judged)"
```

---

## Task 4: `list_cursor_models` + cursor effort-grouping in build_model_index  [DOGFOOD — Gemini]

**Files:** Modify `src/cld/models.py`; Test `tests/test_model_index.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
from cld.models import list_cursor_models

_RAW = """auto - Auto
claude-opus-4-8-low - Opus 4.8 Low
claude-opus-4-8-medium - Opus 4.8 Medium
claude-opus-4-8-high - Opus 4.8
composer-2.5 - Composer 2.5 (current)
composer-2.5-fast - Composer 2.5 Fast (default)
"""


def test_list_cursor_models_parses_id_label():
    models = list_cursor_models(runner=lambda a, c: (0, _RAW))
    ids = [m[0] for m in models]
    assert "claude-opus-4-8-high" in ids and "composer-2.5" in ids
    assert ("composer-2.5", "Composer 2.5 (current)") in models or \
           any(i == "composer-2.5" for i, _ in models)


def test_index_groups_cursor_efforts_into_base():
    models = list_cursor_models(runner=lambda a, c: (0, _RAW))
    idx = build_model_index(opencode_ids=[], cursor_models=models, evidence={})
    opus = [c for c in idx if c.executor == "cursor" and c.model == "claude-opus-4-8"]
    assert len(opus) == 1                       # ONE base entry, not 3
    assert set(opus[0].efforts) >= {"low", "medium", "high"}  # efforts collected
    assert opus[0].default_effort == "high"     # the plain/unlabeled one is default
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_model_index.py -k "list_cursor or cursor_efforts" -q -p no:warnings`
Expected: FAIL — `cannot import name 'list_cursor_models'`.

- [ ] **Step 3: DOGFOOD — dispatch to Gemini**
Brief, two parts:
1. `list_cursor_models(runner) -> list[tuple[str,str]]`: run `["cursor-agent","--list-models"]`
   via runner; parse lines of form `<id> - <label>`; return `(id, label)` tuples (skip blank/
   header lines, skip `auto`). `[]` on rc!=0.
2. Replace the cursor branch in `build_model_index` so cursor_models (the (id,label) tuples) are
   GROUPED by base model: strip a trailing effort suffix from each id (suffixes:
   `low, medium, high, xhigh, max` optionally followed by `-fast` and/or preceded by `thinking-`;
   handle compound like `-thinking-high`, `-high-fast`). The base id (suffix removed) is one
   ModelChoice with `efforts` = the sorted set of effort levels found, and `default_effort` = the
   level whose label has no explicit effort word OR is marked "(default)"/"(current)" (fallback:
   "high" if present else the first). Models with no effort suffix (e.g. `composer-2.5`,
   `composer-2.5-fast` → base `composer-2.5`, effort fast) group the same way. executor="cursor",
   provider=`_provider_of(id)`, cost_class from catalog if present else "metered-unknown",
   headless_status from evidence/catalog else "untested". stdlib only.

- [ ] **Step 4: Judge**
Run: `python -m pytest tests/test_model_index.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_model_index.py
git commit -m "feat(cursor): list_cursor_models + effort grouping into the model index (Gemini-built, Claude-judged)"
```

---

## Task 5: `resolve_composer_default`  [DOGFOOD — **cursor:composer-2.5 via CLI** (the headless proof)]

**Files:** Modify `src/cld/models.py`; Test `tests/test_model_index.py` (append)

- [ ] **Step 1: Write the failing test (append)**
```python
from cld.models import resolve_composer_default


def test_resolve_composer_prefers_current():
    raw = "composer-2.5 - Composer 2.5 (current)\ncomposer-2.5-fast - Composer 2.5 Fast (default)\n"
    assert resolve_composer_default(runner=lambda a, c: (0, raw)) == "composer-2.5"


def test_resolve_composer_falls_back_to_static_on_empty():
    assert resolve_composer_default(runner=lambda a, c: (1, "")) == "composer-2.5"
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_model_index.py -k resolve_composer -q -p no:warnings`
Expected: FAIL — `cannot import name 'resolve_composer_default'`.

- [ ] **Step 3: DOGFOOD via CURSOR (the Composer headless-proof touchpoint)**
This is the ONE slice routed to Composer. Dispatch via the cursor CLI directly (CursorExecutor
exists from T2 but to keep it a pure CLI proof, dispatch through `cursor-agent -p` on an isolated
repo containing the failing test + the src package), model `composer-2.5`:
Brief: add `resolve_composer_default(runner) -> str` to `src/cld/models.py`: call
`list_cursor_models(runner)` (or run `--list-models`); among ids starting with "composer", pick
the one whose label contains "(current)"; else "(default)"; else the highest `composer-N.N`
(numeric sort); else return the static string "composer-2.5". Never raise. stdlib only.
Judge with independent pytest. **If Composer fails/hiccups, fall back to a Gemini dispatch** (the
slice is identical) — the point is to PROVE Composer headless, not to block the build.

- [ ] **Step 4: Judge + record Composer's verdict**
Run: `python -m pytest tests/test_model_index.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS. Then record the live Composer outcome in the evidence store (proven if it built
the slice): note it in STATUS so the picker shows Composer `proven`.

- [ ] **Step 5: Commit**
```bash
git add src/cld/models.py tests/test_model_index.py
git commit -m "feat(cursor): resolve_composer_default dynamic default (Composer-via-CLI dogfood, Claude-judged)"
```

---

## Task 6: Registry + catalog + cursor spec/effort mapping  [CLAUDE]

**Files:** Modify `src/cld/executors/__init__.py`, `src/cld/models.py`; Test `tests/executors/test_registry.py`, `tests/test_model_index.py`

- [ ] **Step 1: Write the failing tests**
Append to `tests/executors/test_registry.py`:
```python
def test_get_cursor():
    from cld.executors import get_executor, KNOWN_EXECUTORS
    from cld.executors.cursor import CursorExecutor
    ex = get_executor("cursor", model="composer-2.5")
    assert isinstance(ex, CursorExecutor)
    assert "cursor" in KNOWN_EXECUTORS
```
Append to `tests/test_model_index.py`:
```python
def test_spec_for_cursor_and_composer_catalog():
    from cld.models import MODEL_METADATA, _spec_for
    assert "cursor:composer-2.5" in MODEL_METADATA
    class _C:  # _spec_for reads .id
        id = "cursor:composer-2.5"
    assert _spec_for(_C()) == "cursor:composer-2.5"  # already spec-shaped, unchanged
```

- [ ] **Step 2: Run to verify both fail**
Run: `python -m pytest tests/executors/test_registry.py -k cursor tests/test_model_index.py -k spec_for_cursor -q -p no:warnings`
Expected: FAIL (ValueError unknown executor / KeyError).

- [ ] **Step 3: Implement**
- `src/cld/executors/__init__.py`: `KNOWN_EXECUTORS = ("gemini", "composer", "opencode", "cursor")`;
  add `elif clean_name == "cursor": from cld.executors.cursor import CursorExecutor; return CursorExecutor(**kwargs)`.
- `src/cld/models.py`: add the Composer catalog entry to `MODEL_METADATA`:
  ```python
  "cursor:composer-2.5": ModelInfo(
      id="cursor:composer-2.5", provider="cursor", cost_class="cheap-metered",
      capability_class="heavy", headless_status="untested", rework_risk="low",
      note="Cursor's cost-optimized Composer; resolve_composer_default tracks the current version"),
  ```
  Confirm `_spec_for` leaves `cursor:<x>` unchanged (it already returns ids with a `:` as-is; if
  it special-cases only opencode, add: ids containing `:` are already specs → return as-is).
- Ensure `get_executor("cursor", model=, effort=)` passes `effort` through (CursorExecutor accepts it).

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/executors/test_registry.py tests/test_model_index.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/cld/executors/__init__.py src/cld/models.py tests/executors/test_registry.py tests/test_model_index.py
git commit -m "feat(cursor): register executor + Composer catalog entry + spec mapping"
```

---

## Task 7: Usage view — Cursor account block  [CLAUDE]

**Files:** Modify `src/cld/usage.py`, `skill/scripts/run_delivery.py`; Test `tests/test_usage.py`

- [ ] **Step 1: Write the failing test (append to tests/test_usage.py)**
```python
from cld.usage import parse_cursor_about, render_usage_table

CUR_ABOUT = """About Cursor CLI
CLI Version 2026.06.12
Model Composer 2.5 Fast
Subscription Tier Pro
User Email x@y.z
"""


def test_parse_cursor_about():
    a = parse_cursor_about(CUR_ABOUT)
    assert a["tier"] == "Pro"
    assert "Composer" in a["model"]


def test_cursor_block_only_when_cursor_slice_present():
    class E:
        def __init__(s, sid, model, tu, cost=None):
            s.slice_id, s.model, s.token_usage, s.cost = sid, model, tu, cost
    class L:
        def __init__(s, e): s._e = {x.slice_id: x for x in e}
        @property
        def entries(s): return s._e
    # a build with a cursor slice -> Cursor account block present
    out = render_usage_table(L([E("T1", "cursor:composer-2.5", {"total": 50})]),
                             {}, cursor_about={"tier": "Pro", "model": "Composer 2.5"})
    assert "Cursor account" in out and "Pro" in out
    assert "/usage" in out or "cursor.com" in out  # the server-side pointer
    # a gemini-only build -> NO cursor block
    out2 = render_usage_table(L([E("T2", "gemini:gemini-3.1-pro-preview", {"total": 9})]),
                              {}, cursor_about={"tier": "Pro", "model": "Composer 2.5"})
    assert "Cursor account" not in out2
```

- [ ] **Step 2: Run to verify it fails**
Run: `python -m pytest tests/test_usage.py -k "cursor" -q -p no:warnings`
Expected: FAIL — `cannot import name 'parse_cursor_about'` / signature mismatch.

- [ ] **Step 3: Implement**
In `src/cld/usage.py`:
- `parse_cursor_about(text) -> dict`: scan lines; capture the value after "Subscription Tier" →
  `tier`, after "Model" → `model`. Return `{}` if none found.
- Extend `render_usage_table(ledger, oc_stats, *, cursor_about=None)`: after the existing
  OpenCode block, IF any ledger entry's `model` starts with "cursor:" AND `cursor_about`, append:
  ```
  ## Cursor account
  Tier: <tier>   Default model: <model>
  Token/cost totals are server-side — run /usage in the Cursor TUI or see cursor.com.
  ```
  (ASCII only, cp1252-safe.) Keep `cursor_about=None` default so existing callers/tests pass.
In `skill/scripts/run_delivery.py`: in the `--usage` handler, also shell `cursor-agent about`
(timeout-guarded, via a `_cursor_about_text()` helper mirroring `_opencode_stats_text`) and pass
`cursor_about=parse_cursor_about(...)` to `render_usage_table`.

- [ ] **Step 4: Run + full suite**
Run: `python -m pytest tests/test_usage.py -q -p no:warnings && python -m pytest -p no:warnings -q`
Expected: PASS (existing render_usage_table tests still green — new kwarg is optional).

- [ ] **Step 5: Commit**
```bash
git add src/cld/usage.py skill/scripts/run_delivery.py tests/test_usage.py
git commit -m "feat(usage): conditional Cursor account block from 'cursor-agent about'"
```

---

## Task 8: SKILL.md cursor integration + global sync  [CLAUDE]

**Files:** Modify `skill/SKILL.md`

- [ ] **Step 1: Add cursor to the picker + usage docs**
In `skill/SKILL.md`: note `cursor` as a 4th executor in the drill-down (Composer in window-1
shortlist, full cursor models via browse, `cursor:<model>@<effort>` specs); document the Cursor
account block in the usage view (server-side usage caveat). Reinforce: cursor is invoked headless
only (`-p`), never bare.

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
git commit -m "docs(skill): cursor executor in picker + usage view"
```
Update STATUS.md: Part 2 done; Next = Part 3 Task 1. Record Composer's live headless verdict.

---

## Done criteria (Part 2)
- `get_executor("cursor")` returns a working CursorExecutor; argv is the proven headless form
  (`-p --output-format json --workspace --model --force --trust`); effort maps to the model suffix.
- `list_cursor_models` + effort grouping feed cursor base-models (with efforts) into the index;
  `resolve_composer_default` tracks the current Composer.
- Composer catalog entry present; cursor registered; usage view shows a Cursor account block when a
  cursor slice ran.
- Composer proven headless via the one CLI dogfood (recorded in the evidence store).
- Full suite green; backward-compatible.
