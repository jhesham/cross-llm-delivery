"""T01 review regressions. Real Git/pytest; no provider CLI or network calls.

Only explicit contract failures are xfailed. Fixture/setup errors and unexpected
exceptions remain failures; strict XPASS forces removal of a marker after a fix.
See docs/plans/codex-support/T01-EVIDENCE.md for owners and baseline failures.
"""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.judge import judge
from cld.ledger import Ledger
from cld.orchestrator import run_plan_parallel
from tests.integration.harness import FileCreatingExecutor, real_git_runner

pytestmark = pytest.mark.integration
BODY = "VALUE = 42\n"


class ContractFailure(AssertionError):
    """Only a reached, unsatisfied safety contract may be an expected failure."""


def expect(condition, message):
    if not condition:
        raise ContractFailure(message)


def pending(issue):
    return pytest.mark.xfail(strict=True, raises=ContractFailure, reason=issue)


def checked_git(args, cwd):
    rc, out = real_git_runner(["git", *args], str(cwd))
    if rc:
        raise RuntimeError(f"test Git setup/inspection failed: {args}: {out}")
    return out


def acceptance(workdir, path):
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
           "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", path],
        cwd=workdir, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30,
    )
    return f"__CLD_PYTEST_RC__={proc.returncode}\n{proc.stdout}{proc.stderr}"


@pytest.fixture
def delivery_repo(git_repo):
    root = Path(git_repo)
    # Baseline is a real assertion failure, not a missing/import-broken test.
    (root / "implementation.py").write_text("VALUE = 0\n", encoding="utf-8")
    (root / "test_acceptance.py").write_text(
        "from implementation import VALUE\ndef test_value():\n    assert VALUE == 42\n",
        encoding="utf-8",
    )
    checked_git(["add", "-A"], root)
    checked_git(["commit", "-qm", "committed failing acceptance test"], root)
    output = acceptance(root, "test_acceptance.py")
    assert output.startswith("__CLD_PYTEST_RC__=1\n") and "1 failed" in output
    assert not checked_git(["status", "--porcelain"], root).strip()
    return root


def task(sid="A", deps=()):
    return SliceTask(id=sid, brief="Set VALUE to 42", files=["implementation.py"],
                     acceptance_test_path="test_acceptance.py", deps=list(deps))


def run(repo, *, executor=None, slices=None, **kwargs):
    options = dict(executor=executor or FileCreatingExecutor(
        contents={"implementation.py": BODY}), judge_fn=judge,
        test_runner=acceptance, repo_dir=str(repo), git_runner=real_git_runner,
        max_workers=1, max_retries=0)
    ledger = kwargs.pop("ledger", Ledger(str(repo / ".cld-ledger.json")))
    options.update(kwargs)
    return run_plan_parallel(slices or [task()], ledger, **options)


def has_committed_body(repo):
    refs = checked_git(["for-each-ref", "--format=%(refname)", "refs/heads"], repo)
    return any(real_git_runner(["git", "show", f"{ref}:implementation.py"], str(repo))
               == (0, BODY) for ref in refs.splitlines())


def has_recoverable_body(repo):
    if has_committed_body(repo):
        return True
    worktrees = checked_git(["worktree", "list", "--porcelain"], repo)
    for line in worktrees.splitlines():
        if line.startswith("worktree "):
            p = Path(line[len("worktree "):]) / "implementation.py"
            if p.is_file() and p.read_text(encoding="utf-8") == BODY:
                return True
    return any("+VALUE = 42" in p.read_text(encoding="utf-8")
               for p in (repo / ".cld").rglob("*.patch"))


class GitFault:
    """Inject nonzero RC for a selected Git command; all other commands are real."""
    def __init__(self, prefix, output="T01 injected Git failure\n"):
        self.prefix = prefix
        self.output = output
        self.hits = 0

    def __call__(self, args, cwd):
        if args[:len(self.prefix)] == self.prefix:
            self.hits += 1
            return 1, self.output
        return real_git_runner(args, cwd)


def test_executor_commit_cannot_hide_forbidden_file(delivery_repo):
    class Committer(FileCreatingExecutor):
        def run(self, t, wd, feedback=None):
            (Path(wd) / "forbidden.py").write_text("FORBIDDEN = True\n")
            (Path(wd) / "implementation.py").write_text(BODY)
            checked_git(["add", "-A"], wd)
            checked_git(["commit", "-qm", "executor-created commit"], wd)
            return super().run(t, wd, feedback)

    result = run(delivery_repo, executor=Committer(contents={"implementation.py": BODY}))
    expect("A" not in result.completed, "R01: executor commit hid forbidden.py")


def test_failed_dispatch_after_writes_is_rejected(delivery_repo):
    class FailedWriter:
        def run(self, t, wd):
            (Path(wd) / "implementation.py").write_text(BODY)
            (Path(wd) / "forbidden.py").write_text("FORBIDDEN = True\n")
            return ExecutorResult(ok=False, diff="", raw_log="dispatch failed after writes")

    result = run(delivery_repo, executor=FailedWriter())
    expect("A" not in result.completed, "R02: failed dispatch was accepted")


