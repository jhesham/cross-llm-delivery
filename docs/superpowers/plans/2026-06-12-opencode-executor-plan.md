# OpenCode Executor + Model Picker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenCode CLI as a third executor with a full interactive model-picker (user-chosen, cost-aware, evidence-backed headless status), defaulting to the proven $0 flat-rate workhorse.

**Architecture:** OpenCode plugs into the existing pluggable-executor registry alongside `gemini`/`composer`, inheriting every shared-pipeline fix (Bug A/B, `--step`, judge timeout, feedback loop). A shared `capture_diff` helper is extracted first (DRY between Gemini and OpenCode). A curated model catalog + pure recommender + a validation harness (one trivial known-answer slice, real test as judge) drive the SKILL.md picker. The USER picks; premium-metered models require explicit cost confirmation.

**Tech Stack:** Python 3.11+, pytest, the OpenCode CLI (`opencode run -m provider/model --format json --dir`), existing `cld` package + the real-git integration harness (`tests/integration/`).

**Spec:** `docs/superpowers/specs/2026-06-12-opencode-executor-design.md`

**Builder routing (per spec):** T1 capture-JSON = CLAUDE (live). T2 capture_diff refactor = CLAUDE. T3 OpenCodeExecutor = CLAUDE (seam). T4 parse_opencode_usage = DOGFOOD (Gemini). T5 registry = trivial CLAUDE. T6 model catalog/list_models = DOGFOOD. T7 recommend() = DOGFOOD (or OpenCode self-dogfood — see task). T8 validate_model harness = CLAUDE. T9 SKILL.md picker = CLAUDE.

---

## File Structure

- **Create `src/cld/executors/_capture.py`** — shared `capture_diff(runner, cwd)` used by both executors (extracted from gemini). One responsibility: stage + capture the worktree diff.
- **Create `src/cld/executors/opencode.py`** — `OpenCodeExecutor` (the seam) + `parse_opencode_usage`.
- **Modify `src/cld/executors/gemini.py`** — use the shared `capture_diff` (remove the duplicated block).
- **Modify `src/cld/executors/__init__.py`** — register `"opencode"`.
- **Create `src/cld/models.py`** — `MODEL_METADATA`, `list_models`, `recommend`.
- **Create `src/cld/validate.py`** — `validate_model` harness.
- **Modify `skill/SKILL.md`** — the picker behavior.
- **Create** tests: `tests/executors/test_capture.py`, `tests/executors/test_opencode.py`, `tests/test_models.py`, `tests/test_validate.py`.
- **Capture artifact:** `docs/notes/opencode-run-sample.json` (real `--format json` output from T1).

---

## Task 1: Capture the real OpenCode `--format json` output  [CLAUDE — live]

**Why first:** the token parser (T4) must be written against the REAL shape, never a guess. This is the Phase-0 smoke discipline. One live dispatch.

**Files:**
- Create: `docs/notes/opencode-run-sample.json`, `docs/notes/opencode-cli-notes.md`

- [ ] **Step 1: Run one real headless dispatch in a throwaway dir, capturing JSON**

```bash
mkdir -p /tmp/oc-probe && cd /tmp/oc-probe
opencode run "Reply with the single word: ok" -m opencode/gemini-3.1-pro --format json > /tmp/oc-probe/out.json 2>/tmp/oc-probe/err.log
echo "exit=$?"; wc -c /tmp/oc-probe/out.json
```
Expected: exit 0, a non-empty JSON file. (If `opencode/gemini-3.1-pro` errors, retry with an id from `opencode models`.)

- [ ] **Step 2: Inspect the JSON shape — where are the token counts?**

```bash
python -c "import json,sys; d=json.load(open('/tmp/oc-probe/out.json')); print(type(d)); print(json.dumps(d, indent=2)[:1500])"
```
Record: is it a single object or a list of events? Where do input/output token counts live (keys/path)? Note this in `opencode-cli-notes.md`. If tokens are NOT in `--format json`, run `opencode stats` and note its shape as the fallback source.

- [ ] **Step 3: Save the sample + notes into the repo (test fixture for T4)**

