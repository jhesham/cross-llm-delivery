# Complete Windows Headless Provider Dispatch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `antigravity` provider and fix the `cursor` Windows direct-node dispatch, clearing the post-rebuild queue.

**Architecture:** Two independent workstreams. Part A adds `engine/cld_providers/antigravity/` (executor that runs `agy` with cwd on the C: drive and captures the reply from the per-dispatch transcript.jsonl), makes its Gemini 3.1 Pro (High) the default workhorse, and demotes the dead `gemini` provider. Part B swaps the cursor executor from the `.cmd` shim to direct `node index.js` invocation. A final controller-run live-validation confirms on-disk writes and applies trust promotions.

**Tech Stack:** Python 3.11+ stdlib only. pytest. The existing `Provider`/`Executor` plugin architecture.

**Spec:** `docs/superpowers/specs/2026-06-22-complete-headless-provider-dispatch-design.md`.

## Global Constraints

- Python 3.11+, standard library only. Trunk-based on `master` (no feature branch); commit per task.
- Test command: `python -m pytest <args> -q -p no:warnings` (a teardown plugin may swallow the summary line — confirm via dots / exit 0). The full existing suite (currently 360) MUST stay green.
- Windows discipline: every subprocess uses `encoding="utf-8", errors="replace"`; cp1252-safe output.
- Provider contract (`engine/cld/providers_api.py`): `Provider(name, make_executor, catalog, default_workhorse, list_models, account_stats, account_block, account_section=None, skill_fragment="", setup_notes="")`. Executor: `run(task: SliceTask, workdir, feedback=None) -> ExecutorResult(ok, diff, files_changed, token_usage, raw_log)`. Diffs via `cld.executors._capture.capture_diff(runner, cwd)`. `ModelInfo(id, provider, cost_class, capability_class, headless_status, rework_risk, note, tier)`.
- Runner type: `Callable[[list[str], str], tuple[int, str]]` (`(args, cwd) -> (rc, combined_output)`), injectable per executor for testing.
- Trust vocabulary: `verified` / `likely` / `untested` / `revalidate` (auto-routing skips `revalidate`).
- NO automated test may invoke a real cloud CLI. Live validation is a manual, controller-run step (Task V1).

---

## Part A — the `antigravity` provider

### Task A1: Pure helpers for transcript capture

**Files:**
- Create: `engine/cld_providers/antigravity/__init__.py` (one line: `from . import provider  # noqa: F401`)
- Create: `engine/cld_providers/antigravity/provider.py` (helpers only in this task; executor/catalog added later)
- Test: `tests/executors/test_antigravity.py`

**Interfaces:**
- Produces (consumed by A2): `_dispatch_cwd() -> str`, `_parse_conversation_id(log_text: str) -> str | None`, `_transcript_path(home: str, conversation_id: str) -> str`, `_extract_model_reply(transcript_text: str) -> str | None`.

- [ ] **Step 1: Write the failing tests** (`tests/executors/test_antigravity.py`)

```python
import os
from pathlib import Path
from cld_providers.antigravity.provider import (
    _dispatch_cwd, _parse_conversation_id, _transcript_path, _extract_model_reply,
)


def test_dispatch_cwd_is_on_system_drive():
    cwd = _dispatch_cwd()
    sysdrive = os.environ.get("SystemDrive", "C:")
    # the dispatch cwd must live on the system drive so agy's POSIX /Users/... path resolves
    assert cwd.upper().startswith(sysdrive.upper())


def test_parse_conversation_id_picks_most_frequent_uuid():
    log = (
        "I0622 server.go:840] Stream goroutine exited for 4479fde7-507f-4dd9-83c3-f23ce0fe36bd\n"
        "I0622 conversation_manager.go:601] Stream completed for 4479fde7-507f-4dd9-83c3-f23ce0fe36bd\n"
        "I0622 something about aaaaaaaa-1111-2222-3333-444444444444 once\n"
    )
    assert _parse_conversation_id(log) == "4479fde7-507f-4dd9-83c3-f23ce0fe36bd"


def test_parse_conversation_id_none_when_absent():
    assert _parse_conversation_id("no uuids here") is None


def test_transcript_path_layout():
    p = _transcript_path("C:\\Users\\Administrator", "abc")
    assert p.endswith(os.path.join(
        ".gemini", "antigravity-cli", "brain", "abc", ".system_generated", "logs", "transcript.jsonl"))


def test_extract_model_reply_joins_model_steps():
    transcript = (
        '{"step_index":0,"source":"USER_EXPLICIT","content":"hi"}\n'
        '{"step_index":3,"source":"MODEL","type":"PLANNER_RESPONSE","content":"READY"}\n'
        '{"step_index":4,"source":"SYSTEM","content":"ignore me"}\n'
    )
    assert _extract_model_reply(transcript) == "READY"


def test_extract_model_reply_none_when_no_model_step():
    assert _extract_model_reply('{"source":"USER_EXPLICIT","content":"hi"}\n') is None
    assert _extract_model_reply("not json\n\n") is None
```

