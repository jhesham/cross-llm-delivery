# v0.4.0 Review Fixes (R01–R06) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `--gc` safe (identity, ownership, binding, ignored data), key OpenCode evidence on config-referenced credentials, and classify late network failures — each red-first from the review's reproduction.

**Architecture:** GC moves from pure slug-based planning to an identity- and lock-aware `collect()` in `engine/cld/gc.py` that the CLI calls; admission gains a provider `config_env` hook; the orchestrator classifies failures from retained full output tails.

**Tech Stack:** Python 3.11+ stdlib, pytest, Git.

**Spec:** [SPEC.md](SPEC.md)

## Global Constraints

- Stdlib only; Python 3.11 compatible; Windows and POSIX.
- Fail closed: any missing, ambiguous or unverifiable identity, ownership or state → `keep`.
- Never touch `refs/cld/*` or `.cld/runs`.
- Each fix starts with the review's reproduction as a failing test.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Push, tag and publish only on the user's explicit go-ahead.

## Review Focus

1. A worktree whose evidence directory was deleted → kept, never removed — Task 3 `test_missing_evidence_keeps_worktree`.
2. `--gc` without `--include-previous` must never take another run's slice lock or remove its worktree — Task 4 `test_previous_run_untouched_without_include_previous`.
3. An ignored file inside a disposable cache directory (`.pytest_cache/v/x`) does not count as dirty, but `cache/x.db` does — Task 2 tests.
4. A ledger whose `build.repo` is the same path written differently (case or slash style on Windows) is not a mismatch — Task 1 `test_same_repo_different_spelling_is_accepted`.
5. A failed dispatch whose retained output files are missing still classifies from `raw_log` without error — Task 6 `test_missing_retained_files_fall_back_to_raw_log`.

---

### Task 1: R04 — GC repository binding

**Files:** Modify `engine/cld/cli.py` (`_gc_report`); Test `tests/v040/test_gc_safety.py` (create).

**Interfaces:** Produces `cld.cli._check_gc_binding(args, build) -> None` (raises `StateError`).

- [ ] **Step 1: Failing tests** — create `tests/v040/test_gc_safety.py`:

```python
"""v0.4.0 review fixes R01, R02, R04, R05 for --gc (real Git)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cld import cli
from cld.ledger import Ledger

RUN = "a" * 32
OLD = "b" * 32


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    for a in (["init", "-q"], ["config", "user.email", "g@g"], ["config", "user.name", "g"],
              ["config", "commit.gpgsign", "false"]):
        git(*a, cwd=path)
    (path / "a.txt").write_text("a")
    (path / ".gitignore").write_text(".cld/\n.cld-ledger.json*\ncache/\n__pycache__/\n.pytest_cache/\n")
    git("add", "-A", cwd=path)
    git("commit", "-qm", "base", cwd=path)
    return path


def add_worktree(repo, slug, session, run=RUN):
    root = repo / ".cld" / "worktrees"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{slug}-{run[:8]}-{session}"
    git("worktree", "add", "-q", "-b", f"cld/{run}/{slug}/{session}", str(path), cwd=repo)
    return path


def write_evidence(repo, run, slice_id, session, worktree):
    d = repo / ".cld" / "runs" / run / slice_id / session
    d.mkdir(parents=True)
    (d / "outcome.json").write_text(json.dumps(dict(
        schema_version=1, session_id=session, slice_id=slice_id, run_id=run,
        worktree=os.path.abspath(worktree), state="failed")))


def bind_ledger(repo, ledger_path, run=RUN, statuses=None, spelled=None):
    """A schema-2 ledger whose build passes validate_build, bound to `repo`."""
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    statuses = statuses or {}
    build = {"run_id": run, "repo": spelled or os.path.realpath(repo),
             "ledger_path": str(Path(ledger_path).resolve()), "git_common_dir": os.path.realpath(common),
             "plan_hash": "0" * 64, "initial_base": "0" * 40,
             "created_at": "2026-10-02T00:00:00Z", "updated_at": "2026-10-02T00:00:00Z",
             "slices": {sid: {"fingerprint": "0" * 64, "deps": []} for sid in statuses}}
    Path(ledger_path).write_text(json.dumps({"schema_version": 2, "build": build,
                                             "entries": {sid: {"status": st} for sid, st in statuses.items()}}))


def gc_json(repo, ledger, *extra):
    from io import StringIO
    import contextlib
    out = StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(["--gc", "--repo", str(repo), "--ledger", str(ledger), *extra, "--json"])
    return code, json.loads(out.getvalue())


def test_ledger_bound_to_other_repo_blocks_without_removal(tmp_path):
    repo_a, repo_b = make_repo(tmp_path / "A"), make_repo(tmp_path / "B")
    wt = add_worktree(repo_b, "S", "1" * 32, run=OLD)
    ledger = tmp_path / "a-ledger.json"
    bind_ledger(repo_a, ledger)
    code, payload = gc_json(repo_b, ledger, "--apply", "--include-previous")
    assert code == 5 and "different repository" in json.dumps(payload)
    assert wt.exists()


def test_same_repo_different_spelling_is_accepted(tmp_path):
    repo = make_repo(tmp_path / "R")
    ledger = tmp_path / "ledger.json"
    spelled = os.path.realpath(repo).upper() if os.name == "nt" else str(repo) + "/"
    bind_ledger(repo, ledger, spelled=spelled)
    code, payload = gc_json(repo, ledger)
    assert code == 0 and payload["command"] == "gc"
```

