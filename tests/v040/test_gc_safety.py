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


def test_text_mode_mismatch_is_gate_5(tmp_path, capsys):
    repo_a, repo_b = make_repo(tmp_path / "A"), make_repo(tmp_path / "B")
    wt = add_worktree(repo_b, "S", "e" * 32, run=OLD)
    ledger = tmp_path / "a-ledger.json"
    bind_ledger(repo_a, ledger)
    code = cli.main(["--gc", "--repo", str(repo_b), "--ledger", str(ledger), "--apply", "--include-previous"])
    assert code == 5 and wt.exists()


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
    ledger = tmp_path / "ledger.json"
    bind_ledger(repo, ledger, statuses={"A.B": "needs_repair", "A_B": "integrated"})
    code, payload = gc_json(repo, ledger, "--apply")
    assert code == 0
    assert w1.exists(), payload
    assert not w2.exists()


def test_long_ids_sharing_slug_prefix(tmp_path):
    repo = make_repo(tmp_path / "R")
    long_a, long_b = "X" * 40 + "a", "X" * 40 + "b"
    s1, s2 = "f" * 32, "0" * 32
    w1, w2 = add_worktree(repo, "X" * 40, s1), add_worktree(repo, "X" * 40, s2)
    write_evidence(repo, RUN, long_a, s1, w1)
    write_evidence(repo, RUN, long_b, s2, w2)
    ledger = tmp_path / "ledger.json"
    bind_ledger(repo, ledger, statuses={long_a: "in_progress", long_b: "integrated"})
    code, payload = gc_json(repo, ledger, "--apply")
    assert code == 0 and w1.exists() and not w2.exists(), payload


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
        for _ in range(400):
            if ready.exists():
                break
            time.sleep(0.05)
        assert ready.exists()
        code, payload = gc_json(repo, ledger, "--apply", "--include-previous")
        assert code == 0 and wt.exists()
        reasons = [w["reason"] for w in payload["details"]["worktrees"]]
        assert any("active owner" in r for r in reasons), reasons
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


def test_earlier_integration_needs_terminal_state(tmp_path):
    repo = make_repo(tmp_path / "R")
    merging, done = "1" * 31 + "a", "1" * 31 + "b"
    w1, w2 = add_worktree(repo, "integration", merging, run=OLD), add_worktree(repo, "integration", done, run=OLD)
    for sess, state in ((merging, "merging"), (done, "passed")):
        d = repo / ".cld" / "runs" / OLD / "integration" / sess
        d.mkdir(parents=True)
        (d / "outcome.json").write_text(json.dumps({"id": sess, "state": state}))
    ledger = tmp_path / "ledger.json"
    bind_ledger(repo, ledger)
    code, payload = gc_json(repo, ledger, "--apply", "--include-previous")
    assert code == 0 and w1.exists() and not w2.exists(), payload["details"]
