import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from cld.dag import parallel_batches
from cld.executors.base import SliceTask
from cld.judge import JudgeResult
from cld.ledger import Ledger, DONE, FAILED, IN_PROGRESS
from cld.telemetry import emit
from cld.worktree import worktree


def _save_failed_diff(git_runner, wt_path: str, repo_dir: str, slice_id: str) -> None:
    """Non-destructive safeguard (BUG B-3): before a worktree is force-removed for a
    slice that was NOT accepted, persist the executor's (uncommitted) diff to
    `<repo>/.cld/<slice_id>/<slice_id>.patch`. Without this, a judge rejection (or a
    judge that simply can't import the test) silently deletes correct executor code
    along with the worktree. Best-effort: never raises, never blocks the build.
    Recover with `git apply .cld/<slice_id>/<slice_id>.patch`.
    """
    try:
        git_runner(["git", "add", "-A"], wt_path)
        _, diff = git_runner(["git", "diff", "--cached", "HEAD"], wt_path)
        if diff and diff.strip():
            d = os.path.join(os.path.abspath(repo_dir), ".cld", slice_id)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"{slice_id}.patch"), "w", encoding="utf-8") as f:
                f.write(diff)
    except Exception:
        pass


def _save_judge_output(repo_dir: str, slice_id: str, deliver_res) -> None:
    """Diagnostic (concurrency report): persist the RAW judge (pytest) output for every
    attempt to `<repo>/.cld/<slice_id>/judge-output.txt`, on pass AND fail. Without this
    a judge false-negative is undiagnosable after the run — `detail.json` only records the
    parsed verdict, not what pytest actually printed. Best-effort; never raises.
    """
    try:
        history = list(getattr(deliver_res, "history", []) or [])
        if not history:
            return
        chunks = []
        for i, jr in enumerate(history, 1):
            chunks.append(
                f"----- attempt {i}  (passed={getattr(jr, 'passed', None)}, "
                f"tests_passed={getattr(jr, 'tests_passed', '?')}, "
                f"tests_failed={getattr(jr, 'tests_failed', '?')}) -----\n"
                f"{getattr(jr, 'raw_output', '') or ''}"
            )
        d = os.path.join(os.path.abspath(repo_dir), ".cld", slice_id)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "judge-output.txt"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(chunks))
    except Exception:
        pass

def _count_diff_lines(diff: str | None) -> int:
    """Count added/removed content lines in a unified diff (excludes +++/--- headers)."""
    return sum(
        1 for ln in (diff or "").splitlines()
        if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))
    )


def _effort_of(spec: str | None) -> str | None:
    """The @<effort> suffix of a resolved executor spec, or None if absent."""
    if spec and "@" in spec:
        eff = spec.rsplit("@", 1)[1].strip()
        return eff or None
    return None


def next_pending_layer(slices: list[SliceTask], ledger: Ledger) -> tuple[int, list[str], int] | None:
    deps = {s.id: list(s.deps) for s in slices}
    layers = parallel_batches(deps)
    for idx, layer in enumerate(layers):
        pending = [sid for sid in sorted(layer) if not ledger.is_done(sid)]
        if pending:
            return (idx, pending, len(layers))
    return None


@dataclass
class DeliverResult:
    accepted: bool
    attempts: int
    final: JudgeResult | None
    history: list[JudgeResult] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    diff_lines: int = 0
    model: str | None = None
    effort: str | None = None
    token_usage: dict = field(default_factory=dict)
    final_rung: str | None = None
    needs_repair: bool = False

