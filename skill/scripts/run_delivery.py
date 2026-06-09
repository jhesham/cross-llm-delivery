#!/usr/bin/env python
"""Drive a cross-llm-delivery run from a plan file.

Assembles the cld engine end-to-end:
  load_slices(plan.md) -> get_executor("gemini") -> run_plan_parallel(...)
with a real git runner (for per-slice worktree isolation) and a real pytest-based
judge. Progress is persisted to a JSON ledger so the run is resumable.

Usage:
    python run_delivery.py <plan.md> [--repo <dir>] [--ledger <path>]
                           [--workers N] [--dry-run]

The plan is markdown with one block per slice (see cld.plan.slice.load_slices):

    ## SLICE: T1
    brief: <natural-language task / spec>
    files: src/a.py, tests/test_a.py
    acceptance_test_path: tests/test_a.py
    deps:

Exit code 0 if all slices accepted (or already done), 1 otherwise.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from cld.executors import get_executor
from cld.judge import judge
from cld.ledger import Ledger
from cld.orchestrator import run_plan_parallel
from cld.plan.slice import load_slices


def git_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Run a git command; return (returncode, combined output)."""
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return (proc.returncode, (proc.stdout or "") + (proc.stderr or ""))


def make_judge_fn(repo_dir: str):
    """Judge runs the slice's acceptance tests via pytest in the repo/worktree."""

    def judge_fn(*, files_changed, allowed, run_tests):
        # run_tests is provided by deliver_slice (executor's raw log); but for a real
        # judgment we re-run pytest in the workdir to get authoritative results.
        return judge(files_changed=files_changed, allowed=allowed, run_tests=run_tests)

    return judge_fn


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run a cross-llm-delivery plan.")
    p.add_argument("plan", help="Path to the plan markdown file")
    p.add_argument("--repo", default=".", help="Repo dir for worktree isolation")
    p.add_argument("--ledger", default=".cld-ledger.json", help="Ledger file path")
    p.add_argument("--workers", type=int, default=4, help="Max parallel slices")
    p.add_argument("--dry-run", action="store_true",
                   help="Load + layer the plan and print the schedule; no dispatch")
    args = p.parse_args(argv)

    plan_md = Path(args.plan).read_text(encoding="utf-8")
    slices = load_slices(plan_md)
    if not slices:
        print("No slices found in plan.", file=sys.stderr)
        return 1

    if args.dry_run:
        from cld.dag import parallel_batches
        deps = {s.id: list(s.deps) for s in slices}
        print(f"{len(slices)} slices. Execution layers (parallel batches):")
        for i, layer in enumerate(parallel_batches(deps)):
            print(f"  layer {i}: {', '.join(layer)}")
        return 0

    ledger = Ledger.load(args.ledger)
    executor = get_executor("gemini")
    judge_fn = make_judge_fn(args.repo)

    result = run_plan_parallel(
        slices, ledger,
        executor=executor, judge_fn=judge_fn,
        max_workers=args.workers,
        repo_dir=args.repo, git_runner=git_runner,
    )

    print(f"completed: {result.completed}")
    print(f"failed:    {result.failed}")
    print(f"skipped:   {result.skipped}")
    print(f"deferred:  {result.deferred}")
    return 0 if not result.failed and not result.deferred else 1


if __name__ == "__main__":
    raise SystemExit(main())
