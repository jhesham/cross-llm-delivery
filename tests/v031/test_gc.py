"""v0.3.1 fix 6: safe, explicit worktree garbage collection.

CLD slice GC. Red by AssertionError only: cld.gc resolved lazily.
"""
import importlib
import shutil
import subprocess
from pathlib import Path

import pytest

RUN = "a" * 32
OLD = "b" * 32


def _gc():
    try:
        module = importlib.import_module("cld.gc")
    except ImportError:
        module = None
    assert module is not None, "cld.gc not implemented"
    return module


def _git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


def _session(n):
    return f"{n:032x}"


def _wt(slug, n, run=RUN, root="/r"):
    return _gc().ManagedWorktree(path=f"{root}/{slug}-{run[:8]}-{_session(n)}",
                                 branch=f"cld/{run}/{slug}/{_session(n)}",
                                 run_id=run, slug=slug, session_id=_session(n))


def _plan(worktrees, **kw):
    options = dict(run_id=RUN, slice_status={}, recorded_integration=None, integration_states={},
                   dirty=set(), include_previous=False)
    options.update(kw)
    return {d.worktree.path: d.action for d in _gc().plan_gc(worktrees, **options)}


def test_slug_matches_managed_location():
    assert _gc().slug_for("T1.a/b") == "T1_a_b"
    assert _gc().slug_for("x" * 60) == "x" * 40


def test_plan_gc_removes_integrated_slice_worktree():
    wt = _wt("A", 1)
    assert _plan([wt], slice_status={"A": "integrated"}) == {wt.path: "remove"}


@pytest.mark.parametrize("status", ["pending", "in_progress", "done", "failed", "needs_repair", "blocked", None])
def test_plan_gc_keeps_every_non_integrated_status(status):
    wt = _wt("A", 1)
    statuses = {} if status is None else {"A": status}
    assert _plan([wt], slice_status=statuses) == {wt.path: "keep"}


def test_plan_gc_integration_rules():
    recorded, passed = _wt("integration", 1), _wt("integration", 2)
    failed, busy = _wt("integration", 3), _wt("integration", 4)
    states = {_session(1): "passed", _session(2): "passed", _session(3): "failed", _session(4): "merging"}
    decisions = _plan([recorded, passed, failed, busy], recorded_integration=_session(1),
                      integration_states=states)
    assert decisions == {recorded.path: "keep", passed.path: "remove",
                         failed.path: "remove", busy.path: "keep"}


def test_plan_gc_failed_integration_kept_without_a_passed_one():
    failed = _wt("integration", 3)
    assert _plan([failed], integration_states={_session(3): "failed"}) == {failed.path: "keep"}


def test_plan_gc_previous_builds():
    clean, dirty = _wt("A", 1, run=OLD), _wt("B", 2, run=OLD)
    assert _plan([clean, dirty]) == {clean.path: "keep", dirty.path: "keep"}
    assert _plan([clean, dirty], include_previous=True, dirty={dirty.path}) == {
        clean.path: "remove", dirty.path: "keep"}


def test_every_decision_has_a_reason():
    decisions = _gc().plan_gc([_wt("A", 1)], run_id=RUN, slice_status={"A": "failed"},
                              recorded_integration=None, integration_states={}, dirty=set(),
                              include_previous=False)
    assert decisions[0].reason


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    (repo / "a.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    return repo


def _root(repo):
    root = (repo / ".cld" / "worktrees").resolve()
    root.mkdir(parents=True)
    return root


def _add(repo, root, slug, n, run=RUN):
    path = root / f"{slug}-{run[:8]}-{_session(n)}"
    subprocess.run(["git", "worktree", "add", "-q", "-b", f"cld/{run}/{slug}/{_session(n)}", str(path)],
                   cwd=repo, check=True)
    return path


def test_list_managed_worktrees_filters_to_root_and_cld_branches(repo, tmp_path):
    root = _root(repo)
    keep = _add(repo, root, "A", 1)
    subprocess.run(["git", "worktree", "add", "-q", "-b", "feature", str(tmp_path / "elsewhere")],
                   cwd=repo, check=True)
    found = _gc().list_managed_worktrees(str(repo), str(root), _git)
    assert [(Path(w.path).resolve(), w.slug, w.run_id, w.session_id) for w in found] == [
        (keep.resolve(), "A", RUN, _session(1))]


def test_worktree_dirty(repo):
    path = _add(repo, _root(repo), "A", 1)
    assert _gc().worktree_dirty(str(path), _git) is False
    (path / "new.txt").write_text("x", encoding="utf-8")
    assert _gc().worktree_dirty(str(path), _git) is True


def test_apply_gc_removes_only_remove_decisions_and_prunes(repo):
    gc = _gc()
    root = _root(repo)
    gone, kept, stale = _add(repo, root, "A", 1), _add(repo, root, "B", 2), _add(repo, root, "C", 3)
    shutil.rmtree(stale)
    worktrees = {w.slug: w for w in gc.list_managed_worktrees(str(repo), str(root), _git)}
    decisions = [gc.GcDecision(worktrees["A"], "remove", "integrated"),
                 gc.GcDecision(worktrees["B"], "keep", "failed")]
    results = gc.apply_gc(str(repo), decisions, root=str(root), git_runner=_git)
    assert [r["action"] for r in results] == ["removed"]
    assert not gone.exists() and kept.exists()
    listing = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=repo,
                             capture_output=True, text=True).stdout
    assert stale.name not in listing
    assert kept.name in listing


def test_apply_gc_refuses_paths_outside_root(repo, tmp_path):
    gc = _gc()
    root = _root(repo)
    outside = tmp_path / "outside"
    branch = f"cld/{RUN}/X/{_session(9)}"
    subprocess.run(["git", "worktree", "add", "-q", "-b", branch, str(outside)], cwd=repo, check=True)
    rogue = gc.ManagedWorktree(str(outside), branch, RUN, "X", _session(9))
    results = gc.apply_gc(str(repo), [gc.GcDecision(rogue, "remove", "test")], root=str(root), git_runner=_git)
    assert results[0]["action"] == "failed"
    assert outside.exists()
