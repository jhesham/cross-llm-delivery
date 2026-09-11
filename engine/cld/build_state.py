"""Schema-2 identity, explicit migration/reconciliation and artifact namespaces."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from cld.executors._capture import checked
from cld.ledger import LedgerEntry, StateError, DONE, now
from cld.recovery import atomic_write, task_fingerprint, recover_collected


def validate_build(build):
    if not isinstance(build, dict):
        raise ValueError("invalid build identity")
    for key in ("run_id", "repo", "ledger_path", "git_common_dir", "plan_hash", "initial_base", "created_at", "updated_at"):
        if not isinstance(build.get(key), str) or not build[key]:
            raise ValueError(f"missing build {key}")
    if not re.fullmatch(r"[0-9a-f]{32}", build["run_id"]):
        raise ValueError("invalid run ID")
    if not isinstance(build.get("slices"), dict):
        raise ValueError("invalid slice manifest")
    if not re.fullmatch(r"[0-9a-f]{64}", build["plan_hash"]) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", build["initial_base"]):
        raise ValueError("invalid plan/base digest")
    for sid, item in build["slices"].items():
        if (not isinstance(sid, str) or not isinstance(item, dict)
                or not isinstance(item.get("fingerprint"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", item["fingerprint"])
                or not isinstance(item.get("deps"), list)
                or not all(isinstance(dep, str) for dep in item["deps"])):
            raise ValueError("invalid slice manifest entry")


def run_directory(repo, run_id):
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise StateError("Invalid artifact run ID")
    root = Path(repo).resolve()
    path = root / ".cld" / "runs" / run_id
    if not path.resolve().is_relative_to(root):
        raise StateError("Artifact directory escapes repository")
    return path


def manifest(tasks):
    result = {}
    for task in tasks:
        if not task.id or task.id in result:
            raise StateError("Empty or duplicate task ID in build manifest")
        result[task.id] = dict(fingerprint=task_fingerprint(task), deps=list(task.deps))
    return result


def backup(ledger, label):
    # Exact source bytes; interrupted migration can safely be retried. No overwrite.
    path = Path(ledger.path + f".{label}-{uuid4().hex}.bak")
    atomic_write(path, ledger._expected)
    return str(path)


def validate_tasks(ledger, repo, tasks):
    if os.path.realpath(repo) != ledger.build["repo"]:
        raise StateError("Ledger belongs to another repository; use its original repo or a separate ledger")
    if manifest(tasks) != ledger.build["slices"]:
        raise StateError("Plan mismatch; use --reconcile-plan with the complete plan")
    for task in tasks:
        if ledger.build["slices"].get(task.id, {}).get("fingerprint") != task_fingerprint(task):
            raise StateError(f"Plan mismatch at {task.id}; use --reconcile-plan with the complete plan")
        entry = ledger.get(task.id)
        if entry and entry.status == "needs_repair" and any(h.get("migration") for h in entry.history):
            raise StateError(f"Legacy {task.id} needs reconciliation; inspect migration evidence before --reconcile-plan")


def bind_build(ledger, repo, tasks, runner, *, plan_path=None, plan_text=None,
               migrate=False, reconcile=False, new_build=False):
    if ledger.build is None and ledger.entries:
        # Schema-2 utility/simulation ledgers also lack production identity.
        # Their DONE entries are not a shortcut around legacy verification.
        ledger.legacy = True
    repo = os.path.realpath(repo)
    common = checked(runner, repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    base = checked(runner, repo, "rev-parse", "HEAD^{commit}").strip()
    slices = manifest(tasks)
    digest = hashlib.sha256(json.dumps(slices, sort_keys=True).encode()).hexdigest()
    source = hashlib.sha256(plan_text.encode("utf-8")).hexdigest() if plan_text is not None else None
    plan_path = str(Path(plan_path).resolve()) if plan_path is not None else None
    old = deepcopy(ledger.build)
    if old and (old["repo"] != repo or old["git_common_dir"] != os.path.realpath(common)):
        raise StateError("Repository identity mismatch; reconciliation cannot retarget an existing ledger")
    mismatch = bool(old and (old["plan_hash"] != digest or old.get("plan_path") != plan_path
                            or old.get("plan_source_hash") != source or old["initial_base"] != base))
    if mismatch and not (reconcile or new_build):
        raise StateError(f"Plan/base mismatch for {ledger.path}; inspect then use --reconcile-plan or --new-build")
    if ledger.legacy and not migrate:
        raise StateError(f"Legacy ledger retained; run --migrate-ledger with the original plan: {ledger.path}")
    if old and not mismatch and not (reconcile or new_build):
        publish_current(ledger)
        return
    previous_entries = deepcopy(ledger.entries)
    previous_legacy = ledger.legacy
    backup_path = backup(ledger, "legacy" if ledger.legacy else "reconcile") if ledger._expected is not None else None
    affected = set(slices) if new_build or (old and old["initial_base"] != base) else {
        sid for sid in set((old or {}).get("slices", {})) | set(slices)
        if (old or {}).get("slices", {}).get(sid) != slices.get(sid)}
    if reconcile:
        affected.update(sid for sid, entry in ledger.entries.items()
                        if any(h.get("migration") for h in entry.history) and entry.status == "needs_repair")
    while True:
        downstream = {sid for sid, item in slices.items() if set(item["deps"]) & affected}
        if downstream <= affected:
            break
        affected |= downstream
    run_id = uuid4().hex
    run_directory(repo, run_id).mkdir(parents=True, exist_ok=False)
    build = dict(run_id=run_id, repo=repo, ledger_path=ledger.path, git_common_dir=os.path.realpath(common),
                 plan_path=plan_path, plan_hash=digest, plan_source_hash=source,
                 initial_base=base, integrated_sha=None, integrated_ref=None,
                 slices=slices, created_at=now(), updated_at=now(),
                 previous_run=(old or {}).get("run_id"), backup=backup_path,
                 legacy_recovery=ledger.legacy, invalidated=sorted(affected) if old else [])
    entries = {}
    for task in tasks:
        entry = deepcopy(ledger.get(task.id)) or LedgerEntry(task.id)
        if old and task.id in affected:
            entry = LedgerEntry(task.id, history=[dict(reconciled_from=old["run_id"], outcome=asdict(entry))])
        if ledger.legacy and entry.status == DONE:
            # Reachability is evidence to preserve, not proof of acceptance/integration.
            ref = entry.commit or f"refs/heads/slice-{task.id}"
            rc, commit = runner(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], repo)
            evidence = dict(migration=True, prior_status=DONE, ref=ref,
                            reachable_commit=commit.strip() if rc == 0 else None)
            recovered = recover_collected(repo, ledger.path, task, runner)
            if recovered is not None:
                record, directory = recovered
                entry.commit, entry.collection = record["collection"]["commit"], record["collection"]
                entry.recovery_path, entry.worktree_path = directory, record["worktree"]
                evidence["verified_journal"] = directory
            else:
                entry.status = "needs_repair"
            entry.history.append(evidence)
        entry.fingerprint = slices[task.id]["fingerprint"]
        entry.updated_at = now()
        entries[task.id] = entry
    ledger.build, ledger._entries, ledger.legacy = build, entries, False
    try:
        ledger.save()
    except BaseException:
        ledger.build, ledger._entries, ledger.legacy = old, previous_entries, previous_legacy
        raise
    publish_current(ledger)


def publish_current(ledger):
    directory = run_directory(ledger.build["repo"], ledger.build["run_id"])
    directory.mkdir(parents=True, exist_ok=True)
    atomic_write(directory / "build.json", json.dumps(ledger.build, indent=2).encode("utf-8"))
    atomic_write(Path(ledger.build["repo"]) / ".cld/current-run.json",
                 json.dumps(dict(run_id=ledger.build["run_id"], ledger=ledger.path)).encode("utf-8"))