@pytest.mark.parametrize("ladder", [False, True], ids=["single", "ladder"])
def test_rejecting_commit_hook_preserves_candidate(delivery_repo, ladder):
    hooks = delivery_repo / ".git" / "review-hooks"
    hooks.mkdir()
    marker = delivery_repo / ".git" / "hook-ran"
    # Git executes this hook using its POSIX shell, including Git for Windows.
    hook = hooks / "pre-commit"
    hook.write_text('#!/bin/sh\necho rejected > "$(git rev-parse --git-common-dir)/hook-ran"\nexit 1\n',
                    encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    checked_git(["config", "core.hooksPath", hooks.as_posix()], delivery_repo)
    options = {"rung_planner": lambda t: [("workhorse", "fake:model", 1)]} if ladder else {}
    result = run(delivery_repo, **options)
    assert marker.is_file(), "the real hook must have rejected the collection commit"
    expect("A" not in result.completed and has_recoverable_body(delivery_repo),
           "R03: commit rejection accepted and/or discarded the candidate")


def test_escalation_dispatches_second_rung(delivery_repo):
    calls = []

    class ImprovingWriter(FileCreatingExecutor):
        def run(self, t, wd, feedback=None):
            calls.append(str(wd))
            self._contents = {"implementation.py": "VALUE = 1\n" if len(calls) == 1 else BODY}
            return super().run(t, wd, feedback)

    result = run(delivery_repo, executor=ImprovingWriter(), rung_planner=lambda t: [
        ("quick", "fake:quick", 1), ("workhorse", "fake:workhorse", 1)])
    expect(len(calls) == 2 and result.completed == ["A"],
           "R04: escalation did not dispatch twice and complete")


@pending("R05 / T06: dependent work must see the accepted dependency")
def test_dependent_dispatch_has_dependency_code(delivery_repo):
    seen = []

    class Observer(FileCreatingExecutor):
        def run(self, t, wd, feedback=None):
            if t.id == "B":
                seen.append((Path(wd) / "implementation.py").read_text() == BODY)
            return super().run(t, wd, feedback)

    result = run(delivery_repo, executor=Observer(contents={"implementation.py": BODY}),
                 slices=[task(), task("B", ["A"])])
    expect(seen == [True] and "B" in result.completed,
           "R05: B ran against HEAD without A's implementation")


@pending("R05 / T06: failed dependency must block dependent dispatch")
def test_failed_dependency_blocks_dispatch(delivery_repo):
    calls = []

    class FailingWriter(FileCreatingExecutor):
        def run(self, t, wd, feedback=None):
            calls.append(t.id)
            return super().run(t, wd, feedback)

    run(delivery_repo, executor=FailingWriter(contents={"implementation.py": "VALUE = 1\n"}),
        slices=[task(), task("B", ["A"])])
    expect(calls == ["A"], "R05: B dispatched despite failed A")


def test_judge_exception_preserves_candidate(delivery_repo):
    calls = []

    def broken_judge(**kwargs):
        calls.append(1)
        raise OSError("T01 judge output unavailable")

    result = run(delivery_repo, judge_fn=broken_judge)
    assert calls == [1]
    expect("A" not in result.completed and has_recoverable_body(delivery_repo),
           "R03: judge exception discarded the only candidate")


def test_diff_capture_error_cannot_accept_candidate(delivery_repo):
    # Empty captured output is not evidence that the command succeeded. Nonempty
    # error text would accidentally be interpreted as a disallowed filename.
    fault = GitFault(["git", "diff"], output="")
    dispatched = []
    class Writer:
        def run(self, t, wd):
            (Path(wd) / "implementation.py").write_text(BODY)
            dispatched.append(wd)
            return ExecutorResult(True, "", [])

    def after_dispatch(args, cwd):
        return fault(args, cwd) if dispatched else real_git_runner(args, cwd)

    result = run(delivery_repo, git_runner=after_dispatch, executor=Writer())
    assert len(dispatched) == 1 and fault.hits > 0
    expect("A" not in result.completed, "R01: failed diff capture was accepted")


def test_ledger_save_failure_leaves_reachable_implementation(delivery_repo):
    class FailingLedger(Ledger):
        hits = 0

        def save(self):
            if self.is_done("A"):
                self.hits += 1
                raise OSError("T01 injected ledger write failure")
            super().save()

    ledger = FailingLedger(str(delivery_repo / ".cld-ledger.json"))
    with pytest.raises(OSError, match="T01 injected ledger"):
        run(delivery_repo, ledger=ledger)
    assert ledger.hits == 1
    assert not Ledger.load(ledger.path).is_done("A")
    assert has_committed_body(delivery_repo), "already-collected code must remain reachable"


def test_cleanup_failure_retains_worktree_and_commit(delivery_repo):
    fault = GitFault(["git", "worktree", "remove"])
    run(delivery_repo, git_runner=fault)
    assert fault.hits == 1
    assert has_committed_body(delivery_repo)
    listed = checked_git(["worktree", "list", "--porcelain"], delivery_repo)
    paths = [Path(line[len("worktree "):]) for line in listed.splitlines()
             if line.startswith("worktree ")]
    assert len(paths) == 2
    # Every retained directory belongs to this test's tmp_path; no global cleanup.
    assert all(p.resolve().is_relative_to(delivery_repo.parent.resolve()) for p in paths)
    assert any((p / "implementation.py").read_text() == BODY for p in paths)
