"""Shared worktree diff capture, used by every CLI executor.

`git diff HEAD` omits UNTRACKED new files, so we `git add --intent-to-add -A`
first (Bug1/Defect1 fix) — created slice files then appear in the diff.
"""

from typing import Callable

# runner(args, cwd) -> (returncode, stdout_or_combined_output)
Runner = Callable[[list[str], str], tuple[int, str]]


class CaptureError(RuntimeError):
    """Git could not provide a complete candidate; never treat this as no edits."""


def checked(runner: Runner, cwd: str, *args: str) -> str:
    rc, output = runner(["git", *args], cwd)
    if rc != 0:
        raise CaptureError(f"git {args[0]} failed ({rc}): {output[:500]}")
    if not isinstance(output, str):
        raise CaptureError("Git runner returned non-text output")
    return output


def nul_names(output: str) -> list[str]:
    if output and not output.endswith("\0"):
        raise CaptureError("Incomplete NUL-delimited Git output")
    return output.split("\0")[:-1] if output else []


def _is_noise(path: str) -> bool:
    """True for transient artifacts the executor generates by RUNNING tests —
    bytecode/caches that are not real slice edits. Counting them as changed files
    makes the judge's diff-rule flag a disallowed edit and FALSELY reject a slice
    whose code is correct and tests pass (found live: a passing deepseek-v4-pro slice
    was judged known-bad because pytest left __pycache__/*.pyc in the worktree)."""
    parts = path.replace("\\", "/").split("/")
    if "__pycache__" in parts or ".pytest_cache" in parts:
        return True
    if path.endswith((".pyc", ".pyo")):
        return True
    return False


def capture_diff(runner: Runner, cwd: str, *, base: str = "HEAD") -> tuple[str, list[str]]:
    """Stage (intent-to-add) then capture (diff, files_changed) for the worktree.

    Transient test artifacts (__pycache__, .pyc, .pytest_cache) are filtered from
    files_changed — they are produced by running the acceptance tests, not by the
    slice, and must not trip the judge's allowed-files diff-rule.
    """
    checked(runner, cwd, "add", "--intent-to-add", "-A")
    diff = checked(runner, cwd, "diff", "--binary", "--no-ext-diff", "--no-textconv", base, "--")
    names = checked(runner, cwd, "diff", "--no-renames", "--name-only", "-z", base, "--")
    files_changed = [
        name for name in nul_names(names) if not _is_noise(name)
    ]
    return diff, files_changed
