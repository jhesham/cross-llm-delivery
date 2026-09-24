import contextlib
from pathlib import Path
import re

from cld.executors._capture import CaptureError, checked
from cld.locking import file_owner


@contextlib.contextmanager
def registry_owner(repo, runner):
    common = checked(runner, repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    with file_owner(Path(common).resolve() / "cld-worktrees.lock", wait_seconds=10):
        yield


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
    with registry_owner(repo_dir, runner) if root is not None else contextlib.nullcontext():
        rc, output = runner(add_args, repo_dir)
    if rc != 0:
        raise RuntimeError(f"worktree creation failed at {path}: {output}")
    
    try:
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
