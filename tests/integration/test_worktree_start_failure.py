"""A slice whose worktree was never created never ran: it stays retryable instead of needing repair."""
from contextlib import contextmanager
from pathlib import Path

import pytest

import cld.worktree as worktree_module
from cld.ledger import Ledger
from cld.locking import OwnerBusy
from cld.orchestrator import PlanResult
from tests.integration.harness import FileCreatingExecutor, real_git_runner
from tests.integration.test_integration_lifecycle import repo, task, dispatch
from tests.integration.test_verified_repair import cli_plan

pytestmark = pytest.mark.integration


class _Counting(FileCreatingExecutor):
    def __init__(self):
        super().__init__(contents={"a.py": "VALUE = 1\n"})
        self.calls = 0

    def run(self, task, workdir, feedback=None):
        self.calls += 1
        return super().run(task, workdir, feedback)


def _busy_once(monkeypatch):
    real, calls = worktree_module.registry_owner, []

    @contextmanager
    def flaky(repo_dir, runner, **kwargs):
        calls.append(repo_dir)
        if len(calls) == 1:
            raise OwnerBusy("Active writer owns cld-worktrees.lock; retry after it exits")
        with real(repo_dir, runner, **kwargs):
            yield
    monkeypatch.setattr(worktree_module, "registry_owner", flaky)


def test_registry_lock_waits_for_parallel_worktree_creation(repo, monkeypatch):
    seen = []

    @contextmanager
    def owner(path, *, wait_seconds=0, cancel=None):
        seen.append(wait_seconds)
        yield
    monkeypatch.setattr(worktree_module, "file_owner", owner)
    with worktree_module.registry_owner(str(repo), real_git_runner):
        pass
    assert seen and seen[0] >= 120, seen


@pytest.mark.parametrize("planner", [None, lambda _task: [("workhorse", "fake:model", 1)]],
                         ids=["no-planner", "rung-planner"])
def test_worktree_creation_failure_leaves_the_slice_retryable(repo, monkeypatch, planner):
    _busy_once(monkeypatch)
    tasks, executor = [task()], _Counting()
    ledger, first = dispatch(repo, tasks, executor=executor, rung_planner=planner)
    entry = ledger.get("A")
    assert executor.calls == 0
    assert entry.status == "failed" and entry.attempts == 0, entry
    assert first.needs_repair == [] and first.failed == ["A"]
    assert "nothing was dispatched" in " ".join(first.details["A"].failing_tests)
    ledger, second = dispatch(repo, tasks, Ledger.load(ledger.path), executor=executor,
                              rung_planner=planner)
    assert executor.calls == 1
    assert ledger.get("A").status == "done", ledger.get("A")


def _stuck(repo, ledger, *, attempts=0, worktree_exists=False):
    path = repo / ".cld" / "worktrees" / "A-00000000-never-created"
    if worktree_exists:
        path.mkdir(parents=True)
    with ledger.writer():
        ledger.set("A", status="needs_repair", attempts=attempts, worktree_path=str(path))
        # As v0.5.4 recorded a session whose worktree was never created.
        ledger.get("A").history.append(dict(session_id="0" * 32, run_id=ledger.build["run_id"],
            branch="cld/x", worktree=str(path), recovery_path=None, state="failed",
            recovery_ref=None, collection={}))
        ledger.save()


def test_a_slice_stuck_before_its_worktree_existed_is_dispatched_again(repo):
    _, tasks, ledger = cli_plan(repo)
    _stuck(repo, ledger)
    executor = _Counting()
    ledger, result = dispatch(repo, tasks, Ledger.load(ledger.path), executor=executor)
    assert executor.calls == 1 and result.needs_repair == []
    assert ledger.get("A").status == "done"


@pytest.mark.parametrize("attempts,worktree_exists,requeued", [
    (0, False, True),    # never started: requeued
    (1, False, False),   # an attempt ran: real repair
    (0, True, False),    # a worktree is retained: real repair
])
def test_cli_step_requeues_only_slices_that_never_started(repo, monkeypatch, attempts,
                                                          worktree_exists, requeued):
    import skill.scripts.run_delivery as rd
    from cld.cli import _dispatchable
    path, tasks, ledger = cli_plan(repo)
    _stuck(repo, ledger, attempts=attempts, worktree_exists=worktree_exists)
    assert [s.id for s in _dispatchable(tasks, Ledger.load(ledger.path))] == (["A"] if requeued else [])
    monkeypatch.setattr(rd, "_preflight_executor", lambda *_: None)
    monkeypatch.setattr(rd, "build_executor_factory", lambda: None)
    monkeypatch.setattr(rd, "build_rung_planner", lambda *_: None)
    prepared = []
    monkeypatch.setattr(rd, "prepare_dispatch",
                        lambda args, slices, led: prepared.append(True) or (None, None))
    if requeued:
        monkeypatch.setattr(rd, "run_plan_parallel",
                            lambda slices, led, **kwargs: PlanResult(build_complete=False))
    code = rd.main([str(path), "--repo", str(repo), "--executor", "opencode:fake", "--step"])
    assert bool(prepared) == requeued, code
    if not requeued:
        assert code == 4
