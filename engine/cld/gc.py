"""Explicit, preview-first cleanup of CLD-managed Git worktrees.

Planning is pure: callers pass ledger-derived facts and receive one decision per
worktree. Only ``apply_gc`` mutates, and only through the identity-checked
``remove_worktree``. Recovery refs (``refs/cld/*``) and run evidence
(``.cld/runs``) are never touched: a new build does not authorize deleting
previous evidence.
"""
from dataclasses import dataclass
from pathlib import Path
import json
import os
import re

from cld.executors._capture import CaptureError, _is_noise
from cld.ledger import StateError
from cld.worktree import remove_worktree, validate_location

_BRANCH = re.compile(r"refs/heads/cld/([0-9a-f]{32})/([A-Za-z0-9_-]{1,40})/([0-9a-f]{32})")


@dataclass(frozen=True)
class ManagedWorktree:
    path: str
    branch: str
    run_id: str
    slug: str
    session_id: str


@dataclass(frozen=True)
class GcDecision:
    worktree: ManagedWorktree
    action: str  # "remove" | "keep"
    reason: str


def slug_for(slice_id: str) -> str:
    """Same leaf rule as cld.worktree.managed_location."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", slice_id)[:40] or "slice"


def list_managed_worktrees(repo_dir, root, git_runner) -> list[ManagedWorktree]:
    """Registered worktrees directly under root on a cld/<run>/<slug>/<session> branch."""
    rc, output = git_runner(["git", "worktree", "list", "--porcelain"], repo_dir)
    if rc != 0:
        raise CaptureError(f"git worktree list failed: {output[:500]}")
    root = Path(root).resolve()
    found = []
    for block in output.replace("\r\n", "\n").split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        path, match = fields.get("worktree"), _BRANCH.fullmatch(fields.get("branch", ""))
        if not path or not match:
            continue
        resolved = Path(path).resolve()
        if resolved.parent != root:
            continue
        run_id, slug, session_id = match.groups()
        found.append(ManagedWorktree(str(resolved), fields["branch"][len("refs/heads/"):],
                                     run_id, slug, session_id))
    return found


def worktree_dirty(path, git_runner) -> bool:
    """Tracked/untracked changes or ignored non-cache data; an unreadable status counts as dirty.

    Plain `git status --porcelain` omits ignored files, so an otherwise clean
    worktree holding ignored local data looked safe to force-remove (R05).
    """
    rc, output = git_runner(["git", "status", "--porcelain", "--ignored"], str(path))
    if rc != 0:
        return True
    for line in output.splitlines():
        if not line.strip():
            continue
        if line.startswith("!! ") and _is_noise(line[3:].strip().strip('"')):
            continue
        return True
    return False


def resolve_slice_id(repo_dir, worktree) -> str | None:
    """True slice ID from this session's recovery evidence; None when not provable (R01).

    The branch slug is sanitized and truncated, so distinct slice IDs can share
    it; only an outcome.json naming this session and this worktree path counts.
    """
    from cld.build_state import run_directory
    try:
        base = run_directory(repo_dir, worktree.run_id)
    except StateError:
        return None
    target = os.path.normcase(os.path.realpath(worktree.path))
    found = set()
    for record_path in base.glob(f"*/{worktree.session_id}/outcome.json"):
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if (isinstance(record, dict) and record.get("session_id") == worktree.session_id
                and isinstance(record.get("slice_id"), str) and isinstance(record.get("worktree"), str)
                and os.path.normcase(os.path.realpath(record["worktree"])) == target):
            found.add(record["slice_id"])
    return found.pop() if len(found) == 1 else None


def plan_gc(worktrees, *, run_id, slice_status, recorded_integration, integration_states,
            dirty, include_previous, slice_ids=None) -> list[GcDecision]:
    """Decide keep/remove per worktree. `slice_ids` maps worktree path -> proven slice ID."""
    slice_ids = slice_ids or {}
    decisions = []
    for wt in worktrees:
        state = integration_states.get(wt.session_id)
        if wt.path in dirty:
            action, reason = "keep", "uncommitted or ignored local data"
        elif wt.run_id != run_id:
            if not include_previous:
                action, reason = "keep", "earlier build; pass --include-previous to remove"
            elif wt.slug == "integration":
                if state in ("passed", "failed"):
                    action, reason = "remove", f"earlier build, integration {state}"
                else:
                    action, reason = "keep", f"earlier build, integration state {state or 'unknown'}"
            elif slice_ids.get(wt.path) is None:
                action, reason = "keep", "slice identity not provable from evidence"
            else:
                action, reason = "remove", "earlier build, no local data"
        elif wt.slug == "integration":
            if wt.session_id == recorded_integration:
                action, reason = "keep", "recorded integration"
            elif state == "passed":
                action, reason = "remove", "passed integration superseded by the recorded one"
            elif state == "failed" and recorded_integration is not None:
                action, reason = "remove", "failed integration; a passed integration is recorded"
            else:
                action, reason = "keep", f"integration state {state or 'unknown'}"
        else:
            sid = slice_ids.get(wt.path)
            if sid is None:
                action, reason = "keep", "slice identity not provable from evidence"
            elif slice_status.get(sid) == "integrated":
                action, reason = "remove", "slice integrated"
            else:
                action, reason = "keep", f"slice status {slice_status.get(sid) or 'unknown'}"
        decisions.append(GcDecision(wt, action, reason))
    return decisions


def apply_gc(repo_dir, decisions, *, root, git_runner, prune=True) -> list[dict]:
    """Remove only 'remove' decisions, each identity-checked; then prune stale registrations."""
    results = []
    for decision in decisions:
        if decision.action != "remove":
            continue
        path = decision.worktree.path
        try:
            validate_location(path, root)
            remove_worktree(repo_dir, path, runner=git_runner, root=root, branch=decision.worktree.branch)
            results.append({"path": path, "action": "removed"})
        except (CaptureError, RuntimeError, OSError) as exc:
            results.append({"path": path, "action": "failed", "error": str(exc)})
    if prune:
        git_runner(["git", "worktree", "prune"], repo_dir)
    return results


def _integration_state(repo_dir, worktree):
    """State recorded by the integration transaction whose id is this session (None if unknown)."""
    from cld.build_state import run_directory
    try:
        for path in (run_directory(repo_dir, worktree.run_id) / "integration").glob("*/outcome.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(record, dict) and record.get("id") == worktree.session_id:
                return record.get("state")
    except (OSError, ValueError, StateError):
        return None
    return None


def collect(repo_dir, root, git_runner, *, run_id, slice_status, recorded_integration,
            include_previous, apply, owner=None):
    """Decide (and optionally remove) each worktree under its slice's owner lock (R02).

    The lock is the repository-wide nonblocking lock delivery holds while a
    slice runs, so a held lock means an active owner and the worktree is kept.
    Eligibility (status, dirty state) is decided under that lock, immediately
    before removal. Earlier builds are not locked unless --include-previous.
    """
    from contextlib import nullcontext
    from cld.attempts import ActiveAttempt, slice_owner
    owner = owner or slice_owner
    decisions, results = [], []
    for wt in list_managed_worktrees(repo_dir, root, git_runner):
        candidate = wt.run_id == run_id or include_previous
        sid, lock, states = None, nullcontext(), {}
        if wt.slug == "integration":
            states = {wt.session_id: _integration_state(repo_dir, wt)}
        else:
            sid = resolve_slice_id(repo_dir, wt)
            if sid is not None and candidate:
                lock = owner(repo_dir, sid, git_runner)
        try:
            with lock:
                dirty = {wt.path} if candidate and worktree_dirty(wt.path, git_runner) else set()
                (decision,) = plan_gc([wt], run_id=run_id, slice_status=slice_status,
                                      recorded_integration=recorded_integration,
                                      integration_states=states, dirty=dirty,
                                      include_previous=include_previous, slice_ids={wt.path: sid})
                if apply and decision.action == "remove":
                    results += apply_gc(repo_dir, [decision], root=root, git_runner=git_runner, prune=False)
        except ActiveAttempt:
            decision = GcDecision(wt, "keep", "active owner holds this slice")
        decisions.append(decision)
    if apply:
        git_runner(["git", "worktree", "prune"], repo_dir)
    return decisions, results
