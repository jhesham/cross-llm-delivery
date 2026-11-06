"""v0.6.0 review fixes: retained repair work, cancellable registry waits, the dispatch guard."""
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest

import cld.worktree as worktree_module
from cld.dispatch_limits import guard, lock_path
from cld.ledger import LedgerEntry
from cld.locking import OwnerBusy, file_owner
from cld.process import process_scope
from tests.integration.harness import real_git_runner
from tests.integration.test_integration_lifecycle import repo  # noqa: F401 (fixture)
from tests.integration.test_verified_repair import failed, repair

pytestmark = pytest.mark.integration

AGY = "antigravity:Gemini 4 Argon (High)"


# --- never_started() needs positive evidence -------------------------------------------

def _entry(tmp_path, *, history, worktree_exists=False):
    path = tmp_path / "wt-never-created"
    if worktree_exists:
        path.mkdir()
    return LedgerEntry("A", status="needs_repair", attempts=0, worktree_path=str(path),
                       history=history)


def _session(tmp_path, name="wt-never-created"):
    return dict(session_id=uuid4().hex, run_id=uuid4().hex, branch="cld/x", state="failed",
                worktree=str(tmp_path / name), recovery_path=str(tmp_path / "evidence"))


def test_a_slice_whose_only_sessions_never_created_a_worktree_never_started(tmp_path):
    assert _entry(tmp_path, history=[_session(tmp_path), _session(tmp_path)]).never_started(refs=set())


def test_without_git_evidence_a_slice_is_not_assumed_to_have_never_started(tmp_path):
    assert not _entry(tmp_path, history=[_session(tmp_path)]).never_started()


def test_an_entry_without_session_history_is_not_assumed_to_have_never_started(tmp_path):
    assert not _entry(tmp_path, history=[]).never_started(refs=set())


def test_a_repair_in_the_history_means_the_slice_started(tmp_path):
    history = [_session(tmp_path), dict(repair_of=str(tmp_path / "evidence"), error="busy")]
    assert not _entry(tmp_path, history=history).never_started(refs=set())


def test_a_retained_earlier_worktree_means_the_slice_started(tmp_path):
    (tmp_path / "earlier").mkdir()
    history = [_session(tmp_path, "earlier"), _session(tmp_path)]
    assert not _entry(tmp_path, history=history).never_started(refs=set())


def test_a_surviving_session_branch_means_the_worktree_was_created(tmp_path):
    session = _session(tmp_path)
    entry = _entry(tmp_path, history=[session])
    assert not entry.never_started(refs={f"refs/heads/{session['branch']}"})


@pytest.mark.parametrize("ref", ["refs/cld/recovery/{sid}/head", "refs/cld/accepted/{sid}"])
def test_a_session_recovery_ref_means_the_slice_started(tmp_path, ref):
    session = _session(tmp_path)
    entry = _entry(tmp_path, history=[session])
    assert not entry.never_started(refs={ref.format(sid=session["session_id"])})


def test_the_cli_keeps_a_slice_whose_branch_holds_manual_work(repo):
    # The reviewer's case: the worktree was created (preflight then failed, no recovery ref),
    # the lead committed manual work on the recorded branch and removed the checkout.
    from cld.cli import _dispatchable
    from cld.ledger import Ledger
    from tests.integration.test_verified_repair import cli_plan
    from tests.integration.test_worktree_start_failure import _stuck
    _, tasks, ledger = cli_plan(repo)
    _stuck(repo, ledger)
    assert [s.id for s in _dispatchable(tasks, Ledger.load(ledger.path))] == ["A"]
    subprocess.run(["git", "branch", "cld/x", "HEAD"], cwd=repo, check=True, capture_output=True)
    assert _dispatchable(tasks, Ledger.load(ledger.path)) == []


def test_a_repair_that_cannot_create_its_worktree_keeps_the_original_attempt(repo, monkeypatch):
    tasks, ledger = failed(repo)
    original, evidence = ledger.get("A").worktree_path, ledger.get("A").recovery_path
    (Path(original) / "a.py").write_text("VALUE = 1\n")  # the lead's manual repair
    real = worktree_module.registry_owner

    @contextmanager
    def busy(*_args, **_kwargs):
        raise OwnerBusy("Active writer owns cld-worktrees.lock; retry after it exits")
        yield
    monkeypatch.setattr(worktree_module, "registry_owner", busy)
    rejected = repair(repo, tasks, ledger)
    entry = ledger.get("A")
    assert not rejected.passed and entry.status == "needs_repair"
    assert entry.worktree_path == original and entry.recovery_path == evidence, entry
    entry.attempts = 0  # as when the baseline preflight failed before any dispatch
    assert not entry.never_started()
    monkeypatch.setattr(worktree_module, "registry_owner", real)
    assert repair(repo, tasks, ledger).passed  # the retained work is still repairable


# --- registry waits stop when the build is cancelled -----------------------------------

def _head(repo):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def _registry_lock(repo):
    common = subprocess.check_output(["git", "rev-parse", "--path-format=absolute",
                                      "--git-common-dir"], cwd=repo, text=True).strip()
    return Path(common).resolve() / "cld-worktrees.lock"


