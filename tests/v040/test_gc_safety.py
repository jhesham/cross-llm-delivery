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
