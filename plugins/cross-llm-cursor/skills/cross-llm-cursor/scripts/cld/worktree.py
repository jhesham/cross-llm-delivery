import contextlib
import os

@contextlib.contextmanager
def worktree(repo_dir: str, branch: str, *, runner):
    # Resolve repo_dir to an ABSOLUTE path first, so the worktree lands as a clean
    # SIBLING (`<abs-repo>-wt-<branch>`). Without this, `--repo .` produced a
    # malformed `.-wt-<branch>` dir INSIDE the repo (Bug A).
    repo_abs = os.path.abspath(repo_dir)
    path = f"{repo_abs}-wt-{branch}"
    add_args = ["git", "worktree", "add", "-b", branch, path, "HEAD"]
    rc, output = runner(add_args, repo_dir)
    if rc != 0:
        raise RuntimeError(output)
    
    try:
        yield path
    finally:
        remove_args = ["git", "worktree", "remove", "--force", path]
        runner(remove_args, repo_dir)
