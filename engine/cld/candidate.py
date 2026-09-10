"""Engine-owned candidate verification, independent of provider reports.

The executor must have terminated before capture. Git isolation is not an OS
sandbox. Snapshot judging needs committed inputs; dependencies belong in the
environment, not in ignored files in the executor's worktree.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shlex
from tempfile import TemporaryDirectory

from cld.executors._capture import CaptureError, Runner, _is_noise, checked, nul_names
from cld.judge import _extract_rc, parse_pytest_output


def acceptance_args(selector: str) -> list[str]:
    """One literal path/node selector, optionally a quoted path and/or -k filter."""
    args = shlex.split(selector) if (selector.startswith(('"', "'")) or " -k " in selector) else [selector]
    if (len(args) not in (1, 3) or (len(args) == 3 and args[1] != "-k")
            or not args[0] or args[0].startswith("-")):
        raise CaptureError("Acceptance selector must be one path, optionally followed by -k expression")
    safe_path(args[0].split("::", 1)[0])
    return args


def safe_path(name: str) -> str:
    # Require canonical portable repository paths. Reject Windows drive/ADS and
    # backslashes even on POSIX, and Git pathspec magic on every platform.
    if (not isinstance(name, str) or not name or "\0" in name or "\\" in name
            or ":" in name or name.startswith("/")
            or any(p in ("", ".", "..") or p.lower() == ".git"
                   for p in name.split("/"))):
        raise CaptureError(f"Unsafe repository path: {name!r}")
    if os.name == "nt" and any(p.endswith((" ", ".")) for p in name.split("/")):
        raise CaptureError(f"Ambiguous Windows repository path: {name!r}")
    return name


def _is_link(path):
    # Path.is_junction is only available in Python 3.12+; retain Python 3.11.
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def tree_entries(runner, cwd, tree):
    entries = {}
    for record in nul_names(checked(runner, cwd, "ls-tree", "-r", "-z", tree)):
        meta, name = record.split("\t", 1)
        mode, kind, oid = meta.split()
        safe_path(name)
        # Conservatively reject symlinks and submodules: checkout behavior differs
        # across hosts and following a link could escape the trusted snapshot.
        if mode not in ("100644", "100755") or kind != "blob":
            raise CaptureError(f"Unsupported symlink/submodule entry: {name!r}")
        entries[name] = (mode, oid)
    return entries


def _protected_default(name):
    path = PurePosixPath(name)
    return (path.name in {"conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini", ".gitattributes"}
            or path.name.startswith("test_") or path.name.endswith("_test.py")
            or "tests" in path.parts)


@dataclass(frozen=True)
class Candidate:
    base: str
    tree: str
    files_changed: tuple[str, ...]
    diff: str
    tests_fingerprint: str


def capture_tree(runner, cwd, base):
    """Capture all source changes for verification or recovery, without path policy."""
    baseline = tree_entries(runner, cwd, base)
    # Include ignored source too; ignore ONLY new transient test artifacts.
    # Tracked cache-looking files are ordinary protected/allowed input files.
    for path in Path(cwd).rglob("*"):
        if _is_link(path):
            raise CaptureError(f"Symlink/junction in candidate: {path.name!r}")
    tracked = nul_names(checked(runner, cwd, "ls-files", "-z"))
    for start in range(0, len(tracked), 100):
        # update-index selects one flag operation per invocation. Combining
        # these options leaves skip-worktree set on supported Git versions.
        for flag in ("--no-assume-unchanged", "--no-skip-worktree"):
            checked(runner, cwd, "update-index", flag,
                    "--", *tracked[start:start + 100])
    checked(runner, cwd, "add", "-A")
    ignored = nul_names(checked(runner, cwd, "ls-files", "--others", "--ignored",
                                "--exclude-standard", "-z"))
    for name in ignored:
        safe_path(name)
        if not _is_noise(name):
            checked(runner, cwd, "--literal-pathspecs", "add", "--force", "--", name)
    staged = nul_names(checked(runner, cwd, "ls-files", "-z"))
    for name in staged:
        safe_path(name)
        if name not in baseline and _is_noise(name):
            checked(runner, cwd, "--literal-pathspecs", "rm", "--cached", "--force", "--", name)
    tree = checked(runner, cwd, "write-tree").strip()
    return tree


class CandidateVerifier:
    def __init__(self, runner: Runner, cwd: str, task, *, base: str | None = None):
        self.runner, self.cwd = runner, cwd
        self.base = base or checked(runner, cwd, "rev-parse", "--verify", "HEAD^{commit}").strip()
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", self.base):
            raise CaptureError("Missing immutable dispatch base")
        self.entries = tree_entries(runner, cwd, self.base)
        self.allowed = frozenset(safe_path(p) for p in task.files)
        self.allow_already_satisfied = task.allow_already_satisfied is True
        self.selector = task.acceptance_test_path
        test_path = acceptance_args(self.selector)[0].split("::", 1)[0]
        selected = {p for p in self.entries if p == test_path or p.startswith(test_path + "/")}
        if not selected:
            raise CaptureError("Acceptance inputs must exist in the committed baseline")
        self.protected = selected | {safe_path(p) for p in task.protected_inputs}
        # Default defense for pytest fixtures/config plus conventional test files.
        # Additional arbitrary fixture/data inputs can be declared in the plan.
        self.protected |= {p for p in self.entries if _protected_default(p)}
        if not self.protected <= self.entries.keys():
            raise CaptureError("Protected inputs must be committed baseline files")
        self.tests_fingerprint = hashlib.sha256(repr((self.selector, sorted(
            (p, self.entries[p]) for p in self.protected))).encode("utf-8")).hexdigest()
        self.baseline_passed = False

    def capture(self) -> Candidate:
        tree = capture_tree(self.runner, self.cwd, self.base)
        entries = tree_entries(self.runner, self.cwd, tree)
        if any(_protected_default(p) and p not in self.entries for p in entries):
            raise CaptureError("Executor added a protected acceptance/configuration input")
        names = nul_names(checked(self.runner, self.cwd, "diff", "--no-renames", "--name-only",
                                  "-z", self.base, tree, "--"))
        diff = checked(self.runner, self.cwd, "diff", "--binary", "--no-ext-diff", "--no-textconv",
                       self.base, tree, "--")
        for name in self.protected:
            if entries.get(name) != self.entries[name]:
                raise CaptureError(f"Protected acceptance input changed: {name!r}")
        forbidden = set(names) - self.allowed
        if forbidden:
            raise CaptureError(f"Edited files outside the allowed set: {sorted(forbidden)!r}")
        return Candidate(self.base, tree, tuple(names), diff, self.tests_fingerprint)

    @contextmanager
    def snapshot(self, candidate):
        # checkout-index materializes Git blobs, not a copy of executor files.
        # Assert the index still names the frozen tree on both sides of checkout.
        with TemporaryDirectory(prefix="cld-judge-") as directory:
            self._check_index(candidate)
            checked(self.runner, self.cwd, "checkout-index", "--all", "--force",
                    f"--prefix={Path(directory).as_posix()}/")
            self._check_index(candidate)
            before = self._fingerprint(directory, candidate)
            yield directory
            if self._fingerprint(directory, candidate) != before:
                raise CaptureError("Acceptance execution mutated the frozen candidate")

    def _check_index(self, candidate):
        if checked(self.runner, self.cwd, "write-tree").strip() != candidate.tree:
            raise CaptureError("Index differs from frozen candidate")

    def _fingerprint(self, directory, candidate):
        tracked = tree_entries(self.runner, self.cwd, candidate.tree)
        digest = hashlib.sha256()
        for path in sorted(Path(directory).rglob("*")):
            name = path.relative_to(directory).as_posix()
            if _is_link(path):
                raise CaptureError("Acceptance execution created a symlink/junction")
            if not path.is_file():
                continue
            if name not in tracked and _is_noise(name):
                continue
            digest.update(name.encode("utf-8") + b"\0")
            digest.update(str(path.stat().st_mode & 0o111).encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        return digest.digest()

    def preflight(self, run_tests):
        candidate = self.capture()
        base_tree = checked(self.runner, self.cwd, "rev-parse", f"{self.base}^{{tree}}").strip()
        if candidate.tree != base_tree:
            raise CaptureError("Dispatch requires a clean committed baseline")
        with self.snapshot(candidate) as directory:
            output = run_tests(directory)
        rc = _extract_rc(output)
        passed, failed, _ = parse_pytest_output(output)
        errors = re.search(r"\b[1-9]\d*\s+errors?\b", output)
        failures = re.findall(r"^FAILED .+$", output, re.MULTILINE)
        if rc == 0 and passed > 0 and failed == 0 and not errors:
            self.baseline_passed = True
        elif (rc == 1 and failed > 0 and not errors and len(failures) == failed
              and all(re.search(r" - (?:assert\b|AssertionError\b)", line) for line in failures)):
            self.baseline_passed = False
        else:
            raise CaptureError("Baseline must pass or fail assertions; collection/configuration/"
                               "missing-RC errors are not a valid red test\n" + output[-1000:])

    def verify_unchanged(self, candidate):
        if self.capture() != candidate:
            raise CaptureError("Executor worktree differs from the verified candidate")

    def prepare_collection(self, candidate):
        self.verify_unchanged(candidate)
        # Use the verified tree, not blanket staging after the judge. T03 owns
        # checked commit results, hook effects, reachability and recovery.
        checked(self.runner, self.cwd, "read-tree", candidate.tree)