def deliver_slice(
    task: SliceTask,
    *,
    executor: Any,
    judge_fn: Callable,
    max_retries: int = 2,
    workdir: str | None = None,
    model: str = "gemini-3.1-pro-preview",
    test_runner: Callable[[str], str] | None = None,
    source: str | None = None,
    rung: str | None = None,
) -> DeliverResult:
    # workdir defaults to task.id (prior behavior); callers wiring real worktrees
    # pass the worktree path so the executor operates in an isolated directory.
    effective_workdir = workdir if workdir is not None else task.id
    history = []
    final_judge_result = None
    total_attempts = max_retries + 1
    feedback = None  # set after a failed attempt, fed to the next dispatch

    for attempt in range(1, total_attempts + 1):
        # Telemetry: one dispatch_start per attempt (best-effort, never raises).
        emit("dispatch_start", slice_id=task.id, model=model, attempt=attempt,
             rung=rung, source=source)
        _t0 = time.monotonic()
        # Pass judge feedback into the retry so the executor can self-correct.
        # Executors that don't accept a `feedback` kwarg (legacy) keep working.
        if feedback is None:
            result = executor.run(task, effective_workdir)
        else:
            try:
                result = executor.run(task, effective_workdir, feedback=feedback)
            except TypeError:
                result = executor.run(task, effective_workdir)
        _tok = getattr(result, "token_usage", {}) or {}
        emit("dispatch_end", slice_id=task.id, model=model,
             rc=0 if getattr(result, "ok", True) else 1,
             tokens=_tok, cost=_tok.get("cost"),
             ms=int((time.monotonic() - _t0) * 1000))

        # The judge runs the REAL acceptance tests in the worktree when a
        # `test_runner` is supplied (the trustworthy path — never trust the
        # executor's self-reported stdout). Falls back to the executor's raw_log
        # only when no real runner is wired (legacy/unit-test path).
        #
        # The runner is given the slice's `acceptance_test_path` so it can scope
        # pytest to JUST that test, NOT the whole repo suite (Bug B: running the
        # whole suite billed a paid LLM if the target repo's tests call one, and a
        # hang anywhere froze the build). New runners take (workdir, path); legacy
        # one-arg runners (workdir) keep working via the TypeError fallback.
        if test_runner is not None:
            def run_tests():
                try:
                    return test_runner(effective_workdir, task.acceptance_test_path)
                except TypeError:
                    return test_runner(effective_workdir)
        else:
            run_tests = lambda: result.raw_log  # noqa: E731
        judge_result = judge_fn(
            files_changed=result.files_changed,
            allowed=task.files,
            run_tests=run_tests,
        )

        history.append(judge_result)
        final_judge_result = judge_result

        _verdict_failing = getattr(judge_result, "failing_tests", []) or []
        emit("judge_verdict", slice_id=task.id, passed=judge_result.passed,
             reason=("; ".join(_verdict_failing) if _verdict_failing else ""),
             attempt=attempt)

        if judge_result.passed:
            return DeliverResult(
                accepted=True,
                attempts=attempt,
                final=final_judge_result,
                history=history,
                files_changed=list(result.files_changed or []),
                diff_lines=_count_diff_lines(result.diff),
                model=model,
                effort=_effort_of(model),
                token_usage=getattr(result, "token_usage", {}) or {},
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

        if attempt < total_attempts:
            emit("retry", slice_id=task.id, attempt=attempt + 1,
                 reason=("; ".join(failing) if failing else ""))

    return DeliverResult(
        accepted=False,
        attempts=total_attempts,
        final=final_judge_result,
        history=history,
        files_changed=list(result.files_changed or []),
        diff_lines=_count_diff_lines(result.diff),
        model=model,
        effort=_effort_of(model),
        token_usage=getattr(result, "token_usage", {}) or {},
    )


@dataclass
class SliceDetail:
    slice_id: str
    status: str            # "completed" | "failed" | "skipped" | "deferred"
    files_changed: list[str] = field(default_factory=list)
    attempts: int = 0
    diff_lines: int = 0    # count of added/removed lines in the diff (for the summary)
    failing_tests: list[str] = field(default_factory=list)


@dataclass
class PlanResult:
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    needs_repair: list[str] = field(default_factory=list)
    details: dict[str, "SliceDetail"] = field(default_factory=dict)


def run_plan(
    slices: list[SliceTask],
    ledger: Ledger,
    *,
    executor: Any,
    judge_fn: Callable,
    max_retries: int = 2,
    test_runner: Callable[[str], str] | None = None,
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
            max_retries=max_retries,
            test_runner=test_runner,
        )
        
        if deliver_res.accepted:
            ledger.set(task.id, status=DONE, attempts=deliver_res.attempts,
                       model=deliver_res.model, token_usage=deliver_res.token_usage)
            result.completed.append(task.id)
        else:
            ledger.set(task.id, status=FAILED, attempts=deliver_res.attempts,
                       model=deliver_res.model, token_usage=deliver_res.token_usage)
            result.failed.append(task.id)

        ledger.save()

    return result


def run_plan_parallel(
    slices: list[SliceTask],
    ledger: Ledger,
    *,
    executor: Any = None,
    executor_factory: Callable[[str], Any] | None = None,
    default_spec: str = "gemini",
    judge_fn: Callable,
    max_retries: int = 2,
    max_workers: int = 4,
    quota_check: Callable[[], int] | None = None,
    quota_threshold: int = 95,
    repo_dir: str | None = None,
    git_runner: Callable[[list[str], str], tuple[int, str]] | None = None,
    test_runner: Callable[[str], str] | None = None,
    rung_planner: Callable | None = None,
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

    def _resolve_spec(task):
        # Resolution order: explicit tag wins, then the build default (pick-once-stick).
        if task.executor:                         # explicit tag wins
            return task.executor
        return default_spec                       # pick-once-stick (S1b fix)

    def _executor_for(task):
        # Per-slice executor: build from the resolved spec when a factory is
        # provided; else fall back to the single legacy executor. Returns the
        # resolved spec too so callers can record per-slice model in the ledger.
        spec = _resolve_spec(task)
        if executor_factory is not None:
            return executor_factory(spec), spec
        return executor, spec

    by_id = {s.id: s for s in slices}
    deps = {s.id: list(s.deps) for s in slices}
    ledger_lock = threading.Lock()

    def _run_one(task: SliceTask):
        """Deliver a slice, isolated in its own worktree when repo_dir is set.

        Collect step: when the slice is accepted, COMMIT its work inside the worktree
        before the context manager removes the worktree dir — otherwise
        `git worktree remove --force` discards the executor's uncommitted files (the
        original "code lost" bug). The commit lands on branch `slice-<id>`, which the
        caller can later merge.

        When rung_planner is provided, walk the rungs in order: first acceptance wins;
        if all rungs fail, return with needs_repair=True and final_rung="orchestrator".
        """
        if rung_planner is None:
            # UNCHANGED existing body — single _executor_for dispatch with max_retries
            slice_executor, resolved_spec = _executor_for(task)
            _src = "tag" if task.executor else "default"
            if repo_dir is not None and git_runner is not None:
                with worktree(repo_dir, f"slice-{task.id}", runner=git_runner) as wt_path:
                    res = deliver_slice(
                        task, executor=slice_executor, judge_fn=judge_fn,
                        max_retries=max_retries, workdir=wt_path,
                        test_runner=test_runner, model=resolved_spec,
                        source=_src, rung="workhorse",
                    )
                    _save_judge_output(repo_dir, task.id, res)
                    if res.accepted:
                        git_runner(["git", "add", "-A"], wt_path)
                        git_runner(
                            ["git", "commit", "-m", f"slice {task.id}: accepted by cld"],
                            wt_path,
                        )
                    else:
                        _save_failed_diff(git_runner, wt_path, repo_dir, task.id)
                    return res
            return deliver_slice(
                task, executor=slice_executor, judge_fn=judge_fn, max_retries=max_retries,
                test_runner=test_runner, model=resolved_spec,
                source=_src, rung="workhorse",
            )

        # Escalation ladder: walk each rung, first acceptance wins.
        rungs = rung_planner(task) or [("workhorse", _resolve_spec(task), max_retries)]
        last = None
        for _i, (rung_name, spec, budget) in enumerate(rungs):
            if _i > 0:
                emit("escalate", slice_id=task.id,
                     from_rung=rungs[_i - 1][0], to_rung=rung_name)
            _src = "tag" if task.executor else ("escalated" if _i > 0 else "default")
            ex = executor_factory(spec) if executor_factory is not None else executor
            if repo_dir is not None and git_runner is not None:
                with worktree(repo_dir, f"slice-{task.id}", runner=git_runner) as wt:
                    res = deliver_slice(task, executor=ex, judge_fn=judge_fn,
                                        max_retries=max(budget - 1, 0), workdir=wt,
                                        test_runner=test_runner, model=spec,
                                        source=_src, rung=rung_name)
                    _save_judge_output(repo_dir, task.id, res)
                    if res.accepted:
                        git_runner(["git", "add", "-A"], wt)
                        git_runner(["git", "commit", "-m", f"slice {task.id}: accepted by cld"], wt)
                    else:
                        _save_failed_diff(git_runner, wt, repo_dir, task.id)
            else:
                res = deliver_slice(task, executor=ex, judge_fn=judge_fn,
                                    max_retries=max(budget - 1, 0), test_runner=test_runner, model=spec,
                                    source=_src, rung=rung_name)
            last = res
            if res.accepted:
                res.final_rung = rung_name
                return res
        # All cheap rungs failed -> handoff for repair
        emit("needs_repair", slice_id=task.id)
        last.final_rung = "orchestrator"
        last.needs_repair = True
        return last

    def _process(task: SliceTask) -> None:
        # Quota gate (checked per slice so a window can fill mid-run).
        if quota_check is not None and quota_check() >= quota_threshold:
            with ledger_lock:
                result.deferred.append(task.id)
                result.details[task.id] = SliceDetail(slice_id=task.id, status="deferred")
            return

        with ledger_lock:
            ledger.set(task.id, status=IN_PROGRESS)
            ledger.save()
        emit("slice_start", slice_id=task.id)

        try:
            deliver_res = _run_one(task)
        except Exception as exc:
            # A build-time error (e.g. unknown executor spec) must FAIL only this
            # slice — record it FAILED and let the rest of the build continue.
            with ledger_lock:
                ledger.set(task.id, status=FAILED, attempts=0)
                result.failed.append(task.id)
                result.details[task.id] = SliceDetail(
                    slice_id=task.id, status="failed",
                    files_changed=[],
                    attempts=0,
                    diff_lines=0,
                    failing_tests=[f"executor error: {exc}"],
                )
                ledger.save()
            emit("slice_done", slice_id=task.id, status="failed")
            return

        with ledger_lock:
            failing = list(getattr(deliver_res.final, "failing_tests", []) or []) \
                if deliver_res.final is not None else []
            if deliver_res.needs_repair:
                ledger.set(task.id, status="needs_repair", attempts=deliver_res.attempts,
                           model=deliver_res.model, effort=deliver_res.effort,
                           token_usage=deliver_res.token_usage,
                           complexity=task.complexity, final_rung="orchestrator",
                           chosen_by=("you" if task.executor else "rec"))
                result.needs_repair.append(task.id)
                status = "needs_repair"
            elif deliver_res.accepted:
                ledger.set(task.id, status=DONE, attempts=deliver_res.attempts,
                           model=deliver_res.model, effort=deliver_res.effort,
                           token_usage=deliver_res.token_usage,
                           complexity=task.complexity, final_rung=deliver_res.final_rung,
                           chosen_by=("you" if task.executor else "rec"))
                result.completed.append(task.id)
                status = "completed"
            else:
                ledger.set(task.id, status=FAILED, attempts=deliver_res.attempts,
                           model=deliver_res.model, effort=deliver_res.effort,
                           token_usage=deliver_res.token_usage)
                result.failed.append(task.id)
                status = "failed"
            result.details[task.id] = SliceDetail(
                slice_id=task.id, status=status,
                files_changed=list(deliver_res.files_changed or []),
                attempts=deliver_res.attempts,
                diff_lines=deliver_res.diff_lines,
                failing_tests=failing,
            )
            ledger.save()
            emit("slice_done", slice_id=task.id, status=status)

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
