"""Verify a lead's retained-worktree repair without trusting a status toggle."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
from uuid import uuid4

from cld.attempts import slice_owner
from cld.build_state import validate_tasks
from cld.candidate import CandidateVerifier
from cld.executors._capture import CaptureError, checked
from cld.integration import IntegrationResult, verified_base, dependency_block
from cld.judge import judge
from cld.ledger import StateError, DONE
from cld.recovery import RecoverySession, task_fingerprint
from cld.test_run import test_result
from cld.worktree import managed_location, verify_worktree, worktree


def verify_repair(slices, ledger, sid, *, repo_dir, git_runner, test_runner, worktree_root=None):
    with ledger.writer(refresh=True):
        if ledger.build is None:
            raise StateError("Repair requires a bound build and its original plan")
        validate_tasks(ledger, repo_dir, slices)
        task = next((s for s in slices if s.id == sid), None)
        entry = ledger.get(sid)
        if task is None or entry is None:
            raise StateError(f"Unknown repair slice {sid}")
        if entry.status not in ("failed", "needs_repair"):
            raise StateError(f"Slice {sid} is {entry.status}; repair requires a retained failed attempt")
        base = verified_base(ledger, git_runner)
        blocked = dependency_block(task, ledger, git_runner, base)
        if blocked:
            raise StateError(blocked)
        if not entry.recovery_path:
            raise StateError("Repair has no retained attempt evidence")
        evidence = Path(entry.recovery_path).resolve()
        if not evidence.is_relative_to((Path(repo_dir).resolve() / ".cld").resolve()):
            raise StateError("Repair evidence escapes repository")
        try:
            previous = json.loads((evidence / "outcome.json").read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise StateError(f"Cannot read repair evidence: {exc}") from exc
        if (previous.get("base") != base or previous.get("task_fingerprint") != task_fingerprint(task)
                or previous.get("run_id") != ledger.build["run_id"]
                or previous.get("repo") != ledger.build["repo"] or previous.get("ledger") != ledger.path
                or previous.get("worktree") != entry.worktree_path):
            raise StateError("Repair evidence/base changed; inspect it and retry the slice")
        with slice_owner(repo_dir, sid, git_runner):
            verify_worktree(repo_dir, entry.worktree_path, previous["worktree_root"], previous["branch"], git_runner)
            source = CandidateVerifier(git_runner, entry.worktree_path, task, base=base).capture()
            txn = uuid4().hex
            wt, root, branch = managed_location(repo_dir, worktree_root, ledger.build["run_id"], sid, txn, create_root=True)
            session = RecoverySession(repo_dir, wt, task, ledger.path, git_runner, session_id=txn, base=base,
                metadata=dict(run_id=ledger.build["run_id"], worktree_root=root, branch=branch,
                              owner_pid=os.getpid(), repair_of=entry.recovery_path))
            try:
                with worktree(repo_dir, branch, runner=git_runner, cleanup=False, path=wt, root=root, base=base):
                    verifier = CandidateVerifier(git_runner, wt, task, base=base)
                    def tests(where, tree):
                        result = test_result(test_runner(where, task.acceptance_test_path), candidate_id=tree)
                        session.tests(result)
                        return result
                    verifier.preflight(lambda where: tests(where, checked(git_runner, wt, "write-tree").strip()))
                    # Only this newly reserved worktree/index is updated.
                    checked(git_runner, wt, "read-tree", "--reset", "-u", source.tree)
                    candidate = verifier.capture()
                    if not candidate.files_changed and not (task.allow_already_satisfied and verifier.baseline_passed):
                        raise CaptureError("No-change repair requires explicit already-satisfied policy")
                    with verifier.snapshot(candidate) as frozen:
                        verdict = judge(list(candidate.files_changed), task.files,
                                        run_tests=lambda: tests(frozen, candidate.tree))
                    session.verdict(verdict)
                    if not verdict.passed:
                        raise CaptureError("Repair tests failed: " + "; ".join(verdict.failing_tests))
                    verifier.verify_unchanged(candidate)
                    session.save(delivery=dict(attempts=1, model="orchestrator", effort=None,
                        token_usage={}, final_rung="orchestrator", final=asdict(verdict)))
                    collected = session.collect(candidate)
                    if not collected.ok:
                        raise CaptureError(collected.error)
            except Exception as exc:
                session.save(state="failed", error=str(exc))
                old = deepcopy(entry)
                ledger.set(sid, status="needs_repair", recovery_path=str(session.directory), worktree_path=wt)
                entry.history.append(dict(repair_of=old.recovery_path, error=str(exc)))
                try:
                    ledger.save()
                except BaseException:
                    ledger.entries[sid] = old
                    raise
                return IntegrationResult(False, evidence=str(session.directory), error=f"{exc}; retained: {wt}")
            old = deepcopy(entry)
            ledger.set(sid, status=DONE, commit=collected.commit, intervened=True, final_rung="orchestrator",
                       collection={**asdict(collected), "base": base, "tests_fingerprint": candidate.tests_fingerprint},
                       recovery_path=str(session.directory), worktree_path=wt)
            entry.history.append(dict(repair_of=old.recovery_path, recovery_path=str(session.directory), commit=collected.commit))
            try:
                ledger.save()
            except BaseException:
                ledger.entries[sid] = old
                raise
            return IntegrationResult(True, (sid,), collected.commit, str(session.directory))
