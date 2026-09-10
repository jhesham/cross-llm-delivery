"""Tests for the shared capture_diff helper (DRY between Gemini and OpenCode).

capture_diff stages with `git add --intent-to-add -A` (so NEW slice files appear in
`git diff HEAD` — the Bug1/Defect1 fix) then returns (diff, files_changed) via the
injected runner. Pure aside from the runner; no real git needed here.
"""

from cld.executors._capture import capture_diff
from cld.executors._capture import CaptureError
import pytest


class _Runner:
    """Returns canned output per matched git subcommand; records calls."""

    def __init__(self, diff="--- a\n+++ b\n+x\n", names="src/a.py\0src/b.py\0"):
        self.calls = []
        self._diff = diff
        self._names = names

    def __call__(self, args, cwd):
        self.calls.append(args)
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


def test_capture_diff_empty():
    r = _Runner(diff="", names="")
    diff, files = capture_diff(r, "/work")
    assert diff == ""
    assert files == []


def test_capture_diff_ignores_pycache_and_pyc():
    # When the executor runs pytest in the worktree it generates __pycache__/*.pyc;
    # these are NOT real edits and must NOT appear in files_changed, or the judge's
    # diff-rule wrongly flags them as disallowed -> false known-bad (found live:
    # deepseek-v4-pro wrote correct calc.py + test passed, but pyc files failed it).
    names = ("calc.py\0"
             "__pycache__/calc.cpython-313.pyc\0"
             "__pycache__/test_calc.cpython-313-pytest-9.0.3.pyc\0"
             "src/.pytest_cache/v/cache/lastfailed\0")
    r = _Runner(names=names)
    _, files = capture_diff(r, "/work")
    assert files == ["calc.py"]  # only the real edit; pyc/cache noise filtered


@pytest.mark.parametrize("command", ["add", "diff"])
def test_capture_fails_closed_on_git_errors(command):
    def runner(args, cwd):
        return (1, "") if args[1] == command else (0, "")
    with pytest.raises(CaptureError, match="failed"):
        capture_diff(runner, "/work")


def test_incomplete_name_capture_is_rejected():
    with pytest.raises(CaptureError, match="Incomplete"):
        capture_diff(_Runner(names="truncated"), "/work")
