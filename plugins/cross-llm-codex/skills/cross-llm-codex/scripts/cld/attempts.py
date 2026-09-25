"""Attempt ownership and conservative restart discovery (ledger migration is T05)."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

from cld.executors._capture import CaptureError, checked
from cld.recovery import recovery_records, task_fingerprint


class ActiveAttempt(CaptureError):
    pass


@contextmanager
def slice_owner(repo, sid, runner):
    """Nonblocking OS lock; process death releases it without PID/age heuristics.

    Keep the lock file: unlinking it would let waiters lock different inodes.
    The common Git directory also serializes linked checkouts of this repository.
    """
    common = Path(checked(runner, repo, "rev-parse", "--path-format=absolute",
                          "--git-common-dir").strip()).resolve()
    directory = common / "cld-locks"
    directory.mkdir(exist_ok=True)
    path = directory / (hashlib.sha256(sid.encode()).hexdigest() + ".lock")
    if not path.resolve().is_relative_to(common):
        raise CaptureError("Owner lock escapes Git directory")
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ActiveAttempt(f"Slice {sid} has an active owner; retry after it exits") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def previous_attempt(repo, ledger, task, runner, *, run_id=None, include_legacy=False):
    """Called only with ownership. Never checkout/reset a prior candidate.

    Resume uses a fresh base with pointers to preserved work, even if a worktree
    or recovery ref was removed. An unjournaled legacy branch is read-only input.
    """
    records = []
    for path in recovery_records(repo, task.id, run_id, include_legacy):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CaptureError(f"Cannot read recovery record {path}: {exc}") from exc
        if (record.get("repo") == os.path.realpath(repo)
                and record.get("ledger") == os.path.realpath(ledger)
                and record.get("task_fingerprint") == task_fingerprint(task)
                and record.get("state") != "collected"):
            records.append((path.stat().st_mtime_ns, path, record))
    if records:
        _, path, record = max(records, key=lambda item: (item[0], str(item[1])))
        ref = record.get("recovery_ref") or record.get("branch")
        available = bool(ref and runner(["git", "rev-parse", "--verify", ref], repo)[0] == 0)
        return dict(session_id=record.get("session_id"), state=record.get("state"),
                    owner="stale", worktree=record.get("worktree"),
                    worktree_exists=Path(record.get("worktree", "")).is_dir(),
                    ref=ref, ref_exists=available, evidence=str(path.parent),
                    diagnostics=str(record.get("error", "Previous attempt did not complete acceptance"))[:2000])
    legacy = f"refs/heads/slice-{task.id}"
    rc, _ = runner(["git", "show-ref", "--verify", "--quiet", legacy], repo)
    if rc == 0:
        return dict(ref=legacy, ref_exists=True, owner="unknown-legacy",
                    diagnostics="Legacy candidate retained; inspect before reusing its changes")
    if rc != 1:
        raise CaptureError(f"Cannot inspect legacy ref {legacy}")
    return None


def recovery_feedback(previous):
    if not previous:
        return None
    # Untrusted diagnostics are context, not permission to alter protected inputs.
    return ("Retry policy: fresh-base; previous candidate remains preserved. "
            "Inspect useful prior work and implement only this task's allowed changes.\n"
            + json.dumps(previous, ensure_ascii=True))[:6000]