- [ ] **Step 2: Run red** — `python -m pytest tests/executors/test_antigravity.py -q -p no:warnings`. Expected: ImportError (module missing).

- [ ] **Step 3: Implement** (`engine/cld_providers/antigravity/provider.py`)

```python
"""Antigravity provider plugin — the `agy` CLI executor.

Windows gotcha: `agy` writes the model reply to a transcript file under a POSIX
path (/Users/<name>/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/
transcript.jsonl). A leading-/ path resolves to the current drive's root on
Windows, so the dispatch must run with cwd on the C: drive. stdout is empty by
design — the reply lives in the transcript. See docs/notes/antigravity-cli-notes.md.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path


def _dispatch_cwd() -> str:
    """User home forced onto SystemDrive, so agy's POSIX transcript path resolves."""
    home = Path.home()
    sysdrive = os.environ.get("SystemDrive", "C:")
    if (home.drive or "").upper() != sysdrive.upper():
        return str(Path(sysdrive + os.sep) / "Users" / home.name)
    return str(home)


_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _parse_conversation_id(log_text: str) -> str | None:
    """The per-dispatch conversation id is the most frequently-occurring UUID in the log."""
    ids = _UUID_RE.findall(log_text or "")
    if not ids:
        return None
    return Counter(ids).most_common(1)[0][0]


def _transcript_path(home: str, conversation_id: str) -> str:
    return os.path.join(home, ".gemini", "antigravity-cli", "brain", conversation_id,
                        ".system_generated", "logs", "transcript.jsonl")


def _extract_model_reply(transcript_text: str) -> str | None:
    """Join the `content` of every JSONL step whose source is MODEL; None if none."""
    replies = []
    for line in (transcript_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("source") == "MODEL" and obj.get("content"):
            replies.append(str(obj["content"]))
    return "\n".join(replies) if replies else None
```

- [ ] **Step 4: Run green** — `python -m pytest tests/executors/test_antigravity.py -q -p no:warnings` (PASS), then full suite stays green.
- [ ] **Step 5: Commit**

```bash
git add engine/cld_providers/antigravity/__init__.py engine/cld_providers/antigravity/provider.py tests/executors/test_antigravity.py
git commit -m "feat(antigravity): transcript-capture helpers (cwd-on-C, conversation-id, reply parse)"
```

---

### Task A2: `AntigravityExecutor`

**Files:**
- Modify: `engine/cld_providers/antigravity/provider.py` (append executor + runner + cmd resolver)
- Test: `tests/executors/test_antigravity.py` (append)

**Interfaces:**
- Consumes: the A1 helpers; `cld.executors._capture.capture_diff`; `cld.executors.base.{ExecutorResult, SliceTask}`.
- Produces (consumed by A3): `AntigravityExecutor(*, runner=_default_runner, model=DEFAULT_MODEL, effort=None, home=None)`; `DEFAULT_MODEL = "Gemini 3.1 Pro (High)"`; `_default_runner(args, cwd) -> (rc, out)`; `_agy_cmd() -> str`.

- [ ] **Step 1: Write the failing tests** (append)

