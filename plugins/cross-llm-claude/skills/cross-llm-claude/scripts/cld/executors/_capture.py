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


_NOISE_DIRS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                         ".hypothesis", ".tox", ".nox", "htmlcov", ".eggs"})


def _is_noise(path: str, cache_roots: frozenset = frozenset()) -> bool:
    """True for transient artifacts produced by RUNNING tools/tests, never slice edits.

    Callers apply this only to NEW, UNTRACKED paths; tracked files are always
    judged. Counting these as changed files makes the diff-rule FALSELY reject a
    correct slice (found live: pytest bytecode; v0.3.1 review: linter caches,
    packaging metadata and test databases such as .hypothesis and .coverage).
    """
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if any(part in _NOISE_DIRS or part.endswith(".egg-info") for part in parts[:-1]):
        return True
    name = parts[-1]
    if name.endswith((".pyc", ".pyo")) or name == ".coverage" or name.startswith(".coverage."):
        return True
    return any(normalized == root or normalized.startswith(root + "/") for root in cache_roots)


def cache_roots(cwd: str) -> frozenset:
    """Repo-relative directories marked with CACHEDIR.TAG (the cross-tool cache convention)."""
    from pathlib import Path
    base = Path(cwd)
    roots = set()
    for tag in base.rglob("CACHEDIR.TAG"):
        relative = tag.parent.relative_to(base).as_posix()
        if relative != "." and relative.split("/")[0] != ".git":
            roots.add(relative)
    return frozenset(roots)


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
