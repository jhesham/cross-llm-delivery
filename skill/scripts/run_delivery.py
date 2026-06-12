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
import shlex
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
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return (proc.returncode, (proc.stdout or "") + (proc.stderr or ""))


def make_judge_fn(repo_dir: str):
    """Judge wrapper — delegates to cld.judge.judge with the run_tests deliver_slice
    supplies. The TRUSTWORTHY test output comes from `pytest_test_runner` (below),
    which deliver_slice invokes in the worktree; this just forwards it."""

    def judge_fn(*, files_changed, allowed, run_tests):
        return judge(files_changed=files_changed, allowed=allowed, run_tests=run_tests)

    return judge_fn


def pytest_test_runner(workdir: str, acceptance_test_path: str | None = None) -> str:
    """Run ONLY the slice's acceptance test in the worktree and return raw output.

    This is the authoritative judge signal (BUG1/Defect2 fix): the verdict comes
    from REALLY running the test in the worktree, never from the executor's
    self-reported stdout. Wired as deliver_slice's `test_runner`.

    BUG B fix: scope pytest to the slice's `acceptance_test_path`, NOT the whole
    repo suite. Running the whole suite (a) bills a paid LLM if the target repo's
    tests call one (e.g. the advisor's headless `claude -p`), and (b) lets a hang
    in an unrelated test freeze the entire build. A short timeout guards against a
    test that hangs anyway.

    TEST SELECTOR: `acceptance_test_path` may carry a pytest selector beyond a bare
    file — a `::node` id or a `-k "expr"` — to scope to JUST the slice's own tests
    inside a SHARED accumulating test file (where sibling tests are legitimately red
    until later slices land). We shlex.split it so the selector tokens reach pytest
    as separate args. Use forward slashes in paths (POSIX split); a bare path with
    no spaces/`::`/`-k` is unaffected.
    """
    target = shlex.split(acceptance_test_path) if acceptance_test_path else []
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *target, "-q"],
            cwd=workdir, capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return "1 failed in 600s (timeout — acceptance test did not complete)"
    return (proc.stdout or "") + (proc.stderr or "")


def parse_executor_spec(spec: str) -> tuple[str, dict]:
    """Parse an --executor value into (name, kwargs).

    Forms: "gemini" -> ("gemini", {}); "gemini:gemini-3-pro-preview" ->
    ("gemini", {"model": "gemini-3-pro-preview"}). The part before the first
    colon is the executor name; the remainder (if any) is the model. This is how
    the USER picks the LLM at invocation (not the orchestrator autonomously).
    """
    spec = (spec or "gemini").strip()
    if ":" in spec:
        name, model = spec.split(":", 1)
        name = name.strip() or "gemini"
        model = model.strip()
        return (name, {"model": model} if model else {})
    return (spec or "gemini", {})


def prompt_for_executor() -> str:
    """Interactive model picker (the CLI surface). Lists available OpenCode models,
    builds the recommended shortlist, and prompts the user to choose. The proven
    Gemini workhorse is always offered as the default. Returns an --executor spec.

    Degrades gracefully: if OpenCode isn't installed, `list_models` returns [] and
    the shortlist falls back to just the Gemini default."""
    from cld.executors.opencode import _default_runner
    from cld.models import list_models, pick_executor, recommend

    available = list_models(runner=_default_runner)
    recs = recommend(available_ids=available)
    if not recs:
        return "gemini"
    return pick_executor(recs)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run a cross-llm-delivery plan.")
    p.add_argument("plan", help="Path to the plan markdown file")
    p.add_argument("--repo", default=".", help="Repo dir for worktree isolation")
    p.add_argument("--ledger", default=".cld-ledger.json", help="Ledger file path")
    p.add_argument("--workers", type=int, default=4, help="Max parallel slices")
    p.add_argument("--executor", default=None,
                   help="Executor to use, e.g. 'gemini', 'gemini:<model-id>', or "
                        "'opencode:<provider/model>'. If omitted and stdin is a TTY, "
                        "an interactive picker prompts you to choose (default: the "
                        "proven Gemini workhorse). Non-interactive: defaults to gemini.")
    p.add_argument("--dry-run", action="store_true",
                   help="Load + layer the plan and print the schedule; no dispatch")
    p.add_argument("--step", action="store_true",
                   help="Run ONLY the next pending DAG layer, then exit (context-lean "
                        "orchestration). Re-invoke to advance. Exit codes: 0 layer all-passed, "
                        "2 some failed/deferred, 3 build complete.")
    args = p.parse_args(argv)

    plan_md = Path(args.plan).read_text(encoding="utf-8")
    slices = load_slices(plan_md)
    if not slices:
        print("No slices found in plan.", file=sys.stderr)
        return 1

    # Resolve the executor. If the user didn't pass --executor and we're attached to
    # an interactive terminal, show the model picker. Otherwise default to gemini so
    # automation / --step loops never block on a prompt.
    if args.executor is None:
        if not args.dry_run and sys.stdin.isatty():
            args.executor = prompt_for_executor()
        else:
            args.executor = "gemini"

    if args.dry_run:
        from cld.dag import parallel_batches
        deps = {s.id: list(s.deps) for s in slices}
        print(f"{len(slices)} slices. Execution layers (parallel batches):")
        for i, layer in enumerate(parallel_batches(deps)):
            print(f"  layer {i}: {', '.join(layer)}")
        return 0

    if args.step:
        from cld.orchestrator import next_pending_layer
        from cld.summary import classify_gate, summarize_layer, write_artifacts
        ledger = Ledger.load(args.ledger)
        sel = next_pending_layer(slices, ledger)
        if sel is None:
            print("BUILD COMPLETE — no pending layers.")
            return 3
        idx, layer_ids, total = sel
        layer_slices = [s for s in slices if s.id in layer_ids]
        exec_name, exec_kwargs = parse_executor_spec(args.executor)
        executor = get_executor(exec_name, **exec_kwargs)
        judge_fn = make_judge_fn(args.repo)
        result = run_plan_parallel(
            layer_slices, ledger,
            executor=executor, judge_fn=judge_fn,
            max_workers=args.workers,
            repo_dir=args.repo, git_runner=git_runner,
            test_runner=pytest_test_runner,
        )
        write_artifacts(result, repo_dir=args.repo)
        nxt = next_pending_layer(slices, ledger)
        next_layer = nxt[1] if nxt else []
        print(summarize_layer(result, layer_index=idx, total_layers=total,
                              next_layer=next_layer))
        return classify_gate(result, more_layers=bool(nxt))

    ledger = Ledger.load(args.ledger)
    exec_name, exec_kwargs = parse_executor_spec(args.executor)
    executor = get_executor(exec_name, **exec_kwargs)
    judge_fn = make_judge_fn(args.repo)

    result = run_plan_parallel(
        slices, ledger,
        executor=executor, judge_fn=judge_fn,
        max_workers=args.workers,
        repo_dir=args.repo, git_runner=git_runner,
        test_runner=pytest_test_runner,  # REAL pytest in the worktree = the judge signal
    )

    print(f"completed: {result.completed}")
    print(f"failed:    {result.failed}")
    print(f"skipped:   {result.skipped}")
    print(f"deferred:  {result.deferred}")
    return 0 if not result.failed and not result.deferred else 1


if __name__ == "__main__":
    raise SystemExit(main())
