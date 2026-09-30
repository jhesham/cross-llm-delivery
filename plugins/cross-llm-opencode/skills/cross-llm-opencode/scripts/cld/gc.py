"""Explicit, preview-first cleanup of CLD-managed Git worktrees.

Planning is pure: callers pass ledger-derived facts and receive one decision per
worktree. Only ``apply_gc`` mutates, and only through the identity-checked
``remove_worktree``. Recovery refs (``refs/cld/*``) and run evidence
(``.cld/runs``) are never touched: a new build does not authorize deleting
previous evidence.
"""
from dataclasses import dataclass
from pathlib import Path
import re

from cld.executors._capture import CaptureError
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
    """True when a worktree has uncommitted changes; an unreadable status counts as dirty."""
    rc, output = git_runner(["git", "status", "--porcelain"], str(path))
    return rc != 0 or bool(output.strip())


def plan_gc(worktrees, *, run_id, slice_status, recorded_integration, integration_states,
            dirty, include_previous) -> list[GcDecision]:
    status_by_slug = {slug_for(sid): status for sid, status in slice_status.items()}
    decisions = []
    for wt in worktrees:
        if wt.run_id != run_id:
            if not include_previous:
                action, reason = "keep", "earlier build; pass --include-previous to remove"
            elif wt.path in dirty:
                action, reason = "keep", "earlier build with uncommitted changes"
            else:
                action, reason = "remove", "earlier build, no uncommitted changes"
        elif wt.slug == "integration":
            state = integration_states.get(wt.session_id)
            if wt.session_id == recorded_integration:
                action, reason = "keep", "recorded integration"
            elif state == "passed":
                action, reason = "remove", "passed integration superseded by the recorded one"
            elif state == "failed" and recorded_integration is not None:
                action, reason = "remove", "failed integration; a passed integration is recorded"
            else:
                action, reason = "keep", f"integration state {state or 'unknown'}"
        else:
            status = status_by_slug.get(wt.slug)
            if status == "integrated":
                action, reason = "remove", "slice integrated"
            else:
                action, reason = "keep", f"slice status {status or 'unknown'}"
        decisions.append(GcDecision(wt, action, reason))
    return decisions


def apply_gc(repo_dir, decisions, *, root, git_runner) -> list[dict]:
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
    git_runner(["git", "worktree", "prune"], repo_dir)
    return results
