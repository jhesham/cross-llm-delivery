"""T03: accepted trees survive failures, and only durable outcomes permit cleanup."""
import json
from pathlib import Path

import pytest

from cld import recovery
from cld.executors.base import ExecutorResult
from cld.ledger import Ledger
from cld.summary import summarize_layer
from tests.integration.harness import FileCreatingExecutor, real_git_runner
from tests.integration.test_review_regressions import BODY, checked_git, delivery_repo, run, task

pytestmark = pytest.mark.integration


class Writer:
    def __init__(self, action=None):
        self.action = action
        self.calls = []

    def run(self, t, wd, feedback=None):
        self.calls.append(wd)
        (Path(wd) / "implementation.py").write_text(BODY, encoding="utf-8")
        if self.action:
            return self.action(t, Path(wd))
        return ExecutorResult(True, "", raw_log=f"dispatch {len(self.calls)}")


def metadata(result):
    return json.loads((Path(result.details["A"].recovery_path) / "outcome.json").read_text(encoding="utf-8"))


def assert_original_unchanged(repo, head):
    assert checked_git(["rev-parse", "HEAD"], repo).strip() == head
    assert (repo / "implementation.py").read_text() == "VALUE = 0\n"
    assert not checked_git(["diff", "HEAD"], repo)


def test_success_records_reachable_tested_tree_before_cleanup(delivery_repo):
    base = checked_git(["rev-parse", "HEAD"], delivery_repo).strip()
    result = run(delivery_repo, executor=Writer())
    assert result.completed == ["A"], result.details
    record = metadata(result)
    entry = Ledger.load(str(delivery_repo / ".cld-ledger.json")).get("A")
    assert entry.status == "done" and entry.commit == record["collection"]["commit"]
    assert entry.collection["tree"] == record["candidate"]["tree"]
    assert entry.collection["tests_fingerprint"] == record["candidate"]["tests_fingerprint"]
    assert record["state"] == "collected"
    assert not Path(entry.worktree_path).exists()
    # Accepted ref is independent of the old slice branch lifetime.
    checked_git(["update-ref", "-d", f'refs/heads/{record["branch"]}'], delivery_repo)
    assert checked_git(["show", f'{entry.collection["ref"]}:implementation.py'], delivery_repo) == BODY
    assert_original_unchanged(delivery_repo, base)


@pytest.mark.parametrize("failure", ["add", "commit", "accepted-ref", "patch-check"])
def test_git_failures_never_accept_or_delete_the_worktree(delivery_repo, failure):
    ex = Writer()
    hits = []
    def runner(args, cwd):
        should_fail = bool(ex.calls) and (
            (failure in ("add", "commit") and args[:2] == ["git", failure])
            or (failure == "accepted-ref" and args[:2] == ["git", "update-ref"]
                and args[2].startswith("refs/cld/accepted/"))
            or (failure == "patch-check" and args[:2] == ["git", "apply"]))
        if should_fail:
            hits.append(args)
            return 1, "T03 injected Git failure"
        return real_git_runner(args, cwd)
    result = run(delivery_repo, executor=ex, git_runner=runner)
    assert hits and result.failed == ["A"], result.details
    path = Path(result.details["A"].worktree_path)
    assert path.is_dir() and (path / "implementation.py").read_text() == BODY
    assert str(path) in " ".join(result.details["A"].failing_tests)
    assert not Ledger.load(str(delivery_repo / ".cld-ledger.json")).is_done("A")


@pytest.mark.parametrize("failure", ["patch", "outcome"])
def test_evidence_write_failure_retains_implementation(delivery_repo, monkeypatch, failure):
    original = recovery.atomic_write
    def faulty(path, data):
        if ((failure == "patch" and path.suffix == ".patch")
                or (failure == "outcome" and path.name == "outcome.json"
                    and json.loads(data).get("state") == "collected")):
            raise OSError("T03 disk full")
        return original(path, data)
    monkeypatch.setattr(recovery, "atomic_write", faulty)
    result = run(delivery_repo, executor=Writer())
    assert result.failed == ["A"]
    assert (Path(result.details["A"].worktree_path) / "implementation.py").read_text() == BODY
    assert "disk full" in " ".join(result.details["A"].failing_tests)


