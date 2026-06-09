import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from cld.dag import parallel_batches
from cld.executors.base import SliceTask
from cld.judge import JudgeResult
from cld.ledger import Ledger, DONE, FAILED, IN_PROGRESS
from cld.tracing import record_dispatch
from cld.worktree import worktree

@dataclass
class DeliverResult:
    accepted: bool
    attempts: int
    final: JudgeResult | None
    history: list[JudgeResult] = field(default_factory=list)

def deliver_slice(
    task: SliceTask,
    *,
    executor: Any,
    judge_fn: Callable,
    max_retries: int = 2,
    workdir: str | None = None,
    model: str = "gemini-3.1-pro-preview",
    tracer=None,
) -> DeliverResult:
    # workdir defaults to task.id (prior behavior); callers wiring real worktrees
    # pass the worktree path so the executor operates in an isolated directory.
    effective_workdir = workdir if workdir is not None else task.id
    history = []
    final_judge_result = None
    total_attempts = max_retries + 1
    feedback = None  # set after a failed attempt, fed to the next dispatch

    for attempt in range(1, total_attempts + 1):
        # Pass judge feedback into the retry so the executor can self-correct.
        # Executors that don't accept a `feedback` kwarg (legacy) keep working.
        if feedback is None:
            result = executor.run(task, effective_workdir)
        else:
            try:
                result = executor.run(task, effective_workdir, feedback=feedback)
            except TypeError:
                result = executor.run(task, effective_workdir)

        judge_result = judge_fn(
            files_changed=result.files_changed,
            allowed=task.files,
            run_tests=lambda: result.raw_log
        )

        history.append(judge_result)
        final_judge_result = judge_result

        # Observability: record one span per dispatch (best-effort, never raises).
        record_dispatch(
            slice_id=task.id,
            model=model,
            token_usage=getattr(result, "token_usage", {}) or {},
            accepted=judge_result.passed,
            attempts=attempt,
            diff_len=len(getattr(result, "diff", "") or ""),
            failing_tests=getattr(judge_result, "failing_tests", []) or [],
            tracer=tracer,
        )

        if judge_result.passed:
            return DeliverResult(
                accepted=True,
                attempts=attempt,
                final=final_judge_result,
                history=history
            )

        # Failed: build feedback for the next attempt from the judge result.
        failing = getattr(judge_result, "failing_tests", []) or []
        disallowed = getattr(judge_result, "disallowed_edits", []) or []
        parts = []
        if failing:
            parts.append("Failing tests: " + ", ".join(failing))
        if disallowed:
            parts.append("Edited files outside the allowed set: " + ", ".join(disallowed))
        feedback = (
            "Your previous attempt did not pass. "
            + " ".join(parts)
            + " Fix these and try again."
        ) if parts else "Your previous attempt did not pass. Fix the failures and try again."

    return DeliverResult(
        accepted=False,
        attempts=total_attempts,
        final=final_judge_result,
        history=history
    )


@dataclass
class PlanResult:
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)


def run_plan(
    slices: list[SliceTask],
    ledger: Ledger,
    *,
    executor: Any,
    judge_fn: Callable,
    max_retries: int = 2
) -> PlanResult:
    result = PlanResult()
    for task in slices:
        if ledger.is_done(task.id):
            result.skipped.append(task.id)
            continue
            
        ledger.set(task.id, status=IN_PROGRESS)
        ledger.save()
        
        deliver_res = deliver_slice(
            task,
            executor=executor,
            judge_fn=judge_fn,
            max_retries=max_retries
        )
        
        if deliver_res.accepted:
            ledger.set(task.id, status=DONE, attempts=deliver_res.attempts)
            result.completed.append(task.id)
        else:
            ledger.set(task.id, status=FAILED, attempts=deliver_res.attempts)
            result.failed.append(task.id)

        ledger.save()

    return result


def run_plan_parallel(
    slices: list[SliceTask],
    ledger: Ledger,
    *,
    executor: Any,
    judge_fn: Callable,
    max_retries: int = 2,
    max_workers: int = 4,
    quota_check: Callable[[], int] | None = None,
    quota_threshold: int = 95,
    repo_dir: str | None = None,
    git_runner: Callable[[list[str], str], tuple[int, str]] | None = None,
) -> PlanResult:
    """Run a plan with DAG-aware parallel fan-out.

    Slices are layered via `parallel_batches` (the DAG): all slices in a layer are
    independent and run concurrently in a thread pool; layers run in order so deps
    are satisfied before dependents start. Each slice is delivered via `deliver_slice`
    and its outcome persisted to the ledger (serialized by a lock, since Ledger is
    not thread-safe).

    Multi-agent isolation: if `repo_dir` (and `git_runner`) are provided, each slice
    runs inside its OWN git worktree (`worktree(repo_dir, "slice-<id>", ...)`) and the
    executor receives that worktree's path as its workdir — so concurrent Gemini agents
    never share a directory. Without `repo_dir`, the workdir falls back to `task.id`
    (the prior behavior; fine for fakes/tests and single-agent use).

    Quota-awareness: if `quota_check` is provided and returns a percentage >=
    `quota_threshold`, slices are NOT dispatched — they are recorded in
    `result.deferred` so a later run (after the quota window resets) picks them up.
    This protects the flat-rate executor's quota bucket during large fan-outs.
    """
    result = PlanResult()
    by_id = {s.id: s for s in slices}
    deps = {s.id: list(s.deps) for s in slices}
    ledger_lock = threading.Lock()

    def _run_one(task: SliceTask):
        """Deliver a slice, isolated in its own worktree when repo_dir is set."""
        if repo_dir is not None and git_runner is not None:
            with worktree(repo_dir, f"slice-{task.id}", runner=git_runner) as wt_path:
                return deliver_slice(
                    task, executor=executor, judge_fn=judge_fn,
                    max_retries=max_retries, workdir=wt_path,
                )
        return deliver_slice(
            task, executor=executor, judge_fn=judge_fn, max_retries=max_retries,
        )

    def _process(task: SliceTask) -> None:
        # Quota gate (checked per slice so a window can fill mid-run).
        if quota_check is not None and quota_check() >= quota_threshold:
            with ledger_lock:
                result.deferred.append(task.id)
            return

        with ledger_lock:
            ledger.set(task.id, status=IN_PROGRESS)
            ledger.save()

        deliver_res = _run_one(task)

        with ledger_lock:
            if deliver_res.accepted:
                ledger.set(task.id, status=DONE, attempts=deliver_res.attempts)
                result.completed.append(task.id)
            else:
                ledger.set(task.id, status=FAILED, attempts=deliver_res.attempts)
                result.failed.append(task.id)
            ledger.save()

    for layer in parallel_batches(deps):
        # A layer may include dep-only ids not in this plan — keep only real tasks
        # that aren't already done in the ledger.
        runnable = []
        for sid in layer:
            task = by_id.get(sid)
            if task is None:
                continue
            if ledger.is_done(sid):
                result.skipped.append(sid)
                continue
            runnable.append(task)

        if not runnable:
            continue

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(_process, runnable))

    return result
