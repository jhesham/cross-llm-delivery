"""B1.1 smoke test — proves the real-git harness functions.

This does NOT yet assert the bug (that's B1.2). It only verifies the harness
itself works: a real repo initializes, the file-creating fake executor actually
writes a file into the workdir, and the real git_runner operates on it. It also
records (without judging) what the real `git diff HEAD` capture reports — which is
the exact surface B1.2 will turn into a failing assertion.
"""

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


def test_harness_exposes_the_capture_surface_b12_will_assert(git_repo):
    """Record (not judge) what `git diff HEAD` reports for a freshly CREATED file.

    The created file is UNTRACKED, so `git diff HEAD --name-only` may not list it.
    B1.1 only documents this surface exists and is observable; B1.2 makes it a
    failing assertion against the bug.
    """
    ex = FileCreatingExecutor()
    task = SliceTask(id="S1", brief="b", files=["src/created.py"],
                     acceptance_test_path="t.py")
    result = ex.run(task, git_repo)
    # the harness gives us the real capture output to inspect — that's the point.
    assert hasattr(result, "files_changed")
    assert isinstance(result.files_changed, list)