```python
from cld.executors.base import Executor, ExecutorResult, SliceTask
from cld_providers.antigravity.provider import AntigravityExecutor


class _Runner:
    """Injected runner. Writes the agy --log-file as a side effect (simulating agy),
    and answers git capture_diff calls."""
    def __init__(self, conv_id, *, dispatch_rc=0, diff="--- a\n+++ b\n+x\n", names="src/x.py\n"):
        self.conv_id = conv_id; self.dispatch_rc = dispatch_rc
        self.diff = diff; self.names = names; self.calls = []

    def __call__(self, args, cwd):
        self.calls.append((args, cwd))
        joined = " ".join(args)
        if "-p" in args and "--add-dir" in args:           # the agy dispatch
            # simulate agy writing its --log-file with the conversation id in it
            i = args.index("--log-file"); log = args[i + 1]
            Path(log).write_text(f"Stream completed for {self.conv_id}\n", encoding="utf-8")
            return (self.dispatch_rc, "")                    # stdout empty by design
        if "--name-only" in joined:
            return (0, self.names)
        if "diff" in joined:
            return (0, self.diff)
        return (0, "")


def _seed_transcript(home: Path, conv_id: str, content="READY"):
    d = home / ".gemini" / "antigravity-cli" / "brain" / conv_id / ".system_generated" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    (d / "transcript.jsonl").write_text(
        '{"source":"MODEL","type":"PLANNER_RESPONSE","content":"%s"}\n' % content, encoding="utf-8")


def _task():
    return SliceTask(id="T", brief="do the thing", files=["src/x.py"],
                     acceptance_test_path="tests/test_x.py")


def test_satisfies_protocol(tmp_path):
    assert isinstance(AntigravityExecutor(runner=_Runner("c"), home=str(tmp_path)), Executor)


def test_dispatch_argv_shape(tmp_path):
    conv = "11111111-1111-1111-1111-111111111111"
    _seed_transcript(tmp_path, conv)
    r = _Runner(conv)
    ex = AntigravityExecutor(runner=r, model="Gemini 3.1 Pro (High)", home=str(tmp_path))
    ex.run(_task(), str(tmp_path / "wt"))
    argv, cwd = r.calls[0]
    assert "-p" in argv
    assert "--model" in argv and "Gemini 3.1 Pro (High)" in argv
    assert "--add-dir" in argv and str(tmp_path / "wt") in argv
    assert "--dangerously-skip-permissions" in argv
    assert "--log-file" in argv
    assert cwd == str(tmp_path)                              # dispatch cwd = home (on C:), NOT the worktree


def test_success_reads_reply_and_diff(tmp_path):
    conv = "22222222-2222-2222-2222-222222222222"
    _seed_transcript(tmp_path, conv, content="DONE")
    ex = AntigravityExecutor(runner=_Runner(conv, diff="DIFF"), home=str(tmp_path))
    res = ex.run(_task(), str(tmp_path / "wt"))
    assert res.ok is True and res.diff == "DIFF" and res.files_changed == ["src/x.py"]
    assert "DONE" in res.raw_log


def test_nonzero_dispatch_not_ok(tmp_path):
    ex = AntigravityExecutor(runner=_Runner("c", dispatch_rc=1), home=str(tmp_path))
    res = ex.run(_task(), str(tmp_path / "wt"))
    assert res.ok is False


def test_missing_transcript_not_ok_with_hint(tmp_path):
    # runner reports success + a conv id, but no transcript on disk -> ok False + cwd hint
    ex = AntigravityExecutor(runner=_Runner("33333333-3333-3333-3333-333333333333"), home=str(tmp_path))
    res = ex.run(_task(), str(tmp_path / "wt"))
    assert res.ok is False and "C:" in res.raw_log
```

- [ ] **Step 2: Run red** — `python -m pytest tests/executors/test_antigravity.py -q -p no:warnings`. Expected: ImportError on `AntigravityExecutor`.

- [ ] **Step 3: Implement** (append to `provider.py`)

