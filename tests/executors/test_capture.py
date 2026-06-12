"""Tests for the shared capture_diff helper (DRY between Gemini and OpenCode).

capture_diff stages with `git add --intent-to-add -A` (so NEW slice files appear in
`git diff HEAD` — the Bug1/Defect1 fix) then returns (diff, files_changed) via the
injected runner. Pure aside from the runner; no real git needed here.
"""

from cld.executors._capture import capture_diff


class _Runner:
    """Returns canned output per matched git subcommand; records calls."""

    def __init__(self, diff="--- a\n+++ b\n+x\n", names="src/a.py\nsrc/b.py\n"):
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