- [ ] **Step 2: Run** `python -m pytest tests/v040/test_gc_safety.py -q -p no:cacheprovider -k "repo or spelling"` → first FAILS (GC returns 0 and removes `wt`).

- [ ] **Step 3: Implement** in `engine/cld/cli.py`:

```python
def _check_gc_binding(args, build):
    """GC must operate only on the repository its ledger is bound to (R04)."""
    bound = build.get("repo")
    if not bound:
        return
    def norm(path):
        return os.path.normcase(os.path.realpath(path))
    rc, out = _hook("git_runner")(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], args.repo)
    if (rc != 0 or norm(bound) != norm(args.repo)
            or norm(build.get("git_common_dir") or "") != norm(out.strip())):
        raise StateError(f"Ledger is bound to a different repository ({bound}); refusing --gc on {args.repo}")
```

Call it in `_gc_report` immediately after `build = ledger.build or {}`. Text mode: `_run` must map the `StateError` to gate 5 the way other blocked paths do (check `main`'s handler; `_json_gc` already catches `StateError` → blocked).

- [ ] **Step 4: Run** the same command → PASS. **Step 5: Commit** `fix: --gc refuses a ledger bound to a different repository (R04)`.

### Task 2: R05 — ignored local data counts as dirty

**Files:** Modify `engine/cld/gc.py` (`worktree_dirty`); Test `tests/v040/test_gc_safety.py` (append).

- [ ] **Step 1: Failing tests** (append):

```python
def test_ignored_local_data_is_dirty(tmp_path):
    from cld.gc import worktree_dirty
    repo = make_repo(tmp_path / "R")
    wt = add_worktree(repo, "S", "2" * 32)
    runner = cli.git_runner
    assert worktree_dirty(str(wt), runner) is False
    (wt / "cache").mkdir()
    (wt / "cache" / "retained.db").write_text("data")
    assert worktree_dirty(str(wt), runner) is True


def test_disposable_caches_are_not_dirty(tmp_path):
    from cld.gc import worktree_dirty
    repo = make_repo(tmp_path / "R")
    wt = add_worktree(repo, "S", "3" * 32)
    (wt / "__pycache__").mkdir()
    (wt / "__pycache__" / "m.pyc").write_bytes(b"x")
    (wt / ".pytest_cache" / "v").mkdir(parents=True)
    (wt / ".pytest_cache" / "v" / "x").write_text("x")
    assert worktree_dirty(str(wt), cli.git_runner) is False
```

- [ ] **Step 2: Run** `-k "ignored or disposable"` → first FAILS (`False is True`).

- [ ] **Step 3: Implement** — replace `worktree_dirty` in `engine/cld/gc.py`:

```python
def worktree_dirty(path, git_runner) -> bool:
    """Tracked/untracked changes or ignored non-cache data; unreadable status counts as dirty.

    Plain `git status --porcelain` omits ignored files, so an otherwise clean
    worktree holding ignored local data looked safe to force-remove (R05).
    """
    rc, output = git_runner(["git", "status", "--porcelain", "--ignored"], str(path))
    if rc != 0:
        return True
    for line in output.splitlines():
        if not line.strip():
            continue
        if line.startswith("!! "):
            if _is_noise(line[3:].strip().strip('"')):
                continue
        return True
    return False
```

with `from cld.executors._capture import CaptureError, _is_noise`.

- [ ] **Step 4: Run** → PASS, plus `tests/v031/test_gc.py`. **Step 5: Commit** `fix: --gc treats ignored local data as dirty (R05)`.

### Task 3: R01 — slice identity from recovery evidence

**Files:** Modify `engine/cld/gc.py`; Modify `tests/v031/test_gc.py` (slug-based expectations); Test `tests/v040/test_gc_safety.py` (append).

**Interfaces:** Produces `cld.gc.resolve_slice_id(repo_dir, worktree: ManagedWorktree) -> str | None`; `plan_gc(..., slice_ids: Mapping[str, str | None])` keyed by worktree path; `dirty` now applies to every candidate.

- [ ] **Step 1: Failing tests** (append):

```python
def test_resolve_slice_id_from_evidence(tmp_path):
    from cld.gc import list_managed_worktrees, resolve_slice_id
    repo = make_repo(tmp_path / "R")
    s1, s2 = "4" * 32, "5" * 32
    w1, w2 = add_worktree(repo, "A_B", s1), add_worktree(repo, "A_B", s2)
    write_evidence(repo, RUN, "A.B", s1, w1)
    write_evidence(repo, RUN, "A_B", s2, w2)
    found = {w.session_id: w for w in list_managed_worktrees(str(repo), str(repo / ".cld/worktrees"), cli.git_runner)}
    assert resolve_slice_id(str(repo), found[s1]) == "A.B"
    assert resolve_slice_id(str(repo), found[s2]) == "A_B"


def test_missing_evidence_keeps_worktree(tmp_path):
    from cld.gc import list_managed_worktrees, resolve_slice_id
    repo = make_repo(tmp_path / "R")
    add_worktree(repo, "S", "6" * 32)
    (wt,) = list_managed_worktrees(str(repo), str(repo / ".cld/worktrees"), cli.git_runner)
    assert resolve_slice_id(str(repo), wt) is None


def test_slug_collision_never_removes_unfinished_slice(tmp_path):
    repo = make_repo(tmp_path / "R")
    s1, s2 = "7" * 32, "8" * 32
    w1, w2 = add_worktree(repo, "A_B", s1), add_worktree(repo, "A_B", s2)
    write_evidence(repo, RUN, "A.B", s1, w1)
    write_evidence(repo, RUN, "A_B", s2, w2)
    (w1 / "work.txt").write_text("unfinished")
    ledger = tmp_path / "ledger.json"
    bind_ledger(repo, ledger, statuses={"A.B": "needs_repair", "A_B": "integrated"})
    code, payload = gc_json(repo, ledger, "--apply")
    assert code == 0
    assert w1.exists() and (w1 / "work.txt").read_text() == "unfinished"
    assert not w2.exists()
```

- [ ] **Step 2: Run** `-k "resolve or missing_evidence or collision"` → FAIL (`resolve_slice_id` missing; collision removes `w1`).

- [ ] **Step 3: Implement** in `engine/cld/gc.py`:

```python
def resolve_slice_id(repo_dir, worktree) -> str | None:
    """True slice ID from this session's recovery evidence; None when not provable (R01)."""
    from cld.build_state import run_directory
    try:
        base = run_directory(repo_dir, worktree.run_id)
    except Exception:
        return None
    target = os.path.normcase(os.path.realpath(worktree.path))
    found = set()
    for record_path in base.glob(f"*/{worktree.session_id}/outcome.json"):
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if (isinstance(record, dict) and record.get("session_id") == worktree.session_id
                and isinstance(record.get("slice_id"), str) and isinstance(record.get("worktree"), str)
                and os.path.normcase(os.path.realpath(record["worktree"])) == target):
            found.add(record["slice_id"])
    return found.pop() if len(found) == 1 else None
```

(add `import json`, `import os` and `from cld.ledger import StateError` at module top; `collect` in Task 4 uses `StateError`). Change `plan_gc` to take `slice_ids` and apply `dirty` universally:

```python
def plan_gc(worktrees, *, run_id, slice_status, recorded_integration, integration_states,
            dirty, include_previous, slice_ids=None) -> list[GcDecision]:
    slice_ids = slice_ids or {}
    decisions = []
    for wt in worktrees:
        state = integration_states.get(wt.session_id)
        if wt.path in dirty:
            action, reason = "keep", "uncommitted or ignored local data"
        elif wt.run_id != run_id:
            if not include_previous:
                action, reason = "keep", "earlier build; pass --include-previous to remove"
            elif wt.slug == "integration":
                if state in ("passed", "failed"):
                    action, reason = "remove", f"earlier build, integration {state}"
                else:
                    action, reason = "keep", f"earlier build, integration state {state or 'unknown'}"
            elif slice_ids.get(wt.path) is None:
                action, reason = "keep", "slice identity not provable from evidence"
            else:
                action, reason = "remove", "earlier build, no local data"
        elif wt.slug == "integration":
            if wt.session_id == recorded_integration:
                action, reason = "keep", "recorded integration"
            elif state == "passed":
                action, reason = "remove", "passed integration superseded by the recorded one"
            elif state == "failed" and recorded_integration is not None:
                action, reason = "remove", "failed integration; a passed integration is recorded"
            else:
                action, reason = "keep", f"integration state {state or 'unknown'}"
        else:
            sid = slice_ids.get(wt.path)
            if sid is None:
                action, reason = "keep", "slice identity not provable from evidence"
            elif slice_status.get(sid) == "integrated":
                action, reason = "remove", "slice integrated"
            else:
                action, reason = "keep", f"slice status {slice_status.get(sid) or 'unknown'}"
        decisions.append(GcDecision(wt, action, reason))
    return decisions
```

Current-run integration logic is unchanged; earlier-build integration now needs a terminal (`passed`/`failed`) transaction state (R02). `slug_for` stays for compatibility but is no longer used for decisions.

- [ ] **Step 4: Update `tests/v031/test_gc.py`** deliberately (ruling: it encoded slug-keyed status, the R01 defect): pass `slice_ids={wt.path: "A"}` (or the matching ID) wherever a current-run slice decision is asserted; the earlier-build test passes `slice_ids` for its worktrees.

- [ ] **Step 5: Wire the CLI** — in `_gc_report`, compute `slice_ids = {w.path: resolve_slice_id(args.repo, w) for w in worktrees if w.slug != "integration"}`, compute `dirty` for **all** worktrees (`worktree_dirty`), read `integration_states` for every run present (from each worktree's run directory `integration/<session>/outcome.json`), and pass `slice_ids` to `plan_gc`. (Task 4 replaces this wiring with `collect`.)

- [ ] **Step 6: Run** `tests/v040/test_gc_safety.py tests/v031/test_gc.py tests/v031/test_cli_wiring.py` → PASS. **Step 7: Commit** `fix: --gc resolves slice identity from recovery evidence (R01)`.

### Task 4: R02 — ownership before decision and removal

**Files:** Modify `engine/cld/gc.py` (add `collect`), `engine/cld/cli.py` (`_gc_report` uses `collect`); Test `tests/v040/test_gc_safety.py` (append).

**Interfaces:** Produces `cld.gc.collect(repo_dir, root, git_runner, *, run_id, slice_status, recorded_integration, include_previous, apply, owner=None) -> tuple[list[GcDecision], list[dict]]` where `owner(repo_dir, slice_id, git_runner)` is a context manager raising `cld.attempts.ActiveAttempt` when held (default `cld.attempts.slice_owner`).

- [ ] **Step 1: Failing tests** (append):

```python
HOLD = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from cld.attempts import slice_owner
from cld.cli import git_runner
with slice_owner(sys.argv[2], sys.argv[3], git_runner):
    Path(sys.argv[4]).write_text("held")
    while not Path(sys.argv[5]).exists():
        time.sleep(0.05)
"""


def test_active_owner_keeps_worktree(tmp_path):
    repo = make_repo(tmp_path / "R")
    session = "9" * 32
    wt = add_worktree(repo, "A", session, run=OLD)
    write_evidence(repo, OLD, "A", session, wt)
    ledger = tmp_path / "ledger.json"
    bind_ledger(repo, ledger)
    ready, stop = tmp_path / "ready", tmp_path / "stop"
    engine = str(Path(cli.__file__).resolve().parents[1])
    holder = subprocess.Popen([sys.executable, "-c", HOLD, engine, str(repo), "A", str(ready), str(stop)])
    try:
        for _ in range(200):
            if ready.exists():
                break
            time.sleep(0.05)
        assert ready.exists()
        code, payload = gc_json(repo, ledger, "--apply", "--include-previous")
        assert code == 0 and wt.exists()
        reasons = [w["reason"] for w in payload["details"]["worktrees"]]
        assert any("active owner" in r for r in reasons)
    finally:
        stop.write_text("x")
        holder.wait(timeout=30)


def test_previous_run_untouched_without_include_previous(tmp_path):
    repo = make_repo(tmp_path / "R")
    session = "c" * 32
    wt = add_worktree(repo, "A", session, run=OLD)
    write_evidence(repo, OLD, "A", session, wt)
    ledger = tmp_path / "ledger.json"
    bind_ledger(repo, ledger)
    code, _ = gc_json(repo, ledger, "--apply")
    assert code == 0 and wt.exists()


def test_unowned_clean_previous_slice_is_removed(tmp_path):
    repo = make_repo(tmp_path / "R")
    session = "d" * 32
    wt = add_worktree(repo, "A", session, run=OLD)
    write_evidence(repo, OLD, "A", session, wt)
    ledger = tmp_path / "ledger.json"
    bind_ledger(repo, ledger)
    code, _ = gc_json(repo, ledger, "--apply", "--include-previous")
    assert code == 0 and not wt.exists()
```

- [ ] **Step 2: Run** `-k "owner or untouched or unowned"` → `test_active_owner_keeps_worktree` FAILS (removed while held).

- [ ] **Step 3: Implement `collect`** in `engine/cld/gc.py`:

```python
def collect(repo_dir, root, git_runner, *, run_id, slice_status, recorded_integration,
            include_previous, apply, owner=None):
    """Decide (and optionally remove) each worktree while holding its slice's owner lock (R02).

    The lock is the same repository-wide, nonblocking lock delivery holds while a
    slice runs; a held lock means an active owner, so the worktree is kept.
    Eligibility is re-checked under the lock immediately before removal.
    """
    from contextlib import nullcontext
    from cld.attempts import ActiveAttempt, slice_owner
    from cld.build_state import run_directory
    owner = owner or slice_owner
    decisions, results = [], []
    for wt in list_managed_worktrees(repo_dir, root, git_runner):
        states = {}
        if wt.slug == "integration":
            # Transaction records are keyed by their "id" field (as _gc_report read them).
            try:
                for path in (run_directory(repo_dir, wt.run_id) / "integration").glob("*/outcome.json"):
                    record = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(record, dict) and record.get("id") == wt.session_id:
                        states[wt.session_id] = record.get("state")
            except (OSError, ValueError, StateError):
                states = {}
            sid, lock = None, nullcontext()
        else:
            sid = resolve_slice_id(repo_dir, wt)
            lock = owner(repo_dir, sid, git_runner) if sid is not None else nullcontext()
        try:
            with lock:
                dirty = {wt.path} if worktree_dirty(wt.path, git_runner) else set()
                (decision,) = plan_gc([wt], run_id=run_id, slice_status=slice_status,
                                      recorded_integration=recorded_integration,
                                      integration_states=states, dirty=dirty,
                                      include_previous=include_previous, slice_ids={wt.path: sid})
                if apply and decision.action == "remove":
                    results += apply_gc(repo_dir, [decision], root=root, git_runner=git_runner, prune=False)
        except ActiveAttempt:
            decision = GcDecision(wt, "keep", "active owner holds this slice")
        decisions.append(decision)
    if apply:
        git_runner(["git", "worktree", "prune"], repo_dir)
    return decisions, results
```

Give `apply_gc` a `prune=True` keyword so `collect` prunes once. Only take the lock for a candidate that could be removed: if `wt.run_id != run_id and not include_previous`, decide `keep` without locking (Review Focus 2).

- [ ] **Step 4: CLI** — `_gc_report` calls `collect(args.repo, root, git, run_id=run_id, slice_status=..., recorded_integration=..., include_previous=args.include_previous, apply=args.apply)` inside the ledger writer lock, after `_check_gc_binding`; build `details` from the returned decisions and results.

- [ ] **Step 5: Run** `tests/v040/test_gc_safety.py tests/v031/test_gc.py tests/v031/test_cli_wiring.py` → PASS. **Step 6: Commit** `fix: --gc decides and removes only under the slice owner lock (R02)`.

### Task 5: R03 — configuration-referenced environment

**Files:** Modify `engine/cld/providers_api.py` (`Provider.config_env`), `engine/cld_providers/opencode/provider.py`, `engine/cld/cli.py` (`context_of`); Test `tests/v040/test_config_env.py`.

- [ ] **Step 1: Failing tests**:

```python
"""v0.4.0 R03: OpenCode credentials referenced by config key validation evidence."""
import json

from cld.admission import validation_context
from cld.providers_api import get_provider, load_providers


def _opencode_patterns(config):
    load_providers()
    provider = get_provider("opencode")
    assert provider.config_env is not None, "opencode provider has no config_env"
    return (*provider.context_env, *provider.config_env([config]))


def _ctx(config):
    return validation_context("opencode:anthropic/x", cli_paths=[], config_paths=[config],
                              repo=".", env_patterns=_opencode_patterns(config))


def test_config_referenced_credential_changes_fingerprint(tmp_path, monkeypatch):
    config = tmp_path / "opencode.json"
    config.write_text(json.dumps({"provider": {"anthropic": {"options": {"apiKey": "{env:ANTHROPIC_API_KEY}"},
                                                             "baseURL": "{env:MY_GATEWAY_URL}"}}}))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-one")
    monkeypatch.setenv("MY_GATEWAY_URL", "https://a")
    first = _ctx(config)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-two")
    second = _ctx(config)
    monkeypatch.setenv("MY_GATEWAY_URL", "https://b")
    third = _ctx(config)
    assert len({first["fingerprint"], second["fingerprint"], third["fingerprint"]}) == 3
    assert "sk-two" not in json.dumps(second) and "MY_GATEWAY_URL" in third["env_names"]


def test_unrelated_session_variable_still_ignored(tmp_path, monkeypatch):
    config = tmp_path / "opencode.json"
    config.write_text('{"apiKey": "{env:ANTHROPIC_API_KEY}"}')
    first = _ctx(config)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "other")
    assert _ctx(config) == first


def test_missing_config_files_are_harmless(tmp_path):
    load_providers()
    assert get_provider("opencode").config_env([tmp_path / "absent.json"]) == ()
```

- [ ] **Step 2: Run** → FAIL (`config_env` missing).

- [ ] **Step 3: Implement** — `Provider` field `config_env: Optional[Callable] = None  # (config paths) -> env names referenced by the provider's config`. In `engine/cld_providers/opencode/provider.py`:

```python
_ENV_REF = re.compile(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}")


def _config_env(paths):
    """Environment names OpenCode configs reference via {env:NAME} (values hashed by admission)."""
    names = set()
    for path in paths:
        try:
            names.update(_ENV_REF.findall(Path(path).read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return tuple(sorted(names))
```

(import `re`), and `config_env=_config_env` on its `Provider`. In `cli.py` `context_of`:

```python
        provider_obj = get_provider(provider)
        patterns = provider_obj.context_env + (
            provider_obj.config_env(config_paths) if provider_obj.config_env else ())
```

passing `env_patterns=patterns`.

- [ ] **Step 4: Run** `tests/v040/test_config_env.py tests/v031/test_validation_context.py tests/test_t09_admission.py` → PASS. **Step 5: Commit** `fix: OpenCode config-referenced credentials key validation evidence (R03)`.

### Task 6: R06 — classify network failures from complete output

**Files:** Modify `engine/cld/orchestrator.py`; Test `tests/v040/test_network_tail.py`.

**Interfaces:** Produces `cld.orchestrator._failure_text(result, limit=65536) -> str`.

- [ ] **Step 1: Failing tests**:

```python
"""v0.4.0 R06: late network errors are final even after long output."""
import subprocess

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.judge import judge
from cld.validate import _pytest


def _git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


@pytest.fixture
def repo(tmp_path):
    for a in (["init", "-q"], ["config", "user.email", "n@n"], ["config", "user.name", "n"],
              ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *a], cwd=tmp_path, check=True)
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return None\n")
    (tmp_path / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "b"], cwd=tmp_path, check=True)
    return tmp_path


class LongThenNetwork:
    """Retained full output lives outside the repo, like CLD's process capture files."""
    def __init__(self, outdir, stderr_text, keep_files=True):
        self.calls = 0
        self.out, self.err = outdir / "stdout.bin", outdir / "stderr.bin"
        self.out.write_text("x" * 5000)
        self.err.write_text(stderr_text)
        if not keep_files:
            self.out.unlink(); self.err.unlink()

    def run(self, task, workdir, feedback=None):
        self.calls += 1
        log = ("x" * 5000)[:4000]
        return ExecutorResult(ok=False, diff="", raw_log=log, process={
            "error": "nonzero_exit", "stdout_path": str(self.out), "stderr_path": str(self.err)})


def _deliver(repo, executor):
    from cld.orchestrator import deliver_slice
    return deliver_slice(SliceTask("s", "b", ["calc.py"], "test_calc.py"), executor=executor,
                         judge_fn=judge, workdir=str(repo), git_runner=_git, test_runner=_pytest,
                         model="codex:gpt-x@low")


def test_late_stderr_network_error_is_final(repo, tmp_path_factory):
    executor = LongThenNetwork(tmp_path_factory.mktemp("out"), "Error: getaddrinfo ENOTFOUND api.openai.com")
    result = _deliver(repo, executor)
    assert executor.calls == 1 and result.final_error == "network_unavailable"


def test_missing_retained_files_fall_back_to_raw_log(repo, tmp_path_factory):
    executor = LongThenNetwork(tmp_path_factory.mktemp("out"), "ignored", keep_files=False)
    result = _deliver(repo, executor)
    assert executor.calls == 3 and result.final_error is None


def test_successful_dispatch_is_never_reclassified(repo, tmp_path_factory):
    outdir = tmp_path_factory.mktemp("out")
    (outdir / "stderr.bin").write_text("retrying after getaddrinfo ENOTFOUND ... recovered")

    class Fixes:
        calls = 0
        def run(self, task, workdir, feedback=None):
            self.calls += 1
            from pathlib import Path
            Path(workdir, "calc.py").write_text("def add(a, b):\n    return a + b\n")
            return ExecutorResult(ok=True, diff="", raw_log="ok",
                                  process={"stderr_path": str(outdir / "stderr.bin")})

    result = _deliver(repo, Fixes())
    assert result.final_error is None
```

- [ ] **Step 2: Run** → first FAILS (`calls == 3`).

- [ ] **Step 3: Implement** in `engine/cld/orchestrator.py`:

```python
def _failure_text(result, limit=65536):
    """Bounded tails of the retained full stdout/stderr plus raw_log (R06).

    raw_log keeps only the start of output, so an error printed late or on
    stderr after long stdout would otherwise be invisible to classification.
    """
    parts = [result.raw_log or ""]
    process = result.process if isinstance(result.process, dict) else {}
    for key in ("stdout_path", "stderr_path"):
        path = process.get(key)
        if not isinstance(path, str):
            continue
        try:
            with open(path, "rb") as stream:
                stream.seek(0, 2)
                size = stream.tell()
                stream.seek(max(0, size - limit))
                parts.append(stream.read().decode("utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(parts)
```

and change the classification line to `and network_error(_failure_text(result))`.

- [ ] **Step 4: Run** `tests/v040/test_network_tail.py tests/v031/test_final_errors.py` → PASS. **Step 5: Commit** `fix: classify network failures from complete retained output (R06)`.

### Task 7: Release preparation

- [ ] **Step 1:** Mark R01–R06 fixed in `docs/plans/v0.3.1-fixes/REVIEW-2026-10-01.md` (tick boxes, add "Fixed in <sha>" per finding); commit it together with the `HANDOFF.md` checkpoint (both previously untracked/modified by the reviewer).
- [ ] **Step 2:** `CHANGELOG.md` `[Unreleased]` → add a "Fixed (review R01–R06)" list; `KNOWN-ISSUES.md` → replace the "avoid `--gc --apply`" caution with the new guarantees.
- [ ] **Step 3:** Regenerate (`build_skill.py --all` both hosts, `build_plugins.py` both hosts, `check_plugins_fresh.py`), commit `build: regenerate`.
- [ ] **Step 4:** Full offline suite (background) → green.
- [ ] **Step 5:** On the user's go-ahead: push, CI green, then the v0.4.0 release flow (VERSION/pyproject 0.4.0, changelog heading, checked sync to `main`, assets, tag, GitHub release, install).