```bash
cp /tmp/oc-probe/out.json /d/claude_server/cross-llm-delivery/docs/notes/opencode-run-sample.json
```
Write `docs/notes/opencode-cli-notes.md` documenting: the exact token key-path, whether `--format json` or `opencode stats` is the token source, and any Windows `opencode.cmd` note.

- [ ] **Step 4: Commit**

```bash
cd /d/claude_server/cross-llm-delivery
git add docs/notes/opencode-run-sample.json docs/notes/opencode-cli-notes.md
git commit -m "docs(opencode): capture real --format json output + token key-path (T4 fixture)"
```

**Acceptance:** a real sample JSON is committed; the token key-path (or `opencode stats` fallback) is documented.

---

## Task 2: Extract shared `capture_diff`  [CLAUDE — refactor]

**Files:**
- Create: `src/cld/executors/_capture.py`
- Modify: `src/cld/executors/gemini.py` (replace the inline capture block)
- Test: `tests/executors/test_capture.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/executors/test_capture.py
from cld.executors._capture import capture_diff


class _Runner:
    """Returns canned output per matched git subcommand."""
    def __init__(self, diff="--- a\n+++ b\n+x\n", names="src/a.py\nsrc/b.py\n"):
        self.calls = []
        self._diff = diff
        self._names = names

    def __call__(self, args, cwd):
        self.calls.append(args)
        joined = " ".join(args)
        if "--name-only" in args:
            return (0, self._names)
        if "diff" in args:
            return (0, self._diff)
        return (0, "")  # git add --intent-to-add


def test_capture_diff_stages_then_returns_diff_and_files():
    r = _Runner()
    diff, files = capture_diff(r, "/work")
    assert diff == "--- a\n+++ b\n+x\n"
    assert files == ["src/a.py", "src/b.py"]
    # it must `git add --intent-to-add -A` BEFORE diffing (so new files show)
    assert r.calls[0] == ["git", "add", "--intent-to-add", "-A"]
    # and it ran in the given cwd
    # (cwd is passed through to the runner; _Runner ignores it but real runner uses it)


def test_capture_diff_empty():
    r = _Runner(diff="", names="")
    diff, files = capture_diff(r, "/work")
    assert diff == ""
    assert files == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/executors/test_capture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cld.executors._capture'`.

- [ ] **Step 3: Implement `_capture.py`**

```python
# src/cld/executors/_capture.py
"""Shared worktree diff capture, used by every CLI executor.

`git diff HEAD` omits UNTRACKED new files, so we `git add --intent-to-add -A`
first (Bug1/Defect1 fix) — created slice files then appear in the diff."""
from typing import Callable

Runner = Callable[[list[str], str], tuple[int, str]]


def capture_diff(runner: Runner, cwd: str) -> tuple[str, list[str]]:
    """Stage (intent-to-add) then capture (diff, files_changed) for the worktree."""
    runner(["git", "add", "--intent-to-add", "-A"], cwd)
    _, diff = runner(["git", "diff", "HEAD"], cwd)
    _, names = runner(["git", "diff", "HEAD", "--name-only"], cwd)
    files_changed = [line.strip() for line in names.splitlines() if line.strip()]
    return diff, files_changed
```

- [ ] **Step 4: Rewire `GeminiExecutor` to use it**

In `src/cld/executors/gemini.py`, add the import near the top:
```python
from cld.executors._capture import capture_diff
```
Replace the inline capture block (the `git add --intent-to-add`, two `git diff` calls, and `files_changed` list-comp) with:
```python
        diff, files_changed = capture_diff(self._runner, cwd)
```
(Keep the `token_usage = parse_token_usage(raw)` line and the `return ExecutorResult(...)` unchanged.)

- [ ] **Step 5: Run capture tests + existing gemini tests (behavior preserved)**