```python
import subprocess
import tempfile
from typing import Callable

from cld.executors._capture import capture_diff
from cld.executors.base import ExecutorResult, SliceTask

Runner = Callable[[list[str], str], tuple[int, str]]

DEFAULT_MODEL = "Gemini 3.1 Pro (High)"


def _agy_cmd() -> str:
    """Resolve the agy executable. AGY_CMD overrides; else the known install path; else 'agy'."""
    override = os.environ.get("AGY_CMD")
    if override:
        return override
    if os.name == "nt":
        cand = os.path.join(os.environ.get("LOCALAPPDATA", ""), "agy", "bin", "agy.exe")
        if os.path.exists(cand):
            return cand
    return "agy"


def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Real subprocess runner: stdin closed (agy waits on a TTY otherwise), utf-8/replace."""
    proc = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return (proc.returncode, out)


class AntigravityExecutor:
    """Executor backed by the Antigravity CLI (`agy`)."""

    def __init__(self, *, runner: Runner = _default_runner, model: str = DEFAULT_MODEL,
                 effort: str | None = None, home: str | None = None):
        # effort accepted for a uniform interface; antigravity bakes effort into the model label
        self._runner = runner
        self._model = model
        self._home = home or _dispatch_cwd()

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

    def run(self, task: SliceTask, workdir, feedback: str | None = None) -> ExecutorResult:
        prompt = self._build_prompt(task, feedback)
        fd, log_file = tempfile.mkstemp(prefix="agy_", suffix=".log")
        os.close(fd)
        try:
            dispatch = [
                _agy_cmd(), "-p", prompt, "--model", self._model,
                "--add-dir", str(workdir), "--dangerously-skip-permissions",
                "--log-file", log_file,
            ]
            rc, raw = self._runner(dispatch, self._home)   # cwd = home on C:
            if rc != 0:
                return ExecutorResult(ok=False, diff="", raw_log=raw)

            try:
                log_text = Path(log_file).read_text(encoding="utf-8", errors="replace")
            except OSError:
                log_text = ""
            log_text = (raw or "") + "\n" + log_text       # raw carries it in tests; log file in prod

            reply = None
            conv = _parse_conversation_id(log_text)
            if conv:
                try:
                    reply = _extract_model_reply(
                        Path(_transcript_path(self._home, conv)).read_text(
                            encoding="utf-8", errors="replace"))
                except OSError:
                    reply = None
            if reply is None:
                return ExecutorResult(
                    ok=False, diff="",
                    raw_log=(raw or "") + "\n[antigravity] no MODEL transcript found; the agy "
                            "dispatch must run with cwd on the C: drive (see "
                            "docs/notes/antigravity-cli-notes.md)")

            diff, files_changed = capture_diff(self._runner, str(workdir))
            return ExecutorResult(ok=True, diff=diff, files_changed=files_changed,
                                  token_usage={}, raw_log=reply)
        finally:
            try:
                os.unlink(log_file)
            except OSError:
                pass
```

- [ ] **Step 4: Run green + full suite.**
- [ ] **Step 5: Commit**

```bash
git add engine/cld_providers/antigravity/provider.py tests/executors/test_antigravity.py
git commit -m "feat(antigravity): AntigravityExecutor (cwd-on-C dispatch, transcript-read capture)"
```

---

### Task A3: Catalog + provider registration + fragment/setup

**Files:**
- Modify: `engine/cld_providers/antigravity/provider.py` (append catalog + PROVIDER + register)
- Create: `engine/cld_providers/antigravity/SKILL.fragment.md`
- Create: `engine/cld_providers/antigravity/setup.md`
- Test: `tests/test_providers_antigravity.py`

**Interfaces:**
- Consumes: `AntigravityExecutor`; `cld.models.ModelInfo`; `cld.providers_api.{Provider, register_provider}`.
- Produces: a registered `Provider(name="antigravity")` with 8 catalog ids and `default_workhorse="antigravity:Gemini 3.1 Pro (High)"`.

- [ ] **Step 1: Write the failing test** (`tests/test_providers_antigravity.py`)

```python
def test_antigravity_provider_registration():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    p = get_provider("antigravity")
    assert p.default_workhorse == "antigravity:Gemini 3.1 Pro (High)"
    ids = {m.id for m in p.catalog}
    assert len(ids) == 8
    assert "antigravity:Gemini 3.1 Pro (High)" in ids
    assert "antigravity:Claude Opus 4.6 (Thinking)" in ids
    # list_models returns the static 8 (agy models is TTY-only)
    assert len(p.list_models(lambda a, c: (0, ""))) == 8


def test_antigravity_tiers_and_buckets():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    by_id = {m.id: m for m in get_provider("antigravity").catalog}
    # exactly one quick-tier and one workhorse-tier model (deterministic auto-routing)
    workhorse_tier = [m.id for m in by_id.values() if m.tier == "workhorse"]
    quick_tier = [m.id for m in by_id.values() if m.tier == "quick"]
    assert workhorse_tier == ["antigravity:Gemini 3.1 Pro (High)"]
    assert quick_tier == ["antigravity:Gemini 3.5 Flash (Medium)"]
    # Opus is the heavy display bucket but NOT auto-routed (tier None)
    assert by_id["antigravity:Claude Opus 4.6 (Thinking)"].capability_class == "heavy"
    assert by_id["antigravity:Claude Opus 4.6 (Thinking)"].tier is None
    assert all(m.cost_class == "flat" for m in by_id.values())
```

