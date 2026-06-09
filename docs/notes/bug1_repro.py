"""Repro harness for BUG 1 — Windows concurrent git worktree collision.

Creates N concurrent `git worktree add -b slice-<id>` from one repo, exactly as
run_plan_parallel does, and reports each command's rc + which worktrees actually
materialized. Run inside a fresh temp git repo.
"""
import os
import subprocess
import sys
import threading


def add(repo, sid, results):
    wt = f"{repo}-wt-slice-{sid}"
    p = subprocess.run(
        ["git", "worktree", "add", "-b", f"slice-{sid}", wt, "HEAD"],
        cwd=repo, capture_output=True, text=True,
    )
    results[sid] = (p.returncode, (p.stderr or p.stdout).strip()[:200])


def main():
    repo = os.getcwd()
    ids = sys.argv[1:] or ["S1", "S2", "S3"]
    results = {}
    threads = [threading.Thread(target=add, args=(repo, s, results)) for s in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for s in ids:
        rc, out = results[s]
        print(f"{s}: rc={rc}  {out}")
    print("--- git worktree list ---")
    print(subprocess.run(["git", "worktree", "list"], cwd=repo,
                         capture_output=True, text=True).stdout)


if __name__ == "__main__":
    main()
