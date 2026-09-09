"""Real-Git harness checks, including production capture of created files."""

import pytest

from cld.executors.base import Executor, SliceTask
from tests.integration.harness import (
    FileCreatingExecutor,
    init_repo,
    real_git_runner,
)

pytestmark = pytest.mark.integration


def test_real_git_runner_runs_git(git_repo):
    rc, out = real_git_runner(["git", "rev-parse", "--abbrev-ref", "HEAD"], git_repo)
    assert rc == 0
    assert out.strip()  # some branch name (master/main)


def test_init_repo_has_head_and_clean_tree(git_repo):
    rc, out = real_git_runner(["git", "status", "--porcelain"], git_repo)
    assert rc == 0
    assert out.strip() == ""  # clean after the initial commit
    rc, head = real_git_runner(["git", "rev-parse", "HEAD"], git_repo)
    assert rc == 0 and head.strip()  # HEAD exists


def test_file_creating_executor_writes_a_real_file(git_repo):
    ex = FileCreatingExecutor()
    assert isinstance(ex, Executor)  # satisfies the protocol
    task = SliceTask(id="S1", brief="b", files=["src/new_module.py"],
                     acceptance_test_path="tests/test_new.py")
    result = ex.run(task, git_repo)
    # the file really exists on disk in the workdir
    from pathlib import Path
    assert (Path(git_repo) / "src" / "new_module.py").is_file()
    assert result.ok is True


def test_harness_captures_created_file_content(git_repo):
    ex = FileCreatingExecutor(contents={"src/created.py": "VALUE = 42\n"})
    task = SliceTask(id="S1", brief="b", files=["src/created.py"],
                     acceptance_test_path="t.py")
    result = ex.run(task, git_repo)
    from pathlib import Path
    assert (Path(git_repo) / "src/created.py").read_text() == "VALUE = 42\n"
    rc, status = real_git_runner(["git", "status", "--porcelain", "-uall"], git_repo)
    assert rc == 0 and "src/created.py" in status
    assert result.files_changed == ["src/created.py"]
    assert "+VALUE = 42" in result.diff