- [ ] **Step 2: Run red** — `python -m pytest tests/test_providers_antigravity.py -q -p no:warnings`. Expected: ValueError "Unknown provider 'antigravity'".

- [ ] **Step 3: Implement** — create the two markdown files, then append the catalog + registration.

`engine/cld_providers/antigravity/SKILL.fragment.md`:
```markdown
### Antigravity (`agy`) executor

Antigravity is a flat-rate plan (quota-based; $0 marginal). It exposes Gemini, Claude and GPT-OSS
models — select with `--executor "antigravity:<label>"`, e.g. `antigravity:Claude Opus 4.6 (Thinking)`.
The default workhorse is `antigravity:Gemini 3.1 Pro (High)`.

Windows note: `agy` writes the model reply to a transcript file under `~/.gemini/antigravity-cli/`
using a POSIX path, so the executor runs the CLI with its working directory on the C: drive and reads
the reply from the latest transcript. Authenticate once interactively (`agy`, browser login) before
running headless builds.
```

`engine/cld_providers/antigravity/setup.md`:
```markdown
# Antigravity CLI setup

1. Install the Antigravity CLI; ensure `agy` (or `%LOCALAPPDATA%\agy\bin\agy.exe`) is on PATH.
2. Authenticate once: run `agy` interactively and complete the browser login (reuses `~/.gemini/`).
3. Verify: `agy models` (in an interactive terminal) lists your models.

Windows: the executor runs `agy` with cwd on the C: drive so its transcript path resolves; no action
needed beyond a standard C: user profile. Override the binary with `AGY_CMD` if installed elsewhere.
```

Append to `provider.py`:
```python
from cld.models import ModelInfo
from cld.providers_api import Provider, register_provider

_HERE = Path(__file__).parent
_SKILL_FRAGMENT = (_HERE / "SKILL.fragment.md").read_text(encoding="utf-8")
_SETUP_NOTES = (_HERE / "setup.md").read_text(encoding="utf-8")


def _m(label, capability_class, tier, headless_status, rework_risk, note):
    return ModelInfo(id=f"antigravity:{label}", provider="antigravity", cost_class="flat",
                     capability_class=capability_class, headless_status=headless_status,
                     rework_risk=rework_risk, note=note, tier=tier)


_CATALOG = (
    _m("Gemini 3.5 Flash (Low)",    "quick",     None,        "likely",   "low",
       "fast budget model; pin for trivial slices"),
    _m("Gemini 3.5 Flash (Medium)", "quick",     "quick",     "likely",   "low",
       "balanced budget workhorse; quick-tier auto-pick"),
    _m("Gemini 3.5 Flash (High)",   "quick",     None,        "likely",   "low",
       "budget model, more thinking; pin manually"),
    _m("Gemini 3.1 Pro (Low)",      "workhorse", None,        "likely",   "low",
       "Pro, lighter thinking; pin manually"),
    _m("Gemini 3.1 Pro (High)",     "workhorse", "workhorse", "likely",   "low",
       "default workhorse; flat-rate via Antigravity"),
    _m("GPT-OSS 120B (Medium)",     "workhorse", None,        "untested", "medium",
       "open model; validate before relying on it"),
    _m("Claude Sonnet 4.6 (Thinking)", "workhorse", None,     "likely",   "low",
       "strong workhorse; flat-rate via Antigravity; pin manually"),
    _m("Claude Opus 4.6 (Thinking)",   "heavy",     None,     "likely",   "low",
       "premium reasoning; flat-rate via Antigravity; pin manually for hard slices"),
)

_IDS = [m.id.split(":", 1)[1] for m in _CATALOG]

PROVIDER = Provider(
    name="antigravity",
    make_executor=lambda **k: AntigravityExecutor(**k),
    catalog=_CATALOG,
    default_workhorse="antigravity:Gemini 3.1 Pro (High)",
    list_models=lambda runner: list(_IDS),
    account_stats=None,
    account_block=None,
    skill_fragment=_SKILL_FRAGMENT,
    setup_notes=_SETUP_NOTES,
)

register_provider(PROVIDER)
```

