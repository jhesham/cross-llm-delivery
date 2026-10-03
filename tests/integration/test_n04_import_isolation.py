"""Acceptance must describe captured Git blobs, including editable source imports."""
from pathlib import Path
import os

import pytest

from cld.candidate import CandidateVerifier
from cld.cli import pytest_test_runner
from cld.executors.base import SliceTask
from cld.judge import judge
from cld.recovery import RecoverySession
from tests.integration.harness import init_repo, real_git_runner
from tests.integration.test_review_regressions import checked_git

pytestmark = pytest.mark.integration
MODULE = "n04_project_fixture"


@pytest.fixture
def project(tmp_path, monkeypatch):
    repo = Path(init_repo(tmp_path / "original project with spaces")).resolve()
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "src" / f"{MODULE}.py").write_text("VALUE = 0\n", encoding="utf-8")
    (repo / "tests/test_value.py").write_text(
        f"from {MODULE} import VALUE\n"
        "from thirdparty_helper import CONSTANT\n"
        "def test_value():\n    assert VALUE == 1\n    assert CONSTANT == 7\n",
        encoding="utf-8")
    checked_git(["add", "."], repo)
    checked_git(["commit", "-qm", "committed red acceptance"], repo)
    wt = (tmp_path / "executor project with spaces").resolve()
    checked_git(["worktree", "add", "--detach", str(wt), "HEAD"], repo)
    dependencies = tmp_path / "external dependencies"
    dependencies.mkdir()
    (dependencies / "thirdparty_helper.py").write_text("CONSTANT = 7\n", encoding="utf-8")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    task = SliceTask("N04", "Implement the value", [f"src/{MODULE}.py"], "tests/test_value.py")
    try:
        yield repo, wt, dependencies.resolve(), task
    finally:
        assert wt.is_relative_to(tmp_path.resolve())
        checked_git(["worktree", "remove", "--force", str(wt)], repo)


def import_environment(project, monkeypatch, style):
    repo, _, dependencies, _ = project
    source = repo / "src"
    paths = [str(dependencies)]
    if style == "pythonpath":
        paths.append(str(source))
    elif style == "pth":
        # Legacy editable installs add their source root during site initialization.
        (dependencies / "sitecustomize.py").write_text(
            f"import sys\nsys.path.insert(0, {str(source)!r})\n", encoding="utf-8")
    elif style == "pep660":
        # Modern editable installs can supply a meta-path finder rather than sys.path.
        (dependencies / "sitecustomize.py").write_text(
            "import sys, importlib.abc, importlib.util\n"
            "class EditableFinder(importlib.abc.MetaPathFinder):\n"
            "    def find_spec(self, fullname, path=None, target=None):\n"
            f"        if fullname == {MODULE!r}:\n"
            f"            return importlib.util.spec_from_file_location(fullname, {str(source / (MODULE + '.py'))!r})\n"
            "sys.meta_path.append(EditableFinder())\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(paths))


@pytest.mark.parametrize("style", ["pythonpath", "pth", "pep660"])
@pytest.mark.parametrize("candidate_correct", [False, True])
def test_live_checkout_cannot_supply_acceptance(project, monkeypatch, style, candidate_correct):
    repo, wt, _, task = project
    import_environment(project, monkeypatch, style)
    verifier = CandidateVerifier(real_git_runner, str(wt), task)
    verifier.preflight(lambda where: pytest_test_runner(where, task.acceptance_test_path))
    assert not verifier.baseline_passed
    value = int(candidate_correct)
    (wt / task.files[0]).write_text(f"VALUE = {value}\n# executor candidate\n", encoding="utf-8")
    # The lead checkout disagrees with the candidate, in both directions.
    (repo / task.files[0]).write_text(f"VALUE = {1 - value}\n", encoding="utf-8")
    candidate = verifier.capture()
    with verifier.snapshot(candidate) as frozen:
        result = pytest_test_runner(frozen, task.acceptance_test_path)
        verdict = judge(list(candidate.files_changed), task.files, run_tests=lambda: result)
    assert verdict.passed is candidate_correct, result.output
    verifier.verify_unchanged(candidate)
    if candidate_correct:
        session = RecoverySession(str(repo), str(wt), task, str(repo / "ledger.json"), real_git_runner)
        collection = session.collect(candidate)
        assert collection.ok, collection.error
        assert "VALUE = 1" in checked_git(["show", f"{collection.commit}:{task.files[0]}"], repo)


def test_module_loaded_from_live_source_at_startup_blocks_acceptance(project, monkeypatch):
    repo, wt, dependencies, task = project
    # Startup side effects cannot be undone safely by merely replacing sys.path.
    (repo / task.files[0]).write_text("VALUE = 1\n", encoding="utf-8")
    (dependencies / "sitecustomize.py").write_text(
        f"import sys\nsys.path.insert(0, {str(repo / 'src')!r})\nimport {MODULE}\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(dependencies))
    verifier = CandidateVerifier(real_git_runner, str(wt), task)
    candidate = verifier.capture()
    with verifier.snapshot(candidate) as frozen:
        result = pytest_test_runner(frozen, task.acceptance_test_path)
    assert not result.passed, result.output
    assert "outside the frozen candidate" in result.output


def test_test_time_import_loader_cannot_bypass_snapshot_policy(project, monkeypatch):
    repo, wt, dependencies, task = project
    # A trusted fixture can add a finder after pytest installs its own import hooks.
    late_import = (
        "import sys, importlib.abc, importlib.util\n"
        "class LateFinder(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        f"        if fullname == {MODULE!r}:\n"
        f"            return importlib.util.spec_from_file_location(fullname, {str(repo / task.files[0])!r})\n"
        "sys.meta_path.insert(0, LateFinder())\n"
        f"from {MODULE} import VALUE\n"
        "def test_value(): assert VALUE == 1\n")
    (wt / "tests/test_value.py").write_text(late_import, encoding="utf-8")
    checked_git(["add", "."], wt)
    checked_git(["commit", "-qm", "trusted import fixture"], wt)
    (repo / task.files[0]).write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(dependencies))
    verifier = CandidateVerifier(real_git_runner, str(wt), task)
    candidate = verifier.capture()
    with verifier.snapshot(candidate) as frozen:
        result = pytest_test_runner(frozen, task.acceptance_test_path)
    assert not result.passed, result.output
    assert "outside the frozen candidate" in result.output
