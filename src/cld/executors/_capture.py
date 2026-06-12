"""Shared worktree diff capture, used by every CLI executor.

`git diff HEAD` omits UNTRACKED new files, so we `git add --intent-to-add -A`
first (Bug1/Defect1 fix) — created slice files then appear in the diff.
"""

from typing import Callable

# runner(args, cwd) -> (returncode, stdout_or_combined_output)
Runner = Callable[[list[str], str], tuple[int, str]]


def capture_diff(runner: Runner, cwd: str) -> tuple[str, list[str]]:
    """Stage (intent-to-add) then capture (diff, files_changed) for the worktree."""
    runner(["git", "add", "--intent-to-add", "-A"], cwd)
    _, diff = runner(["git", "diff", "HEAD"], cwd)
    _, names = runner(["git", "diff", "HEAD", "--name-only"], cwd)
    files_changed = [line.strip() for line in names.splitlines() if line.strip()]
    return diff, files_changed