- [ ] **Step 4: Run green + full suite.**
- [ ] **Step 5: Commit**

```bash
git add engine/cld_providers/antigravity/ tests/test_providers_antigravity.py
git commit -m "feat(antigravity): 8-model catalog + provider registration + fragment/setup"
```

---

### Task A4: Make antigravity the default workhorse

**Files:**
- Modify: `engine/cld/providers_api.py` (`default_workhorse()`)
- Test: `tests/test_providers_api.py` (append)

**Interfaces:**
- Consumes: the registry. Produces: `default_workhorse()` prefers antigravity over gemini.

- [ ] **Step 1: Write the failing test** (append to `tests/test_providers_api.py`)

```python
def test_default_workhorse_prefers_antigravity():
    from cld.providers_api import _REGISTRY, load_providers, default_workhorse
    _REGISTRY.clear(); load_providers()
    assert default_workhorse() == "antigravity:Gemini 3.1 Pro (High)"
```

- [ ] **Step 2: Run red** — `python -m pytest tests/test_providers_api.py -k default_workhorse_prefers_antigravity -q -p no:warnings`. Expected: FAIL (returns the gemini spec).

- [ ] **Step 3: Implement** — in `engine/cld/providers_api.py`, replace the `default_workhorse()` body's gemini preference with an ordered preference:

```python
_WORKHORSE_PREFERENCE = ("antigravity", "gemini")


def default_workhorse() -> str:
    """Return the spec for the default workhorse model.

    1. Exactly one provider registered  -> that provider's own default_workhorse.
    2. Multiple providers -> the first present provider in _WORKHORSE_PREFERENCE.
    3. Otherwise -> the first registered provider's default_workhorse.
    """
    providers = list(_REGISTRY.values())
    if len(providers) == 1:
        return providers[0].default_workhorse
    for name in _WORKHORSE_PREFERENCE:
        if name in _REGISTRY:
            return _REGISTRY[name].default_workhorse
    return providers[0].default_workhorse
```

- [ ] **Step 4: Run the full suite and fix fallout.** Changing the default workhorse is cross-cutting: existing picker/routing/recommend tests (e.g. in `tests/test_models.py`) may hardcode the old default spec `gemini:gemini-3.1-pro-preview` or assert a pre-antigravity shortlist. Run `python -m pytest -p no:warnings -q`; for every failure caused by the changed default, update the expectation to the new default `antigravity:Gemini 3.1 Pro (High)` (and the now-demoted gemini). These are legitimate expectation updates, NOT test weakenings — the behavior intentionally changed. Do not relax an assertion to `assert True` or delete coverage; re-point it to the new expected value. If a failure is NOT explained by the default change, stop and report it.
- [ ] **Step 5: Commit**

```bash
git add engine/cld/providers_api.py tests/
git commit -m "feat(engine): default_workhorse prefers antigravity over (deprecated) gemini"
```

---

### Task A5: Demote the `gemini` provider + update cross-provider regression

**Files:**
- Modify: `engine/cld_providers/gemini/provider.py` (`_GEMINI_MODEL_INFO`)
- Modify: `tests/test_providers_api.py` (the `test_assembled_catalog_has_expected_ids` count 9 -> 17)
- Test: `tests/test_providers_gemini.py` (append a demotion assertion)

**Interfaces:** Consumes the catalog; produces gemini marked `revalidate`.

- [ ] **Step 1: Write/adjust the failing tests**
  - In `tests/test_providers_gemini.py`, append:
```python
def test_gemini_demoted_to_revalidate():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    m = get_provider("gemini").catalog[0]
    assert m.headless_status == "revalidate"
```
  - In `tests/test_providers_api.py`, update `test_assembled_catalog_has_expected_ids`: change `assert len(ids) == 9` to `assert len(ids) == 17` and add `assert "antigravity:Gemini 3.1 Pro (High)" in ids`.

- [ ] **Step 2: Run red** — `python -m pytest tests/test_providers_gemini.py -k demoted tests/test_providers_api.py -k assembled_catalog -q -p no:warnings`. Expected: both FAIL.

- [ ] **Step 3: Implement** — in `engine/cld_providers/gemini/provider.py`, change `_GEMINI_MODEL_INFO`:
```python
    headless_status="revalidate",
    note="CLI deprecated 2026-06-21; superseded by antigravity. Historical adapter.",
```
(leave the rest of the ModelInfo unchanged).

