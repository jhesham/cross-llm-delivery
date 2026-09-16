"""Build-owned, journaled integration. No operation checks out the user's HEAD."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from uuid import uuid4

from cld.build_state import run_directory, validate_tasks
from cld.candidate import CandidateVerifier
from cld.executors._capture import CaptureError, checked
from cld.executors.base import SliceTask
from cld.judge import judge
from cld.test_run import test_result
from cld.ledger import DONE, StateError
from cld.recovery import atomic_write, recover_collected
from cld.worktree import managed_location, worktree


@dataclass
class IntegrationResult:
    passed: bool
    integrated: tuple = ()
    commit: str | None = None
    evidence: str | None = None
    error: str | None = None


def pending_integration(ledger):
    return sorted(sid for sid, entry in ledger.entries.items() if entry.status == DONE)


def verified_base(ledger, runner):
    """Reject stale/tampered integration proof before it can become a dispatch base."""
    build = ledger.build
    sha = build.get("integrated_sha")
    if not sha:
        if any(e.status == "integrated" for e in ledger.entries.values()):
            raise StateError("Integrated entries have no verified build base")
        return build["initial_base"]
    proof = build.get("integration_proof", {})
    try:
        if not isinstance(proof.get("id"), str) or len(proof["id"]) != 32 or any(c not in "0123456789abcdef" for c in proof["id"]):
            raise StateError("Invalid integration transaction ID")
        expected = run_directory(build["repo"], build["run_id"]) / "integration" / proof["id"] / "outcome.json"
        if (not expected.resolve().is_relative_to(run_directory(build["repo"], build["run_id"]).resolve())
                or json.loads(expected.read_text(encoding="utf-8")) != proof
                or proof["state"] != "passed" or proof["commit"] != sha
                or proof["selector"] != build.get("integration_selector")
                or proof["ref"] != f'refs/cld/integration/{build["run_id"]}/{proof["id"]}'
                or build["integrated_ref"] != proof["ref"]
                or checked(runner, build["repo"], "rev-parse", proof["ref"]).strip() != sha):
            raise StateError("Integration proof does not match its recorded commit")
        checked(runner, build["repo"], "merge-base", "--is-ancestor", build["initial_base"], sha)
        for sid, commit in proof["all_commits"].items():
            entry = ledger.get(sid)
            if entry is None or entry.status != "integrated" or entry.commit != commit:
                raise StateError(f"Integration proof mismatch for {sid}")
            checked(runner, build["repo"], "merge-base", "--is-ancestor", commit, sha)
        if {sid for sid, e in ledger.entries.items() if e.status == "integrated"} != set(proof["all_commits"]):
            raise StateError("Integrated entries differ from the verified gate")
    except (KeyError, TypeError, AttributeError, ValueError, OSError, CaptureError) as exc:
        raise StateError(f"Invalid integration evidence: {exc}") from exc
    return sha


def dependency_block(task, ledger, runner, base):
    for dep in task.deps:
        entry = ledger.get(dep)
        if entry is None or entry.status != "integrated":
            return f"Dependency {dep} is {entry.status if entry else 'missing'}; verified integration required"
        rc, _ = runner(["git", "merge-base", "--is-ancestor", entry.commit, base], ledger.build["repo"])
        if rc != 0:
            return f"Dependency {dep} commit is absent from the verified integration base"
    return None


def configure_suite(slices, ledger, runner, selector, base):
    """Freeze the explicit selector before unattended dispatch or integration."""
    if not selector:
        raise StateError("Integration requires an explicit suite selector and test runner")
    configured = ledger.build.get("integration_selector")
    if configured is not None and configured != selector:
        raise StateError("Integration suite changed; use --new-build or --reconcile-plan")
    task = SliceTask("integration", "Verify the combined build",
                     sorted({f for s in slices for f in s.files}), selector,
                     protected_inputs=sorted({f for s in slices for f in s.protected_inputs}))
    CandidateVerifier(runner, ledger.build["repo"], task, base=base)
    if configured is None:
        ledger.build["integration_selector"] = selector
        try:
            ledger.save()
        except BaseException:
            ledger.build.pop("integration_selector", None)
            raise
    return task


def integrate(slices, ledger, *, repo_dir, git_runner, test_runner, selector,
              worktree_root=None, manual_ref=None):
    """Merge accepted commits in ID order, test a frozen tree, then publish atomically.

    Incomplete/failed transactions and all worktrees remain inspectable. A passed
    journal survives a failed ledger write and is re-tested without another merge
    on retry. An already published integration is a no-op.
    """
    with ledger.writer(refresh=True):
        if ledger.build is None:
            raise StateError("Bind the complete plan before integration")
        validate_tasks(ledger, repo_dir, slices)
        base = verified_base(ledger, git_runner)
        if test_runner is None:
            raise StateError("Integration requires an explicit suite selector and test runner")
        task = configure_suite(slices, ledger, git_runner, selector, base)
        pending = pending_integration(ledger)
        if not pending:
            return IntegrationResult(True, commit=ledger.build.get("integrated_sha"))
        tasks = {s.id: s for s in slices}
        pending = [sid for sid in pending if all(ledger.get(dep) and ledger.get(dep).status == "integrated"
                                                for dep in tasks[sid].deps)]
        if not pending:
            raise StateError("Accepted work is blocked by dependencies awaiting verified integration")
        commits = {}
        for sid in pending:
            entry = ledger.get(sid)
            # DONE/--mark-repaired alone is never proof of acceptance.
            recovered = recover_collected(repo_dir, ledger.path, tasks[sid], git_runner,
                run_id=ledger.build["run_id"], include_legacy=ledger.build.get("legacy_recovery", False),
                expected_base=entry.collection.get("base") or base,
                record_path=Path(entry.recovery_path) / "outcome.json" if entry.recovery_path else None)
            if recovered is None or recovered[0]["collection"]["commit"] != entry.commit:
                raise StateError(f"Accepted collection cannot be verified for {sid}")
            for dep in tasks[sid].deps:
                if ledger.get(dep) is None or ledger.get(dep).status != "integrated":
                    raise StateError(f"Cannot integrate {sid}: dependency {dep} is not integrated")
            commits[sid] = entry.commit
        root = run_directory(repo_dir, ledger.build["run_id"]) / "integration"
        if not root.resolve().is_relative_to(root.parent.resolve()):
            raise StateError("Integration artifact directory escapes the build run")
        root.mkdir(parents=True, exist_ok=True)
        manual = checked(git_runner, repo_dir, "rev-parse", "--verify", f"{manual_ref}^{{commit}}").strip() if manual_ref else None
        recovered = None
        for path in sorted(root.glob("*/outcome.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if (record.get("state") == "passed" and record.get("base") == base
                    and record.get("commits") == commits and record.get("selector") == selector
                    and record.get("manual_commit") == manual):
                recovered = record
                break
        txn = uuid4().hex
        directory = root / txn
        directory.mkdir()
        wt, wt_root, branch = managed_location(repo_dir, worktree_root, ledger.build["run_id"],
                                               "integration", txn, create_root=True)
        record = dict(id=txn, run_id=ledger.build["run_id"], base=base, commits=commits,
                      selector=selector, manual_commit=manual, worktree=wt, branch=branch,
                      state="reserved", all_commits={**ledger.build.get("integration_proof", {}).get("all_commits", {}), **commits})

        def save(**updates):
            record.update(json.loads(json.dumps(updates)))
            atomic_write(directory / "outcome.json", json.dumps(record, indent=2).encode("utf-8"))

        def tests(where, name):
            result = test_result(test_runner(where, selector), candidate_id=checked(git_runner, wt, "write-tree").strip())
            atomic_write(directory / name, result.output.encode("utf-8"))
            atomic_write(directory / (name + ".json"), json.dumps({**asdict(result), "log_path": str(directory / name)}).encode("utf-8"))
            return result

        save()
        try:
            with worktree(repo_dir, branch, runner=git_runner, cleanup=False, path=wt, root=wt_root, base=base):
                verifier = CandidateVerifier(git_runner, wt, task, base=base)
                verifier.preflight(lambda where: tests(where, "baseline.txt"))
                save(state="merging", baseline_passed=verifier.baseline_passed)
                if recovered:
                    if checked(git_runner, repo_dir, "rev-parse", recovered["ref"]).strip() != recovered["commit"]:
                        raise CaptureError("Recovered integration ref changed")
                    targets = [recovered["commit"]]
                else:
                    targets = [manual] if manual else list(commits.values())
                for commit in targets:
                    checked(git_runner, wt, "merge", "--no-edit", "--ff-only" if recovered or manual else "--no-ff", commit)
                head = checked(git_runner, wt, "rev-parse", "HEAD^{commit}").strip()
                for commit in commits.values():
                    checked(git_runner, wt, "merge-base", "--is-ancestor", commit, head)
                candidate = verifier.capture()
                if checked(git_runner, wt, "rev-parse", f"{head}^{{tree}}").strip() != candidate.tree:
                    raise CaptureError("Integration worktree differs from its merge commit")
                save(state="candidate", commit=head, candidate=asdict(candidate))
                with verifier.snapshot(candidate) as frozen:
                    verdict = judge(list(candidate.files_changed), task.files,
                                    run_tests=lambda: tests(frozen, "candidate.txt"))
                    if not verdict.passed:
                        kind = "layer regression" if verifier.baseline_passed else "baseline failure persists"
                        raise CaptureError(f"Integration {kind}: {'; '.join(verdict.failing_tests)}")
                verifier.verify_unchanged(candidate)
                ref = f'refs/cld/integration/{ledger.build["run_id"]}/{txn}'
                checked(git_runner, wt, "update-ref", ref, head, "0" * len(head))
                if checked(git_runner, wt, "rev-parse", ref).strip() != head:
                    raise CaptureError("Integration ref readback mismatch")
                save(state="passed", ref=ref)
        except Exception as exc:
            save(state="failed", error=str(exc))
            old_build = deepcopy(ledger.build)
            ledger.build["integration_failure"] = dict(error=str(exc), evidence=str(directory), worktree=wt)
            try:
                ledger.save()
            except BaseException:
                ledger.build = old_build
                raise
            return IntegrationResult(False, evidence=str(directory), error=f"{exc}; worktree retained at {wt}")
        # The journal and immutable ref precede publication. Roll back memory on
        # save failure so a retry cannot silently treat this gate as published.
        old_build, old_entries = deepcopy(ledger.build), deepcopy(ledger.entries)
        try:
            ledger.build.pop("integration_failure", None)
            ledger.build.update(integrated_sha=head, integrated_ref=ref, integration_proof=deepcopy(record))
            for sid in pending:
                ledger.set(sid, status="integrated")
            ledger.save()
        except BaseException:
            ledger.build, ledger._entries = old_build, old_entries
            raise
        return IntegrationResult(True, tuple(pending), head, str(directory))
