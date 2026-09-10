import contextlib
import os

@contextlib.contextmanager
def worktree(repo_dir: str, branch: str, *, runner, cleanup: bool = True):
    # Resolve repo_dir to an ABSOLUTE path first, so the worktree lands as a clean
    # SIBLING (`<abs-repo>-wt-<branch>`). Without this, `--repo .` produced a
    # malformed `.-wt-<branch>` dir INSIDE the repo (Bug A).
    repo_abs = os.path.abspath(repo_dir)
    path = f"{repo_abs}-wt-{branch}"
    add_args = ["git", "worktree", "add", "-b", branch, path, "HEAD"]
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
            remove_worktree(repo_dir, path, runner=runner)


def remove_worktree(repo_dir: str, path: str, *, runner):
    rc, output = runner(["git", "worktree", "remove", "--force", path], repo_dir)
    if rc != 0:
        raise RuntimeError(f"Cleanup failed; worktree retained at {path}: {output}")