def _location(repo):
    return worktree_module.managed_location(str(repo), None, uuid4().hex, "A", uuid4().hex,
                                            create_root=True)


def _create(repo, wt, root, branch):
    with worktree_module.worktree(str(repo), branch, runner=real_git_runner, cleanup=False,
                                  path=wt, root=root, base=_head(repo)):
        pass


def test_cancelling_the_build_stops_a_worktree_waiting_for_the_registry(repo):
    wt, root, branch = _location(repo)
    cancel, outcome = threading.Event(), []

    def waiter():
        with process_scope(cancel=cancel):
            try:
                _create(repo, wt, root, branch)
                outcome.append("created")
            except BaseException as exc:  # noqa: BLE001 - the outcome is the assertion
                outcome.append(exc)

    with file_owner(_registry_lock(repo)):
        thread = threading.Thread(target=waiter)
        thread.start()
        time.sleep(0.3)
        cancel.set()
        began = time.monotonic()
        thread.join(10)
        elapsed = time.monotonic() - began
    assert not thread.is_alive()
    assert outcome and isinstance(outcome[0], KeyboardInterrupt), outcome
    assert elapsed < 3, f"the cancelled registry wait took {elapsed:.1f}s"
    assert not Path(wt).exists()


def test_no_worktree_is_created_once_the_build_is_cancelled(repo):
    wt, root, branch = _location(repo)
    cancel = threading.Event()
    cancel.set()
    with process_scope(cancel=cancel), pytest.raises(KeyboardInterrupt):
        _create(repo, wt, root, branch)
    assert not Path(wt).exists()


def test_removing_a_worktree_still_completes_after_cancellation(repo):
    wt, root, branch = _location(repo)
    _create(repo, wt, root, branch)
    cancel = threading.Event()
    cancel.set()
    with process_scope(cancel=cancel):
        worktree_module.remove_worktree(str(repo), wt, runner=real_git_runner, root=root,
                                        branch=branch)
    assert not Path(wt).exists()


# --- the dispatch guard ------------------------------------------------------------------

@pytest.fixture
def lock_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLD_DISPATCH_LOCK_DIR", str(tmp_path / "locks"))


class _NoFeedback:
    def __init__(self):
        self.calls = []

    def run(self, task, workdir):
        self.calls.append((task, workdir))
        return "ok"


def test_the_guard_drops_retry_feedback_for_an_executor_without_it(lock_dir):
    inner = _NoFeedback()
    guarded = guard(inner, AGY)
    assert guarded.run("task", "wd") == "ok"
    assert guarded.run("task", "wd", feedback="tests failed") == "ok"
    assert inner.calls == [("task", "wd"), ("task", "wd")]


def test_the_guard_holds_the_slot_for_evidence_dispatches(lock_dir):
    class _Evidence(_NoFeedback):
        def run_evidence(self, prompt, workdir):
            try:
                with file_owner(lock_path("antigravity")):
                    return "slot free"
            except OwnerBusy:
                return "slot held"

    assert guard(_Evidence(), AGY).run_evidence("prompt", "wd") == "slot held"
    assert not hasattr(guard(_NoFeedback(), AGY), "run_evidence")


# --- unreadable refs are inconclusive (production runner keeps stderr separate) -------

def _break_branch(repo, branch="cld/x"):
    # Git skips a ref it cannot parse: exit 0, a stderr warning, and no stdout line.
    ref = Path(repo) / ".git" / "refs" / "heads" / Path(branch)
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text("not-a-sha\n", encoding="utf-8")


def test_git_warnings_make_the_ref_listing_inconclusive(repo):
    from cld.cli import git_runner
    from cld.executors._capture import CaptureError
    from cld.worktree import repository_refs
    assert "refs/heads/" + "cld/x" not in repository_refs(str(repo), git_runner)
    _break_branch(repo)
    with pytest.raises(CaptureError):
        repository_refs(str(repo), git_runner)


def test_the_cli_keeps_a_slice_whose_session_branch_is_broken(repo):
    from cld.cli import _dispatchable
    from cld.ledger import Ledger
    from tests.integration.test_verified_repair import cli_plan
    from tests.integration.test_worktree_start_failure import _stuck
    _, tasks, ledger = cli_plan(repo)
    _stuck(repo, ledger)
    _break_branch(repo)
    assert _dispatchable(tasks, Ledger.load(ledger.path)) == []


def test_the_orchestrator_keeps_a_slice_whose_session_branch_is_broken(repo):
    from cld.cli import git_runner
    from cld.ledger import Ledger
    from tests.integration.test_integration_lifecycle import dispatch
    from tests.integration.test_verified_repair import cli_plan
    from tests.integration.test_worktree_start_failure import _Counting, _stuck
    _, tasks, ledger = cli_plan(repo)
    _stuck(repo, ledger)
    _break_branch(repo)
    executor = _Counting()
    _, result = dispatch(repo, tasks, Ledger.load(ledger.path), executor=executor,
                         git_runner=git_runner)
    assert executor.calls == 0 and result.needs_repair == ["A"], result
