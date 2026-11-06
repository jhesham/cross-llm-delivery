import contextlib
from pathlib import Path
import re

from cld.executors._capture import CaptureError, checked
from cld.locking import file_owner
from cld.process import _scope
from cld._windows_workspace import prepare_windows_workspace


# Parallel workers queue here while Git adds or removes a worktree, which can take
# well over ten seconds per checkout on a loaded machine. The OS releases the lock
# when its owner exits, so a long wait never hangs on a dead process.
REGISTRY_WAIT_SECONDS = 300


@contextlib.contextmanager
def registry_owner(repo, runner, *, cancellable=False):
    """Own the worktree registry. Creation is *cancellable*: a cancelled build stops
    waiting and creates nothing. Removal always finishes so cleanup is not stranded."""
    common = checked(runner, repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    cancel = _scope.get().get("cancel") if cancellable else None
    with file_owner(Path(common).resolve() / "cld-worktrees.lock", wait_seconds=REGISTRY_WAIT_SECONDS,
                    cancel=cancel):
        yield


def repository_refs(repo, runner) -> frozenset:
    """Every ref name in *repo*: durable evidence of which sessions created anything.

    Git skips a ref it cannot read with only a warning and exit 0, so any stderr text,
    or any line that is not a ref (a runner that merges stderr), makes the listing
    incomplete: raise, and callers treat the evidence as inconclusive.
    """
    output = checked(runner, repo, "for-each-ref", "--format=%(refname)")
    lines = output.splitlines()
    stderr = getattr(output, "stderr", "") or ""
    if stderr.strip() or any(not line.startswith("refs/") for line in lines):
        raise CaptureError("Git could not list every ref: " + (stderr.strip() or output)[:300])
    return frozenset(lines)


def managed_location(repo, root, run_id, sid, session_id, *, create_root=False):
    """Canonical configured root; generated leaf names never contain path syntax."""
    if not all(re.fullmatch(r"[0-9a-f]{32}", value) for value in (run_id, session_id)):
        raise CaptureError("Invalid run/session identity")
    repo = Path(repo).resolve()
    root = Path(root) if root is not None else repo / ".cld" / "worktrees"
    if not root.is_absolute():
        root = repo / root
    root = root.resolve()
    if root == repo or repo.is_relative_to(root):
        raise CaptureError("Worktree root must not be the repository or its ancestor")
    if create_root:
        # Stabilize the parent before resolving a missing leaf. On Windows,
        # realpath of a missing leaf can transiently differ while another
        # worker creates its ancestors. No dispatch/worktree creation yet.
        root.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", sid)[:40] or "slice"
    branch = f"cld/{run_id}/{slug}/{session_id}"
    path = root / f"{slug}-{run_id[:8]}-{session_id}"
    validate_location(path, root)
    return str(path), str(root), branch


def validate_location(path, root):
    path, root = Path(path), Path(root)
    # Detect a replaced root/leaf junction as well as lexical traversal.
    if not root.is_absolute() or root.resolve() != root:
        raise CaptureError(f"Worktree root changed: {root}")
    if not path.is_absolute() or path.resolve() != path or path.parent != root:
        raise CaptureError(f"Worktree path escapes recorded root: {path} (resolved: {path.resolve()})")

@contextlib.contextmanager
def worktree(repo_dir: str, branch: str, *, runner, cleanup: bool = True,
             path: str | None = None, root: str | None = None, base: str = "HEAD"):
    # Resolve repo_dir to an ABSOLUTE path first, so the worktree lands as a clean
    # SIBLING (`<abs-repo>-wt-<branch>`). Without this, `--repo .` produced a
    # malformed `.-wt-<branch>` dir INSIDE the repo (Bug A).
    repo_abs = str(Path(repo_dir).resolve())
    if path is None:
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", branch) or branch.startswith("-"):
            raise CaptureError("Legacy worktree branch must be a single safe component")
        path = f"{repo_abs}-wt-{branch}"
        validate_location(path, str(Path(repo_abs).parent))
    elif root is None:
        raise CaptureError("An explicit worktree path requires a recorded root")
    if root is not None:
        validate_location(path, root)
        Path(root).mkdir(parents=True, exist_ok=True)
        validate_location(path, root)
        if Path(path).exists():
            raise CaptureError(f"Reserved worktree path already exists: {path}")
    add_args = ["git", "worktree", "add", "-b", branch, path, base]
    with registry_owner(repo_dir, runner, cancellable=True) if root is not None else contextlib.nullcontext():
        rc, output = runner(add_args, repo_dir)
    if rc != 0:
        raise RuntimeError(f"worktree creation failed at {path}: {output}")

    try:
        prepare_windows_workspace(Path(path), parent=Path(path).parent)
        yield path
    except BaseException as exc:
        exc.add_note(f"Worktree retained at {path}")
        raise
    else:
        if cleanup:
            remove_worktree(repo_dir, path, runner=runner, root=root, branch=branch if root else None)


def verify_worktree(repo_dir, path, root, branch, runner):
    validate_location(path, root)
    if checked(runner, path, "symbolic-ref", "HEAD").strip() != f"refs/heads/{branch}":
        raise CaptureError(f"Worktree branch changed; retained at {path}")
    common = checked(runner, path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    expected = checked(runner, repo_dir, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    if Path(common).resolve() != Path(expected).resolve():
        raise CaptureError(f"Worktree belongs to another repository: {path}")


def remove_worktree(repo_dir: str, path: str, *, runner, root=None, branch=None):
    if root is not None:
        verify_worktree(repo_dir, path, root, branch, runner)
    else:
        repo = Path(repo_dir).resolve()
        validate_location(path, str(repo.parent))
        if not Path(path).name.startswith(repo.name + "-wt-"):
            raise CaptureError(f"Unrecognized legacy worktree path: {path}")
    with registry_owner(repo_dir, runner) if root is not None else contextlib.nullcontext():
        rc, output = runner(["git", "worktree", "remove", "--force", path], repo_dir)
    if rc != 0:
        raise RuntimeError(f"Cleanup failed; worktree retained at {path}: {output}")
