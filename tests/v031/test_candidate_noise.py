"""v0.3.1 fix 2: tool caches/metadata never reject a correct slice; tracked files still judged."""
import subprocess
import types
from pathlib import Path

import pytest

from cld.candidate import CandidateVerifier
from cld.executors._capture import CaptureError

TASK = types.SimpleNamespace(files=["src/calc.py"], acceptance_test_path="tests/test_calc.py",
                             protected_inputs=[], allow_already_satisfied=False)
TAG = "Signature: 8a477f597d28d172789f06886806bc55\n"


def git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


def make_repo(root: Path, extra_tracked=None) -> Path:
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *args], cwd=root, check=True)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src/calc.py").write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
    (root / "tests/test_calc.py").write_text(
        "import sys; sys.path.insert(0, 'src')\nfrom calc import add\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    (root / ".gitignore").write_text("*.egg-info/\n.coverage\n", encoding="utf-8")
    for name, text in (extra_tracked or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "-f", name], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    return root


def fix(root: Path):
    (root / "src/calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")


def write(root: Path, name: str, text="x"):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("files", [
    {".ruff_cache/.gitignore": "*\n", ".ruff_cache/CACHEDIR.TAG": TAG},
    {".mypy_cache/.gitignore": "*\n", ".mypy_cache/3.11/calc.data.json": "{}"},
    {"src/calc.egg-info/PKG-INFO": "Name: calc\n"},
    {".hypothesis/examples/abc": "db"},
    {".coverage": "data", ".coverage.host.1234": "data"},
    {".tox/py311/log.txt": "x", ".nox/s/log.txt": "x", "htmlcov/index.html": "x", ".eggs/README.txt": "x"},
    {"build-cache/CACHEDIR.TAG": TAG, "build-cache/blob": "x"},
], ids=["ruff", "mypy", "egg-info", "hypothesis", "coverage", "tox-nox-htmlcov-eggs", "cachedir-tag"])
def test_new_cache_and_metadata_files_are_not_candidate_edits(tmp_path, files):
    root = make_repo(tmp_path)
    fix(root)
    for name, text in files.items():
        write(root, name, text)
    candidate = CandidateVerifier(git, str(root), TASK).capture()
    assert list(candidate.files_changed) == ["src/calc.py"]


def test_tracked_noise_named_file_is_still_judged(tmp_path):
    root = make_repo(tmp_path, extra_tracked={"src/calc.egg-info/PKG-INFO": "Name: calc\n"})
    fix(root)
    write(root, "src/calc.egg-info/PKG-INFO", "Name: changed\n")
    with pytest.raises(CaptureError, match="outside the allowed set"):
        CandidateVerifier(git, str(root), TASK).capture()


def test_real_source_in_ignored_path_is_still_caught(tmp_path):
    root = make_repo(tmp_path)
    (root / ".gitignore").write_text("*.egg-info/\n.coverage\nvendor/\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "ignore vendor"], cwd=root, check=True)
    fix(root)
    write(root, "vendor/helper.py", "X = 1\n")
    with pytest.raises(CaptureError, match="outside the allowed set"):
        CandidateVerifier(git, str(root), TASK).capture()


def test_cache_roots_lists_cachedir_tag_directories(tmp_path):
    from cld.executors._capture import cache_roots
    write(tmp_path, "a/CACHEDIR.TAG", TAG)
    write(tmp_path, "b/c/CACHEDIR.TAG", TAG)
    assert cache_roots(str(tmp_path)) == frozenset({"a", "b/c"})


def _snapshot_with(root, writer):
    verifier = CandidateVerifier(git, str(root), TASK)
    candidate = verifier.capture()
    with verifier.snapshot(candidate) as snap:
        writer(Path(snap))
    return verifier


@pytest.mark.parametrize("name", [".hypothesis/examples/x", ".coverage", "tmp_output.txt"])
def test_judge_may_create_untracked_files(tmp_path, name):
    root = make_repo(tmp_path)
    fix(root)
    verifier = _snapshot_with(root, lambda snap: write(snap, name, "db"))
    assert name in verifier.judge_untracked


def test_tracked_file_mutation_in_snapshot_still_fails(tmp_path):
    root = make_repo(tmp_path)
    fix(root)
    with pytest.raises(CaptureError, match="mutated the frozen candidate"):
        _snapshot_with(root, lambda snap: write(snap, "src/calc.py", "def add(a, b):\n    return 3\n"))


def test_tracked_file_deletion_in_snapshot_still_fails(tmp_path):
    root = make_repo(tmp_path)
    fix(root)
    with pytest.raises(CaptureError, match="mutated the frozen candidate"):
        _snapshot_with(root, lambda snap: (snap / "tests/test_calc.py").unlink())


def test_baseline_preflight_tolerates_hypothesis_db(tmp_path):
    root = make_repo(tmp_path)
    verifier = CandidateVerifier(git, str(root), TASK)

    def red_run(directory):
        write(Path(directory), ".hypothesis/examples/y", "db")
        from cld.test_run import TestRun
        return TestRun(1, "FAILED tests/test_calc.py::test_add - AssertionError: assert 0 == 3\n1 failed in 0.01s")

    verifier.preflight(red_run)
    assert verifier.baseline_passed is False