Run: `python -m pytest tests/executors/test_capture.py tests/executors/test_gemini.py -q`
Expected: all PASS (the gemini tests prove the extraction didn't change behavior).

- [ ] **Step 6: Commit**

```bash
git add src/cld/executors/_capture.py src/cld/executors/gemini.py tests/executors/test_capture.py
git commit -m "refactor(exec): extract shared capture_diff; GeminiExecutor reuses it"
```

**Acceptance:** `capture_diff` is shared; gemini tests still green.

---

## Task 3: `OpenCodeExecutor` (the seam)  [CLAUDE]

**Files:**
- Create: `src/cld/executors/opencode.py`
- Test: `tests/executors/test_opencode.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/executors/test_opencode.py
from cld.executors.base import Executor, ExecutorResult, SliceTask
from cld.executors.opencode import OpenCodeExecutor


class RecordingRunner:
    """Matches a substring of the command, returns canned (rc, out); records argv."""
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def __call__(self, args, cwd):
        self.calls.append((args, cwd))
        joined = " ".join(args)
        for match, rc, out in self._responses:
            if match in joined:
                return (rc, out)
        return (0, "")


def _ok_runner(diff="--- a\n+++ b\n+x\n"):
    return RecordingRunner([
        ("opencode", 0, '{"usage": {"input": 10, "output": 5}}'),
        ("--name-only", 0, "src/x.py\n"),
        ("diff", 0, diff),
    ])


def test_satisfies_protocol():
    assert isinstance(OpenCodeExecutor(runner=_ok_runner()), Executor)


def test_builds_locked_argv():
    runner = _ok_runner()
    ex = OpenCodeExecutor(runner=runner, model="anthropic/claude-sonnet-4-6")
    task = SliceTask(id="T", brief="do the thing", files=["src/x.py"],
                     acceptance_test_path="tests/test_x.py")
    ex.run(task, "/work")
    argv = runner.calls[0][0]
    assert argv[0] in ("opencode", "opencode.cmd")
    assert "run" in argv
    assert "-m" in argv and "anthropic/claude-sonnet-4-6" in argv
    assert "--format" in argv and "json" in argv
    assert "--dir" in argv and "/work" in argv
    assert "do the thing" in " ".join(argv)  # prompt carries the brief


def test_captures_diff_and_files():
    ex = OpenCodeExecutor(runner=_ok_runner(diff="DIFF"))
    task = SliceTask(id="T", brief="b", files=["src/x.py"], acceptance_test_path="t.py")
    res = ex.run(task, "/work")
    assert isinstance(res, ExecutorResult)
    assert res.ok is True
    assert res.diff == "DIFF"
    assert res.files_changed == ["src/x.py"]


def test_nonzero_dispatch_not_ok():
    runner = RecordingRunner([("opencode", 1, "boom: model unavailable")])
    ex = OpenCodeExecutor(runner=runner)
    task = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    res = ex.run(task, "/work")
    assert res.ok is False
    assert "boom" in res.raw_log
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/executors/test_opencode.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cld.executors.opencode'`.

- [ ] **Step 3: Implement `opencode.py`**

```python
# src/cld/executors/opencode.py
"""OpenCodeExecutor — adapts the OpenCode CLI to the Executor protocol.

    opencode run "<prompt>" -m <provider/model> --format json --dir <wt>

Mirrors GeminiExecutor: build argv, run via the injected runner, parse OpenCode's
token usage, capture the diff via the shared capture_diff. Windows resolves
`opencode.cmd`; override with OPENCODE_CLI_CMD."""
import os
import subprocess
from pathlib import Path
from typing import Callable

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask

Runner = Callable[[list[str], str], tuple[int, str]]
DEFAULT_MODEL = "opencode/gemini-3.1-pro"


def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return (proc.returncode, out)


class OpenCodeExecutor:
    def __init__(self, *, runner: Runner = _default_runner, model: str = DEFAULT_MODEL,
                 variant: str | None = None):
        self._runner = runner
        self._model = model
        self._variant = variant

    def _build_prompt(self, task: SliceTask, feedback: str | None = None) -> str:
        allowed = ", ".join(task.files)
        prompt = (
            f"Implement the following so that the acceptance tests pass.\n\n"
            f"{task.brief}\n\n"
            f"You may only create/modify these files: {allowed}\n"
            f"Acceptance tests: {task.acceptance_test_path}\n"
            f"Do not edit the test file. Run pytest yourself and iterate until green."
        )
        if feedback:
            prompt += (f"\n\nYour previous attempt did not pass. {feedback}\n"
                       f"Address this specifically before trying again.")
        return prompt

    def run(self, task: SliceTask, workdir: Path, feedback: str | None = None) -> ExecutorResult:
        from cld.executors.opencode import parse_opencode_usage  # late import; defined in T4
        cwd = str(workdir)
        prompt = self._build_prompt(task, feedback)
        oc = os.environ.get("OPENCODE_CLI_CMD") or (
            "opencode.cmd" if os.name == "nt" else "opencode")
        argv = [oc, "run", prompt, "-m", self._model, "--format", "json", "--dir", cwd]
        if self._variant:
            argv += ["--variant", self._variant]
        rc, raw = self._runner(argv, cwd)
        if rc != 0:
            return ExecutorResult(ok=False, diff="", raw_log=raw)
        token_usage = parse_opencode_usage(raw)
        diff, files_changed = capture_diff(self._runner, cwd)
        return ExecutorResult(ok=True, diff=diff, files_changed=files_changed,
                              token_usage=token_usage, raw_log=raw)


def parse_opencode_usage(raw_json: str) -> dict[str, int]:
    """Placeholder — replaced in T4 against the REAL captured JSON. Best-effort: {}."""
    return {}
```

(Note: `parse_opencode_usage` is a stub here so T3's tests pass; T4 replaces it with the real
parser written against the captured sample. The stub returns `{}`, which the T3 tests tolerate.)

- [ ] **Step 4: Run tests to verify they pass + full suite**

Run: `python -m pytest tests/executors/test_opencode.py -q && python -m pytest -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/cld/executors/opencode.py tests/executors/test_opencode.py
git commit -m "feat(opencode): OpenCodeExecutor seam (argv, capture via shared helper)"
```

**Acceptance:** OpenCodeExecutor satisfies the protocol; builds the locked argv; captures diff; `ok=False` on nonzero.

---

## Task 4: `parse_opencode_usage` against the real JSON  [DOGFOOD — Gemini]

**Files:**
- Modify: `src/cld/executors/opencode.py` (replace the stub)
- Test: `tests/executors/test_opencode_usage.py`

- [ ] **Step 1: Write the failing test using the REAL captured sample (T1)**

```python
# tests/executors/test_opencode_usage.py
import json
from pathlib import Path

from cld.executors.opencode import parse_opencode_usage

_SAMPLE = (Path(__file__).resolve().parents[2] / "docs" / "notes" /
           "opencode-run-sample.json")  # tests/executors/ -> repo root is parents[2]


def test_parses_real_sample_tokens():
    raw = _SAMPLE.read_text(encoding="utf-8")
    usage = parse_opencode_usage(raw)
    # The exact assertions are filled in from the captured sample's token key-path
    # (documented in docs/notes/opencode-cli-notes.md). At minimum: usage is a dict
    # of int values and includes a positive total or input+output.
    assert isinstance(usage, dict)
    assert all(isinstance(v, int) for v in usage.values())
    assert sum(usage.values()) > 0  # the real sample consumed tokens


def test_unparseable_returns_empty():
    assert parse_opencode_usage("not json") == {}
    assert parse_opencode_usage("{}") == {}
```

(When writing this test, replace the loose `sum>0` assertion with the EXACT expected counts read
from `docs/notes/opencode-run-sample.json` per `opencode-cli-notes.md` — the dogfood brief will
include the concrete key-path so Gemini implements against the real shape, and the test asserts
the real numbers.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/executors/test_opencode_usage.py -v`
Expected: FAIL — the stub returns `{}`, so `sum(usage.values()) > 0` fails.

- [ ] **Step 3: DOGFOOD — dispatch `parse_opencode_usage` to Gemini**

Write `docs/notes/opencode-usage-brief.md`: implement `parse_opencode_usage(raw_json) -> dict[str,int]`
in `src/cld/executors/opencode.py` so `tests/executors/test_opencode_usage.py` passes. Pin the
EXACT token key-path from `opencode-cli-notes.md` (e.g. "tokens at `<path>`; map to input/output/
total"). Must return `{}` on unparseable input (try/except). stdlib only.
Dispatch via the standard dogfood flow (commit failing test → worktree → `gemini` → judge → merge).

- [ ] **Step 4: Judge + full suite**

Run (independently, not trusting the executor): `python -m pytest tests/executors/test_opencode_usage.py -q && python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit (merge of the dogfood)**

```bash
git commit -m "feat(opencode): parse_opencode_usage against real JSON (Gemini-built, Claude-judged)"
```

**Acceptance:** the real sample's token counts are parsed; unparseable → `{}`.

---

## Task 5: Register `opencode` in the executor registry  [CLAUDE — trivial]

**Files:**
- Modify: `src/cld/executors/__init__.py`
- Test: `tests/executors/test_registry.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
def test_get_opencode():
    from cld.executors import get_executor, KNOWN_EXECUTORS
    from cld.executors.opencode import OpenCodeExecutor
    ex = get_executor("opencode", model="opencode/gemini-3.1-pro")
    assert isinstance(ex, OpenCodeExecutor)
    assert "opencode" in KNOWN_EXECUTORS
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/executors/test_registry.py -k opencode -v`
Expected: FAIL — `ValueError: Unknown executor: 'opencode'`.

- [ ] **Step 3: Add the branch**

In `src/cld/executors/__init__.py`:
- change `KNOWN_EXECUTORS = ("gemini", "composer")` → `KNOWN_EXECUTORS = ("gemini", "composer", "opencode")`
- add before the `else:`:
```python
    elif clean_name == "opencode":
        from cld.executors.opencode import OpenCodeExecutor
        return OpenCodeExecutor(**kwargs)
```

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/executors/test_registry.py -q && python -m pytest -q`
Expected: PASS. (`--executor opencode:provider/model` now works end-to-end via the existing parser.)

- [ ] **Step 5: Commit**

```bash
git add src/cld/executors/__init__.py tests/executors/test_registry.py
git commit -m "feat(registry): register opencode executor"
```

**Acceptance:** `get_executor("opencode")` returns an `OpenCodeExecutor`; in `KNOWN_EXECUTORS`.

---

## Task 6: Model catalog + `list_models`  [DOGFOOD — Gemini]

**Files:**
- Create: `src/cld/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from cld.models import MODEL_METADATA, list_models, ModelInfo


def test_metadata_has_seed_workhorse():
    # the proven flat-rate workhorse must be present and tagged correctly
    g = MODEL_METADATA["gemini:gemini-3.1-pro-preview"]
    assert g.cost_class == "flat"
    assert g.capability_class == "workhorse"
    assert g.headless_status == "proven"


def test_list_models_parses_opencode_output():
    def fake_runner(args, cwd):
        assert "models" in args
        return (0, "opencode/gemini-3.1-pro\nopencode/claude-opus-4-8\nopencode/deepseek-v4-flash-free\n")
    ids = list_models(runner=fake_runner)
    assert "opencode/gemini-3.1-pro" in ids
    assert "opencode/deepseek-v4-flash-free" in ids
    assert len(ids) == 3


def test_list_models_empty_on_failure():
    def boom(args, cwd):
        return (1, "opencode not found")
    assert list_models(runner=boom) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cld.models'`.

- [ ] **Step 3: DOGFOOD — dispatch `models.py` to Gemini**

Brief (`docs/notes/models-brief.md`): create `src/cld/models.py` so `tests/test_models.py` passes:
- `ModelInfo` dataclass: `id, provider, cost_class, capability_class, headless_status, rework_risk, note, last_validated=None`.
- `MODEL_METADATA: dict[str, ModelInfo]` — a curated SEED table. MUST include
  `"gemini:gemini-3.1-pro-preview"` = `cost_class="flat", capability_class="workhorse",
  headless_status="proven", rework_risk="low", note="our 14/14 workhorse"`. Add a handful more
  recommended entries (e.g. an opencode claude-opus as `premium-metered/heavy/likely`, a
  deepseek-free as `free/quick/untested`) — values are curation, the test only pins the gemini seed.
- `list_models(runner) -> list[str]`: run `["opencode", "models"]` via the injected runner, split
  stdout lines into ids; return `[]` if rc != 0. (Windows opencode.cmd handled by the caller's runner.)
- stdlib only. Pure aside from the injected runner.

- [ ] **Step 4: Judge + full suite**

Run: `python -m pytest tests/test_models.py -q && python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit (merge of the dogfood)**

```bash
git commit -m "feat(models): curated catalog + list_models (Gemini-built, Claude-judged)"
```

**Acceptance:** catalog has the proven workhorse seed; `list_models` parses `opencode models`; `[]` on failure.

---

## Task 7: `recommend()` — filter/bucket/annotate  [OPENCODE self-dogfood]

**Note:** this is the "OpenCode dogfoods itself" slice — by now `OpenCodeExecutor` (T3/T4) works,
so dispatch this pure-logic slice via `--executor opencode:opencode/gemini-3.1-pro` (a proven
model through OpenCode) to prove OpenCode as an executor on real work. If the OpenCode dispatch
fails for any reason, fall back to a Gemini dogfood — the slice is identical either way.

**Files:**
- Modify: `src/cld/models.py`
- Test: `tests/test_models.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
from cld.models import recommend, Recommendation


def test_recommend_filters_to_available_and_status():
    available = ["opencode/gemini-3.1-pro", "opencode/claude-opus-4-8",
                 "opencode/some-unknown-model"]
    recs = recommend(available_ids=available)
    ids = [r.id for r in recs]
    # only models that are BOTH in available AND in our curated catalog appear
    assert "opencode/some-unknown-model" not in ids
    # known-bad never appears; untested only with a warning flag
    for r in recs:
        assert r.headless_status in ("proven", "likely", "untested")
        if r.headless_status == "untested":
            assert r.warning  # untested carries a warning
        assert r.cost_class  # cost is always annotated
        assert r.why         # one-line rationale present


def test_recommend_default_is_proven_workhorse():
    recs = recommend(available_ids=["opencode/gemini-3.1-pro"])
    default = next(r for r in recs if r.is_default)
    assert default.capability_class == "workhorse"
    assert default.headless_status == "proven"


def test_recommend_buckets_by_job():
    available = ["opencode/gemini-3.1-pro", "opencode/claude-opus-4-8",
                 "opencode/deepseek-v4-flash-free"]
    recs = recommend(available_ids=available)
    buckets = {r.bucket for r in recs}
    assert "workhorse" in buckets
    # premium model is flagged as billed
    opus = next((r for r in recs if "opus" in r.id), None)
    if opus:
        assert opus.cost_class == "premium-metered"
        assert opus.confirm_cost is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_models.py -k recommend -v`
Expected: FAIL — `cannot import name 'recommend'`.

- [ ] **Step 3: DOGFOOD (OpenCode) — dispatch `recommend` to OpenCode**

Brief (`docs/notes/recommend-brief.md`): add to `src/cld/models.py`:
- `Recommendation` dataclass: `id, bucket, cost_class, headless_status, why, is_default=False,
  warning="", confirm_cost=False`.
- `recommend(*, available_ids, job=None) -> list[Recommendation]`: for each id in MODEL_METADATA
  that is ALSO in `available_ids`: skip `headless_status == "known-bad"`; build a Recommendation
  with `bucket=capability_class`, carry `cost_class`/`headless_status`/`note` (as `why`);
  `warning` set when `headless_status == "untested"`; `confirm_cost=True` when
  `cost_class == "premium-metered"`; mark exactly one `is_default=True` — the proven workhorse
  (prefer `gemini:gemini-3.1-pro-preview` if available, else the first `proven/workhorse`). Pure,
  stdlib only.
Dispatch via OpenCode (`--executor opencode:opencode/gemini-3.1-pro`); fall back to Gemini if needed.

- [ ] **Step 4: Judge + full suite**

Run: `python -m pytest tests/test_models.py -q && python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit (merge)**

```bash
git commit -m "feat(models): recommend() filter/bucket/annotate (OpenCode-built, Claude-judged)"
```

**Acceptance:** `recommend` returns only available+catalogued models, status-gated, bucketed, with default + cost-confirm flags. (Proves OpenCode as an executor.)

---

## Task 8: `validate_model` harness  [CLAUDE]

**Files:**
- Create: `src/cld/validate.py`
- Test: `tests/test_validate.py`

- [ ] **Step 1: Write the failing test (real git, fake executors)**

```python
# tests/test_validate.py
import pytest
from pathlib import Path

from cld.executors.base import ExecutorResult, SliceTask
from cld.validate import validate_model, ValidationResult
from tests.integration.harness import init_repo, real_git_runner

pytestmark = pytest.mark.integration


class _PassExec:
    """Writes calc.py that satisfies the trivial known-answer test."""
    def run(self, task, workdir, feedback=None):
        p = Path(workdir) / "calc.py"
        p.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        real_git_runner(["git", "add", "--intent-to-add", "-A"], str(workdir))
        return ExecutorResult(ok=True, diff="+x", files_changed=["calc.py"], raw_log="")


class _FailExec:
    """Writes WRONG code so the acceptance test fails."""
    def run(self, task, workdir, feedback=None):
        p = Path(workdir) / "calc.py"
        p.write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
        real_git_runner(["git", "add", "--intent-to-add", "-A"], str(workdir))
        return ExecutorResult(ok=True, diff="+x", files_changed=["calc.py"], raw_log="")


def test_validate_promotes_to_proven_on_pass(tmp_path):
    res = validate_model("opencode/x", executor=_PassExec(),
                         git_runner=real_git_runner, base_dir=str(tmp_path))
    assert isinstance(res, ValidationResult)
    assert res.passed is True
    assert res.status == "proven"


def test_validate_marks_known_bad_on_fail(tmp_path):
    res = validate_model("opencode/x", executor=_FailExec(),
                         git_runner=real_git_runner, base_dir=str(tmp_path))
    assert res.passed is False
    assert res.status == "known-bad"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cld.validate'`.

- [ ] **Step 3: Implement `validate.py`**

```python
# src/cld/validate.py
"""Evidence-backed headless validation: does a model actually build a trivial slice?

Spins a throwaway git repo with a known-answer slice (`add(a,b)`), dispatches it to the
model via the given executor, runs the REAL acceptance test (scoped — Bug B), and reports
whether it produced PASSING code. Promotes headless_status from assertion to proof."""
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cld.executors.base import SliceTask
from cld.judge import judge

_TEST_SRC = (
    "from calc import add\n\n"
    "def test_add():\n    assert add(2, 3) == 5\n"
)


@dataclass
class ValidationResult:
    model: str
    passed: bool
    status: str          # "proven" | "known-bad" | "untested"
    attempts: int
    note: str = ""


def _pytest(workdir: str, test_path: str) -> str:
    try:
        proc = subprocess.run([sys.executable, "-m", "pytest", test_path, "-q"],
                              cwd=workdir, capture_output=True, text=True, timeout=120)
        return (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return "1 failed in 120s (timeout)"


def validate_model(model: str, *, executor, git_runner, base_dir: str) -> ValidationResult:
    repo = os.path.join(base_dir, "validate-repo")
    init_dir = Path(repo)
    init_dir.mkdir(parents=True, exist_ok=True)
    # set up a real repo with the failing acceptance test committed
    for args in (["git", "init", "-q"],
                 ["git", "config", "user.email", "v@v.t"],
                 ["git", "config", "user.name", "v"],
                 ["git", "config", "commit.gpgsign", "false"]):
        git_runner(args, repo)
    (init_dir / "test_calc.py").write_text(_TEST_SRC, encoding="utf-8")
    git_runner(["git", "add", "-A"], repo)
    git_runner(["git", "commit", "-qm", "init"], repo)

    task = SliceTask(id="validate", brief="Implement add(a, b) returning a + b in calc.py.",
                     files=["calc.py"], acceptance_test_path="test_calc.py")
    try:
        result = executor.run(task, repo)
    except Exception as exc:  # executor blew up -> untested, not a model failure verdict
        return ValidationResult(model, False, "untested", 0, note=f"executor error: {exc}")

    jr = judge(files_changed=result.files_changed, allowed=task.files,
               run_tests=lambda: _pytest(repo, task.acceptance_test_path))
    if jr.passed:
        return ValidationResult(model, True, "proven", 1)
    return ValidationResult(model, False, "known-bad", 1,
                            note="; ".join(jr.failing_tests) or "acceptance test failed")
```
Add `from pathlib import Path` is already imported; ensure `init_dir.mkdir` parent exists.

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_validate.py -q && python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cld/validate.py tests/test_validate.py
git commit -m "feat(validate): evidence-backed headless validation harness"
```

**Acceptance:** pass → `proven`, fail → `known-bad`, executor error → `untested`; real test as judge.

---

## Task 9: SKILL.md picker behavior + global sync  [CLAUDE]

**Files:**
- Modify: `skill/SKILL.md`

- [ ] **Step 1: Add a "Choosing the executor/model" subsection**

In `skill/SKILL.md`, under the run section, add:

```markdown
### Choosing the executor & model (interactive picker)

When helping a user start a build (or when they ask "which model?"), present the recommended
shortlist and let them pick — the USER decides, never the orchestrator. The default is the proven
$0 flat-rate workhorse (`gemini:gemini-3.1-pro-preview`); "just go" needs no decision.

To build the shortlist: run `opencode models` (via the project's runner) → `cld.models.list_models`
→ `cld.models.recommend(available_ids=...)`. Present buckets (workhorse / heavy / quick / free),
each line: `<executor:provider/model> · <cost_class> · <headless_status> · <why>`.

Rules:
- **Default pre-selected:** the proven workhorse. Pressing enter uses it.
- **Cost guardrail:** if the user picks a `premium-metered` model (`confirm_cost=True`), CONFIRM
  explicitly first: "This model bills real $ per dispatch (not flat-rate) — proceed?" Do not
  dispatch a premium model without that confirmation.
- **Headless warning:** an `untested` model carries "may not complete builds reliably — validate
  first?" Offer to run `cld.validate.validate_model` on it (one trivial slice) before trusting it.
- The choice maps to `--executor opencode:<provider/model>` (or `gemini:<model>`). Per-slice
  override via an `executor:` field in the plan is supported for "use the heavy model on this one
  hard slice."

Example:
    Recommended executors (installed + available):
      WORKHORSE (default)
      ▸ gemini:gemini-3.1-pro-preview      · $0 flat · proven   · best $/passing-slice; 14/14 workhorse
      HEAVY (hard slices, worth more $)
        opencode:anthropic/claude-opus-4-8 · premium ⚠ · likely · top capability; confirms cost
      QUICK / BUDGET
        opencode:deepseek-v4-flash-free    · free ⚠   · untested· cheap; validate before trusting
    Pick one [default: gemini workhorse]:
```

- [ ] **Step 2: Sync the global skill copy**

Run: `cp skill/SKILL.md ~/.claude/skills/cross-llm-delivery/SKILL.md`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs(skill): interactive model picker (default workhorse, cost + headless guardrails)"
```

**Acceptance:** SKILL.md documents the picker flow, default, cost-confirm, and headless-warning rules; global copy synced.

---

## Done criteria

- `--executor opencode:<provider/model>` runs a real OpenCode dispatch end-to-end (inherits Bug A/B, `--step`, timeout, feedback-loop).
- The picker presents a bucketed, available-filtered, status-gated shortlist with a default; premium models require cost confirmation; untested models warn + offer validation.
- `validate_model` promotes a model to `proven`/`known-bad` from a real-test verdict.
- OpenCode proved itself as an executor (T7 built via OpenCode).
- Full suite green; shared `capture_diff` keeps gemini tests passing.
