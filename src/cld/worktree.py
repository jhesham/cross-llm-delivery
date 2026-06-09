import contextlib

@contextlib.contextmanager
def worktree(repo_dir: str, branch: str, *, runner):
    path = f"{repo_dir}-wt-{branch}"
    add_args = ["git", "worktree", "add", "-b", branch, path, "HEAD"]
    rc, output = runner(add_args, repo_dir)
    if rc != 0:
        raise RuntimeError(output)
    
    try:
        yield path
    finally:
        remove_args = ["git", "worktree", "remove", "--force", path]
        runner(remove_args, repo_dir)