- [ ] **Step 4: Run green + full suite** — confirm the whole suite is green with the new catalog count (17) and gemini demoted.
- [ ] **Step 5: Commit**

```bash
git add engine/cld_providers/gemini/provider.py tests/test_providers_gemini.py tests/test_providers_api.py
git commit -m "feat(gemini): demote to revalidate (CLI deprecated); catalog now 17 with antigravity"
```

---

## Part B — cursor direct-node dispatch fix

### Task B1: Replace the `.cmd` shim with direct-node invocation

**Files:**
- Modify: `engine/cld_providers/cursor/provider.py` (`_cursor_cmd` -> `_cursor_invocation`, `_default_runner`, `run()`, `account_stats()`)
- Test: `tests/executors/test_cursor.py` (retarget) + `tests/executors/test_cursor_invocation.py` (new)

**Interfaces:**
- Produces: `_cursor_invocation() -> list[str]` (direct-node argv prefix). `_default_runner` sets `stdin=DEVNULL` + `CURSOR_INVOKED_AS=cursor-agent`.

- [ ] **Step 1: Write the failing tests**

New file `tests/executors/test_cursor_invocation.py`:
```python
import os
from pathlib import Path
from cld_providers.cursor.provider import _cursor_invocation


def test_override_wins(monkeypatch):
    monkeypatch.setenv("CURSOR_AGENT_CMD", "/custom/cursor-agent")
    assert _cursor_invocation() == ["/custom/cursor-agent"]


def test_direct_node_prefix_on_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("CURSOR_AGENT_CMD", raising=False)
    monkeypatch.setattr(os, "name", "nt")
    base = tmp_path / "cursor-agent" / "versions"
    v = base / "2026.06.15"
    v.mkdir(parents=True)
    (v / "index.js").write_text("// entry", encoding="utf-8")
    (v / "node.exe").write_text("", encoding="utf-8")           # bundled node
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    inv = _cursor_invocation()
    assert inv[0].endswith("node.exe")                          # node, not the .cmd shim
    assert inv[1].endswith("index.js")
    assert not any(part.endswith(".cmd") for part in inv)
```

Append to `tests/executors/test_cursor.py` (and retarget the existing `_ok_runner`/argv tests to the new invocation — they assert `"cursor" in argv[0].lower()`, which still holds for `node.exe`/`index.js` paths containing "cursor-agent"; if any asserts a `.cmd`, change it):
```python
def test_dispatch_has_no_cmd_shim(monkeypatch, tmp_path):
    # with a fake versions dir, the dispatched argv must use index.js, not cursor-agent.cmd
    monkeypatch.delenv("CURSOR_AGENT_CMD", raising=False)
    monkeypatch.setattr(os, "name", "nt")
    v = tmp_path / "cursor-agent" / "versions" / "2026.06.15"
    v.mkdir(parents=True)
    (v / "index.js").write_text("//", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    runner = _ok_runner()
    CursorExecutor(runner=runner, model="composer-2.5").run(
        SliceTask(id="T", brief="b", files=["src/x.py"], acceptance_test_path="t.py"), "/work")
    argv = runner.calls[0][0]
    assert any(p.endswith("index.js") for p in argv)
    assert not any(p.endswith(".cmd") for p in argv)
```
(Add `import os` to `tests/executors/test_cursor.py` if absent.)

- [ ] **Step 2: Run red** — `python -m pytest tests/executors/test_cursor_invocation.py tests/executors/test_cursor.py -q -p no:warnings`. Expected: the new tests FAIL (`_cursor_invocation` missing; argv still uses `.cmd`).

- [ ] **Step 3: Implement** — in `engine/cld_providers/cursor/provider.py`:

Replace `_cursor_cmd()` with `_cursor_invocation()`:
```python
def _cursor_invocation() -> list[str]:
    """Argv prefix to launch cursor-agent. CURSOR_AGENT_CMD overrides (returns [override]).
    On Windows the .cmd shim mangles long prompts, so invoke the bundled Node entrypoint
    directly: [<node>, <version>/index.js]. Falls back to ['cursor-agent']."""
    override = os.environ.get("CURSOR_AGENT_CMD")
    if override:
        return [override]
    if os.name == "nt":
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "cursor-agent", "versions")
        try:
            versions = sorted((d for d in os.listdir(base)
                               if os.path.isdir(os.path.join(base, d))), reverse=True)
        except OSError:
            versions = []
        for v in versions:
            vdir = os.path.join(base, v)
            index_js = os.path.join(vdir, "index.js")
            if os.path.exists(index_js):
                bundled = os.path.join(vdir, "node.exe")
                node = bundled if os.path.exists(bundled) else "node"
                return [node, index_js]
    return ["cursor-agent"]
```

