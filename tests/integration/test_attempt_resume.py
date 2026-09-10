"""T04: real Git, OS ownership and restart boundaries; no model calls."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from cld.attempts import ActiveAttempt, slice_owner
from cld.executors.base import ExecutorResult
from cld.ledger import Ledger
from cld.worktree import managed_location, validate_location
from cld.executors._capture import CaptureError
from tests.integration.harness import real_git_runner
from tests.integration.test_collection_recovery import Writer, metadata
from tests.integration.test_review_regressions import BODY, checked_git, delivery_repo, run

pytestmark = pytest.mark.integration


def child_env():
    project = Path(__file__).resolve().parents[2]
    return {**os.environ, "PYTHONPATH": os.pathsep.join([str(project / "engine"), str(project)])}


def test_escalation_uses_unique_paths_and_preserved_feedback(delivery_repo):
    class Improving:
        def __init__(self):
            self.calls = []

        def run(self, task, wd, feedback=None):
            self.calls.append((wd, feedback))
            # Escalation starts from the immutable base, not a failed candidate.
            assert (Path(wd) / "implementation.py").read_text() == "VALUE = 0\n"
            (Path(wd) / "implementation.py").write_text("VALUE = 1\n" if len(self.calls) == 1 else BODY)
            return ExecutorResult(True, "")

    ex = Improving()
    result = run(delivery_repo, executor=ex,
                 rung_planner=lambda t: [("quick", "fake:quick", 1), ("workhorse", "fake:large", 1)])
    assert result.completed == ["A"] and len(ex.calls) == 2, result.details
    old, new = ex.calls
    assert old[0] != new[0] and Path(old[0]).exists() and not Path(new[0]).exists()
    assert old[0].replace("\\", "\\\\") in new[1] and len(new[1]) <= 6000
    record = metadata(result)
    assert record["retry_policy"] == "fresh-base" and record["previous"]["ref_exists"]
    assert record["run_id"] in record["branch"] and record["session_id"] in record["branch"]


def test_hard_stop_restarts_with_candidate_pointer_and_no_branch_reset(delivery_repo):
    code = '''
import os, sys
from pathlib import Path
from tests.integration.test_review_regressions import run, BODY
class Stop:
    def run(self, task, wd, feedback=None):
        (Path(wd) / "implementation.py").write_text(BODY)
        os._exit(17)
run(Path(sys.argv[1]), executor=Stop())
'''
    child = subprocess.run([sys.executable, "-c", code, str(delivery_repo)],
                           env=child_env(), capture_output=True, timeout=60)
    assert child.returncode == 17, child.stderr.decode(errors="replace")
    record_path = next((delivery_repo / ".cld/A").glob("*/outcome.json"))
    old = json.loads(record_path.read_text(encoding="utf-8"))
    assert old["state"] == "running"
    old_head = checked_git(["rev-parse", old["branch"]], delivery_repo)
    class Resume(Writer):
        def run(self, task, wd, feedback=None):
            assert "stale" in feedback and old["session_id"] in feedback
            assert (Path(old["worktree"]) / "implementation.py").read_text() == BODY
            return super().run(task, wd, feedback)
    result = run(delivery_repo, executor=Resume())
    assert result.completed == ["A"], result.details
    assert checked_git(["rev-parse", old["branch"]], delivery_repo) == old_head
    assert Path(old["worktree"]).exists()


@pytest.mark.parametrize("missing", ["worktree", "ref"])
def test_orphans_do_not_block_new_attempt_or_delete_other_evidence(delivery_repo, missing):
    first = run(delivery_repo, executor=Writer(lambda t, wd: ExecutorResult(False, "", raw_log="failed")))
    old = metadata(first)
    if missing == "worktree":
        path = Path(old["worktree"]).resolve()
        assert path.is_relative_to(delivery_repo.resolve())
        checked_git(["worktree", "remove", "--force", str(path)], delivery_repo)
    else:
        checked_git(["update-ref", "-d", old["recovery_ref"]], delivery_repo)
    result = run(delivery_repo, executor=Writer())
    assert result.completed == ["A"], result.details
    previous = metadata(result)["previous"]
    assert previous["worktree_exists"] is (missing != "worktree")
    assert previous["ref_exists"] is (missing != "ref")
    assert Path(old["patch"]).is_file()
    assert checked_git(["rev-parse", old["branch"]], delivery_repo).strip() == old["base"]


def test_legacy_candidate_is_read_and_never_reset(delivery_repo):
    checked_git(["branch", "slice-A"], delivery_repo)
    before = checked_git(["rev-parse", "slice-A"], delivery_repo)
    result = run(delivery_repo, executor=Writer())
    assert result.completed == ["A"], result.details
    assert metadata(result)["previous"]["ref"] == "refs/heads/slice-A"
    assert checked_git(["rev-parse", "slice-A"], delivery_repo) == before


def test_configured_workspace_root_and_creation_boundary(delivery_repo):
    root = delivery_repo / "writable-worktrees"
    mutations = []
    def runner(args, cwd):
        if args[:3] in (["git", "worktree", "add"], ["git", "worktree", "remove"]):
            path = Path(args[5] if args[2] == "add" else args[4]).resolve()
            assert path.parent == root.resolve()
            mutations.append(args[2])
        return real_git_runner(args, cwd)
    result = run(delivery_repo, executor=Writer(), worktree_root="writable-worktrees", git_runner=runner)
    assert result.completed == ["A"] and mutations == ["add", "remove"], result.details
    assert metadata(result)["worktree_root"] == str(root.resolve())
    with pytest.raises(CaptureError):
        managed_location(delivery_repo, delivery_repo.parent, "a" * 32, "A", "b" * 32)
    with pytest.raises(CaptureError):
        validate_location(root / ".." / "unrelated", root.resolve())


def test_active_owner_defers_without_touching_ledger_or_dispatch(delivery_repo):
    ledger_path = delivery_repo / ".cld-ledger.json"
    ledger_path.write_text('{"sentinel": "untouched"}')
    ex = Writer()
    with slice_owner(str(delivery_repo), "A", real_git_runner):
        result = run(delivery_repo, executor=ex)
    assert result.deferred == ["A"] and not ex.calls
    assert "active owner" in result.details["A"].failing_tests[0]
    assert ledger_path.read_text() == '{"sentinel": "untouched"}'


def test_creation_failure_has_durable_reservation_and_can_restart(delivery_repo):
    def runner(args, cwd):
        if args[:3] == ["git", "worktree", "add"]:
            records = list((delivery_repo / ".cld/A").glob("*/outcome.json"))
            assert len(records) == 1
            assert json.loads(records[0].read_text(encoding="utf-8"))["state"] == "reserved"
            return 1, "injected creation failure"
        return real_git_runner(args, cwd)
    ex = Writer()
    failed = run(delivery_repo, executor=ex, git_runner=runner)
    assert failed.failed == ["A"] and not ex.calls
    old = metadata(failed)
    result = run(delivery_repo, executor=ex)
    assert result.completed == ["A"] and len(ex.calls) == 1, result.details
    assert metadata(result)["previous"]["session_id"] == old["session_id"]
    assert metadata(result)["session_id"] != old["session_id"]


def test_cleanup_does_not_touch_reassigned_worktree(delivery_repo):
    class Reassign(Ledger):
        def save(self):
            super().save()
            if self.is_done("A"):
                checked_git(["checkout", "-b", "unrelated"], self.get("A").worktree_path)
    result = run(delivery_repo, executor=Writer(),
                 ledger=Reassign(str(delivery_repo / ".cld-ledger.json")))
    detail = result.details["A"]
    assert result.completed == ["A"] and "branch changed" in detail.cleanup_warning
    assert Path(detail.worktree_path).exists()
    assert checked_git(["rev-parse", "unrelated"], delivery_repo).strip() == detail.commit


def test_os_lock_excludes_other_process_and_releases_on_exit(delivery_repo):
    code = '''
import sys
from cld.attempts import slice_owner
from tests.integration.harness import real_git_runner
with slice_owner(sys.argv[1], "A", real_git_runner):
    print("owned", flush=True)
    sys.stdin.readline()
'''
    child = subprocess.Popen([sys.executable, "-c", code, str(delivery_repo)],
                             env=child_env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "owned"
        with pytest.raises(ActiveAttempt):
            with slice_owner(str(delivery_repo), "A", real_git_runner):
                pytest.fail("duplicate owner")
    finally:
        child.communicate("exit\n", timeout=20)
    assert child.returncode == 0
    with slice_owner(str(delivery_repo), "A", real_git_runner):
        pass