@pytest.mark.parametrize("stage", [True, False])
def test_commit_hook_mutation_cannot_change_the_accepted_tree(delivery_repo, stage):
    hooks = delivery_repo / ".git" / "t03-hooks"
    hooks.mkdir()
    hook = hooks / "pre-commit"
    hook.write_text('#!/bin/sh\nprintf "VALUE = 13\\n" > implementation.py\n'
                    + ('git add implementation.py\n' if stage else '') + 'exit 0\n',
                    encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    checked_git(["config", "core.hooksPath", hooks.as_posix()], delivery_repo)
    result = run(delivery_repo, executor=Writer())
    assert result.failed == ["A"], result.details
    record = metadata(result)
    # Preserve the tested tree even though the hook overwrote the physical file.
    verified_ref = f'refs/cld/recovery/{record["session_id"]}/verified'
    assert checked_git(["show", f"{verified_ref}:implementation.py"], delivery_repo) == BODY
    assert Path(result.details["A"].worktree_path).exists()


def test_binary_and_executor_committed_patch_reconstructs_from_base(delivery_repo, tmp_path):
    base = checked_git(["rev-parse", "HEAD"], delivery_repo).strip()
    binary = b"\x00\xff\x80T03\x00"
    def write(t, wd):
        (wd / "asset.bin").write_bytes(binary)
        checked_git(["add", "-A"], wd)
        checked_git(["commit", "-qm", "executor checkpoint"], wd)
        (wd / "after.txt").write_text("after commit", encoding="utf-8")
        return ExecutorResult(False, "", raw_log="provider failed after committed and untracked writes")
    result = run(delivery_repo, executor=Writer(write))
    assert result.failed == ["A"]
    record = metadata(result)
    patch = Path(record["patch"])
    assert "GIT binary patch" in patch.read_text(encoding="utf-8")
    rebuilt = tmp_path / "rebuilt"
    checked_git(["clone", "--no-checkout", str(delivery_repo), str(rebuilt)], tmp_path)
    checked_git(["checkout", "--detach", base], rebuilt)
    checked_git(["apply", "--index", "--binary", str(patch)], rebuilt)
    assert (rebuilt / "asset.bin").read_bytes() == binary
    assert (rebuilt / "after.txt").read_text() == "after commit"
    assert (rebuilt / "implementation.py").read_text() == BODY
    assert checked_git(["write-tree"], rebuilt).strip() == record["recovery_tree"]
    dispatch = Path(result.details["A"].recovery_path) / "attempt-1/dispatch.txt"
    assert "provider failed" in dispatch.read_text()
    assert_original_unchanged(delivery_repo, base)


def test_ledger_failure_rolls_back_memory_and_recovers_without_dispatch(delivery_repo):
    class FailDone(Ledger):
        def save(self):
            if self.is_done("A"):
                raise OSError("T03 ledger unavailable")
            super().save()
    ledger = FailDone(str(delivery_repo / ".cld-ledger.json"))
    ex = Writer()
    with pytest.raises(OSError, match="ledger unavailable") as error:
        run(delivery_repo, executor=ex, ledger=ledger)
    assert not ledger.is_done("A")
    assert len(ex.calls) == 1 and Path(ex.calls[0]).exists()
    assert any(ex.calls[0] in note for note in error.value.__notes__)
    records = list((delivery_repo / ".cld/A").glob("*/outcome.json"))
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["state"] == "collected"
    restarted = Ledger.load(ledger.path)
    result = run(delivery_repo, executor=ex, ledger=restarted)
    assert result.completed == ["A"], result.details
    assert len(ex.calls) == 1, "recovery must not rerun a provider"
    assert restarted.get("A").commit == record["collection"]["commit"]
    assert not Path(ex.calls[0]).exists()


def test_cleanup_failure_is_reported_after_durable_acceptance(delivery_repo):
    def runner(args, cwd):
        if args[:3] == ["git", "worktree", "remove"]:
            return 1, "T03 directory busy"
        return real_git_runner(args, cwd)
    result = run(delivery_repo, git_runner=runner, executor=Writer())
    detail = result.details["A"]
    assert result.completed == ["A"] and detail.commit
    assert "directory busy" in detail.cleanup_warning
    assert Path(detail.worktree_path).is_dir()
    assert "retained" in summarize_layer(result, layer_index=0, total_layers=1, next_layer=[])
    assert Ledger.load(str(delivery_repo / ".cld-ledger.json")).get("A").commit == detail.commit


def test_retry_keeps_each_attempt_patch_and_diagnostics(delivery_repo):
    count = []
    def write(t, wd):
        count.append(wd)
        (wd / "implementation.py").write_text("VALUE = 1\n" if len(count) == 1 else BODY)
        return ExecutorResult(True, "", raw_log=f"provider output {len(count)}")
    result = run(delivery_repo, executor=Writer(write), max_retries=1)
    assert result.completed == ["A"] and len(count) == 2, result.details
    directory = Path(result.details["A"].recovery_path)
    for attempt in [1, 2]:
        evidence = directory / f"attempt-{attempt}"
        assert (evidence / "dispatch.txt").read_text() == f"provider output {attempt}"
        assert (evidence / "dispatch.patch").is_file()
        assert (evidence / "judge.txt").is_file()
    assert "+VALUE = 1" in (directory / "attempt-1/dispatch.patch").read_text()
    assert "+VALUE = 42" in (directory / "attempt-2/dispatch.patch").read_text()


@pytest.mark.parametrize("exception", [ValueError, KeyboardInterrupt])
def test_dispatch_exception_preserves_files(delivery_repo, exception):
    def broken(t, wd):
        raise exception("T03 interrupted executor")
    ex = Writer(broken)
    if exception is KeyboardInterrupt:
        with pytest.raises(KeyboardInterrupt):
            run(delivery_repo, executor=ex)
    else:
        assert run(delivery_repo, executor=ex).failed == ["A"]
    assert (Path(ex.calls[0]) / "implementation.py").read_text() == BODY
    assert list((delivery_repo / ".cld/A").glob("*/attempt-1/error.txt"))


def test_valid_noop_does_not_invoke_commit(delivery_repo):
    (delivery_repo / "implementation.py").write_text(BODY)
    checked_git(["add", "-A"], delivery_repo)
    checked_git(["commit", "-qm", "already satisfied"], delivery_repo)
    commits = []
    def runner(args, cwd):
        if args[:2] == ["git", "commit"]:
            commits.append(args)
            return 1, "must not need a new commit"
        return real_git_runner(args, cwd)
    t = task()
    t.allow_already_satisfied = True
    result = run(delivery_repo, executor=Writer(), slices=[t], git_runner=runner)
    assert result.completed == ["A"] and not commits, result.details


def test_executor_commit_is_reused_without_duplicate_collection_commit(delivery_repo):
    commits = []
    def commit(t, wd):
        checked_git(["add", "-A"], wd)
        checked_git(["commit", "-qm", "executor commit"], wd)
        commits.append(checked_git(["rev-parse", "HEAD"], wd).strip())
        return ExecutorResult(True, "")
    result = run(delivery_repo, executor=Writer(commit))
    assert result.completed == ["A"]
    assert result.details["A"].commit == commits[0]


@pytest.mark.parametrize("change", ["ref", "worktree"])
def test_restart_checks_refs_and_retains_later_worktree_edits(delivery_repo, change):
    class FailDone(Ledger):
        def save(self):
            if self.is_done("A"):
                raise OSError("stop after collection")
            super().save()
    ledger = FailDone(str(delivery_repo / ".cld-ledger.json"))
    ex = Writer()
    with pytest.raises(OSError):
        run(delivery_repo, executor=ex, ledger=ledger)
    record_path = next((delivery_repo / ".cld/A").glob("*/outcome.json"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if change == "ref":
        checked_git(["update-ref", record["collection"]["ref"], record["base"]], delivery_repo)
    else:
        (Path(ex.calls[0]) / "implementation.py").write_text("VALUE = 99\n")
    result = run(delivery_repo, executor=ex, ledger=Ledger.load(ledger.path))
    assert len(ex.calls) == 1 and Path(ex.calls[0]).exists()
    if change == "ref":
        assert result.failed == ["A"] and not result.completed
    else:
        # The previously tested commit is valid, but a new physical edit must
        # survive cleanup. Acceptance never incorporates that untested edit.
        assert result.completed == ["A"] and result.details["A"].cleanup_warning
        assert (Path(ex.calls[0]) / "implementation.py").read_text() == "VALUE = 99\n"
        assert checked_git(["show", f'{result.details["A"].commit}:implementation.py'], delivery_repo) == BODY