Update `_default_runner`:
```python
def _default_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Real subprocess runner. Direct-node cursor-agent needs CURSOR_INVOKED_AS set and
    stdin closed. utf-8/replace; stderr merged on failure for raw_log."""
    env = {**os.environ, "CURSOR_INVOKED_AS": "cursor-agent"}
    proc = subprocess.run(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return (proc.returncode, out)
```

In `run()`, change the argv head from `[_cursor_cmd(), ...]` to:
```python
        argv = [*_cursor_invocation(), "-p", prompt, "--output-format", "json",
                "--workspace", cwd, "--model", model_id, "--force", "--trust"]
```

In `account_stats()`, change `cmd = os.environ.get("CURSOR_AGENT_CMD") or _cursor_cmd()` and the `subprocess.run([cmd, "about"], ...)` to use the invocation list:
```python
    invocation = _cursor_invocation()
    try:
        proc = subprocess.run([*invocation, "about"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
        return proc.stdout or ""
    except Exception:
        return ""
```
(Update the module docstring's "Invocation form" note to mention direct-node; remove the stale `_cursor_cmd` references.)

- [ ] **Step 4: Run green + full suite** — the retargeted + new cursor tests pass; the whole suite stays green.
- [ ] **Step 5: Commit**

```bash
git add engine/cld_providers/cursor/provider.py tests/executors/test_cursor.py tests/executors/test_cursor_invocation.py
git commit -m "fix(cursor): direct-node dispatch (no .cmd shim) + CURSOR_INVOKED_AS + stdin closed"
```

---

## Task V1: Live validation + trust promotions  [CONTROLLER — manual, not a TDD subagent]

This task is run by the controller (it invokes the real CLIs, which need auth + write to disk). Do NOT dispatch it as an automated implementer. After A1–A5 and B1 are merged and green:

- [ ] **Antigravity live slice:** create a throwaway git worktree; build a real one-file slice via `AntigravityExecutor` (default model) with `--add-dir <worktree>`; confirm the file is written on disk and `capture_diff` returns it. Record evidence in `docs/notes/antigravity-cli-notes.md`.
- [ ] **Cursor live slice:** build a real long multi-line slice via `CursorExecutor` (direct-node); confirm it writes the file (the long-prompt path that previously broke). Record evidence in `docs/notes/cursor-cli-notes.md`.
- [ ] **On antigravity success:** dispatch a small subagent to flip the exercised model's `headless_status` `likely`->`verified` in `cld_providers/antigravity/provider.py` (+ its registration test), commit.
- [ ] **On cursor success:** dispatch a small subagent to (a) set `cursor:composer-2.5` `headless_status` `untested`->`verified` in `cld_providers/cursor/provider.py`; (b) remove the cursor exclusion in `engine/cld/models.py` (the `if id.startswith("cursor:"): continue` block at ~line 146-150) so cursor rejoins the `recommend()` shortlist; (c) update/del the test that asserts cursor is shortlist-excluded; commit.
- [ ] If either live step FAILS: capture evidence, leave that provider's trust as-is, and log a contained follow-up (the other provider is unaffected). Do NOT force promotions on failure.
- [ ] **Update STATUS.md:** post-rebuild queue cleared (note any residual live item); update the gemini/cursor/antigravity memory pointers.

---

## Done criteria
- `antigravity` provider registered (8 models); `default_workhorse()` == `antigravity:Gemini 3.1 Pro (High)`; `gemini` demoted to `revalidate`; assembled catalog count == 17.
- `cursor` executor dispatches via direct-node (`index.js`, no `.cmd`), with `CURSOR_INVOKED_AS` + `stdin=DEVNULL`.
- All new unit tests + the full existing suite green (no real-CLI calls in CI).
- Live validation done (or failures captured as contained follow-ups); trust promotions + cursor shortlist re-admission applied on success.
- STATUS.md updated; post-rebuild queue cleared.
