"""Bug A regression: the worktree path must be a clean SIBLING of the repo, never
a malformed dir like '.-wt-<branch>' INSIDE the repo (which `--repo .` produced)."""
import os

from cld.worktree import worktree


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, args, cwd):
        self.calls.append((args, cwd))
        return (0, "")


def _yielded_path(repo_dir):
    rec = _Recorder()
    with worktree(repo_dir, "slice-S7", runner=rec) as path:
        return path, rec.calls


def test_dot_repo_does_not_produce_dot_wt_inside_repo():
    path, calls = _yielded_path(".")
    base = os.path.basename(path)
    # the bug: base was ".-wt-slice-S7" and the path lived INSIDE the repo
    assert not base.startswith(".-wt-"), f"malformed worktree path: {path!r}"
    # it must be an absolute path (resolved), not a relative '.'-prefixed string
    assert os.path.isabs(path), f"worktree path should be absolute, got {path!r}"
    # and it must not be a child of the cwd (it's a SIBLING)
    cwd = os.path.abspath(".")
    assert os.path.dirname(path.rstrip(os.sep)) != cwd, \
        f"worktree should be a sibling of the repo, not inside it: {path!r}"


def test_relative_repo_path_resolved_to_sibling():
    path, _ = _yielded_path("myrepo")
    base = os.path.basename(path)
    assert base == "myrepo-wt-slice-S7"
    assert os.path.isabs(path)


def test_absolute_repo_path_still_works():
    # backward-compatible: an absolute repo dir yields '<abs>-wt-<branch>'
    abs_repo = os.path.abspath(os.path.join("some", "repo"))
    path, _ = _yielded_path(abs_repo)
    assert path == abs_repo + "-wt-slice-S7"
