import os
import inspect
from copy import deepcopy
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from cld.dag import parallel_batches
from cld.executors.base import ExecutorResult, SliceTask
from cld.candidate import Candidate, CandidateVerifier
from cld.executors._capture import CaptureError
from cld.judge import JudgeResult, judge, _extract_rc
from cld.ledger import Ledger, DONE, FAILED, IN_PROGRESS
from cld.telemetry import emit
from cld.worktree import worktree, remove_worktree
from cld.recovery import RecoverySession, recover_collected


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
    candidate: Candidate | None = None
    collection: dict = field(default_factory=dict)
    recovery_path: str | None = None
    worktree_path: str | None = None


def _accepts(fn, *args, **kwargs):
    """Adapt legacy injected signatures BEFORE calling; never retry a body error."""
    try:
        inspect.signature(fn).bind(*args, **kwargs)
    except TypeError:
        return False
    return True

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
    git_runner: Callable | None = None,
    simulation: bool = False,
    evidence: RecoverySession | None = None,
) -> DeliverResult:
    if git_runner is None and not simulation:
        raise CaptureError("Delivery requires git_runner; report-only test doubles must opt into simulation=True")
    if git_runner is not None and simulation:
        raise CaptureError("Simulation cannot be combined with a real Git boundary")
    # workdir defaults to task.id (prior behavior); callers wiring real worktrees
    # pass the worktree path so the executor operates in an isolated directory.
    effective_workdir = workdir if workdir is not None else task.id
    history = []
    final_judge_result = None
    total_attempts = max_retries + 1
    feedback = None  # set after a failed attempt, fed to the next dispatch
    verifier = None
    candidate = None
    files_changed, diff = [], ""
    acceptance_selector = task.acceptance_test_path

    def run_at(directory):
        if _accepts(test_runner, directory, acceptance_selector):
            output = test_runner(directory, acceptance_selector)
        else:
            output = test_runner(directory)
        if evidence is not None:
            evidence.tests(output)
        return output

    if git_runner is not None:
        if test_runner is None:
            raise CaptureError("Verified delivery requires an independent acceptance runner")
        verifier = CandidateVerifier(git_runner, effective_workdir, task)
        verifier.preflight(run_at)

    for attempt in range(1, total_attempts + 1):
        if evidence is not None:
            evidence.start_attempt(attempt)
        # Telemetry: one dispatch_start per attempt (best-effort, never raises).
        emit("dispatch_start", slice_id=task.id, model=model, attempt=attempt,
             rung=rung, source=source)
        _t0 = time.monotonic()
        # Pass judge feedback into the retry so the executor can self-correct.
        # Executors that don't accept a `feedback` kwarg (legacy) keep working.
        if feedback is None or not _accepts(executor.run, task, effective_workdir, feedback=feedback):
            result = executor.run(deepcopy(task), effective_workdir)
        else:
            result = executor.run(deepcopy(task), effective_workdir, feedback=feedback)
        if evidence is not None:
            evidence.dispatch(result)
        _tok = getattr(result, "token_usage", {})
        if not isinstance(_tok, dict):
            _tok = {}
        emit("dispatch_end", slice_id=task.id, model=model,
             rc=0 if getattr(result, "ok", False) is True else 1,
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
        # one-arg runners (workdir) are adapted by signature inspection.
        try:
            if verifier is not None:
                candidate = verifier.capture()
                files_changed, diff = list(candidate.files_changed), candidate.diff
            if (not isinstance(result, ExecutorResult) or type(result.ok) is not bool
                    or not isinstance(result.raw_log, str) or not isinstance(result.diff, str)
                    or not isinstance(result.files_changed, list)
                    or not all(isinstance(p, str) for p in result.files_changed)
                    or not isinstance(result.token_usage, dict)):
                raise CaptureError("Malformed executor completion")
            if not result.ok:
                raise CaptureError("Executor dispatch failed: " + result.raw_log[-500:])
            if verifier is None:
                # Compatibility for synthetic callers with no Git boundary.
                files_changed, diff = result.files_changed, result.diff
                judge_result = judge_fn(files_changed=files_changed, allowed=task.files,
                    run_tests=(lambda: run_at(effective_workdir)) if test_runner else lambda: result.raw_log)
            else:
                if not candidate.files_changed and not (verifier.allow_already_satisfied
                                                        and verifier.baseline_passed):
                    raise CaptureError("No-change acceptance requires allow_already_satisfied and a passing baseline")
                with verifier.snapshot(candidate) as directory:
                    outputs = []
                    def run_frozen_tests():
                        output = run_at(directory)
                        if not isinstance(output, str) or _extract_rc(output) is None:
                            raise CaptureError("Acceptance runner must return an authoritative exit code")
                        outputs.append(output)
                        return output
                    judge_result = judge_fn(files_changed=files_changed, allowed=list(verifier.allowed),
                                            run_tests=run_frozen_tests)
                    if not isinstance(judge_result, JudgeResult) or type(judge_result.passed) is not bool:
                        raise CaptureError("Malformed judge completion")
                    if len(outputs) != 1:
                        raise CaptureError("Judge must run the frozen acceptance inputs exactly once")
                    authoritative = judge(files_changed, list(verifier.allowed), run_tests=lambda: outputs[0])
                    if authoritative.passed and (authoritative.tests_passed < 1 or authoritative.tests_failed):
                        raise CaptureError("Acceptance requires at least one passing test and no failures")
                    if not authoritative.passed:
                        judge_result = authoritative
                verifier.verify_unchanged(candidate)
        except CaptureError as exc:
            judge_result = JudgeResult(False, 0, 0, failing_tests=[str(exc)])

        history.append(judge_result)
        final_judge_result = judge_result
        if evidence is not None:
            evidence.verdict(judge_result)

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
                files_changed=list(files_changed),
                diff_lines=_count_diff_lines(diff),
                model=model,
                effort=_effort_of(model),
                token_usage=_tok,
                candidate=candidate,
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
        files_changed=list(files_changed),
        diff_lines=_count_diff_lines(diff),
        model=model,
        effort=_effort_of(model),
        token_usage=_tok,
        candidate=candidate,
    )


@dataclass
class SliceDetail:
    slice_id: str
    status: str            # "completed" | "failed" | "skipped" | "deferred"
    files_changed: list[str] = field(default_factory=list)
    attempts: int = 0
    diff_lines: int = 0    # count of added/removed lines in the diff (for the summary)
    failing_tests: list[str] = field(default_factory=list)
    commit: str | None = None
    recovery_path: str | None = None
    worktree_path: str | None = None
    cleanup_warning: str | None = None


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
    repo_dir: str | None = None,
    git_runner: Callable | None = None,
    simulation: bool = False,
) -> PlanResult:
    if not simulation:
        return run_plan_parallel(slices, ledger, executor=executor, judge_fn=judge_fn,
                                 max_retries=max_retries, max_workers=1, repo_dir=repo_dir,
                                 git_runner=git_runner, test_runner=test_runner)
    if repo_dir is not None or git_runner is not None:
        raise CaptureError("Simulation cannot be combined with a real Git boundary")
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
            simulation=True,
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
    simulation: bool = False,
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
    never share a directory. Report-only test doubles must explicitly select
    `simulation=True`; that mode uses task.id and cannot take a Git boundary.

    Quota-awareness: if `quota_check` is provided and returns a percentage >=
    `quota_threshold`, slices are NOT dispatched — they are recorded in
    `result.deferred` so a later run (after the quota window resets) picks them up.
    This protects the flat-rate executor's quota bucket during large fan-outs.
    """
    if simulation:
        if repo_dir is not None or git_runner is not None:
            raise CaptureError("Simulation cannot be combined with a real Git boundary")
    elif repo_dir is None or git_runner is None:
        raise CaptureError("Plan delivery requires repo_dir and git_runner; use simulation=True only for test doubles")
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

    def _worktree_delivery(task, ex, spec, retries, source, rung):
        # Cleanup is explicitly delayed until the durable ledger write below.
        with worktree(repo_dir, f"slice-{task.id}", runner=git_runner, cleanup=False) as wt:
            session = None
            res = None
            try:
                session = RecoverySession(repo_dir, wt, task, ledger.path, git_runner)
                res = deliver_slice(task, executor=ex, judge_fn=judge_fn,
                    max_retries=retries, workdir=wt, test_runner=test_runner,
                    model=spec, source=source, rung=rung, git_runner=git_runner, evidence=session)
                if res.accepted:
                    session.save(delivery=dict(attempts=res.attempts, model=res.model,
                        effort=res.effort, token_usage=res.token_usage, final_rung=rung,
                        final=asdict(res.final)))
                    collected = session.collect(res.candidate)
                    if not collected.ok:
                        raise CaptureError(collected.error)
                    res.collection = {**asdict(collected), "base": res.candidate.base,
                                      "tests_fingerprint": res.candidate.tests_fingerprint}
                else:
                    session.save(state="failed")
            except BaseException as exc:
                detail = f"{exc}; worktree retained at {wt}"
                if session is not None:
                    try:
                        session.failure(exc)
                    except Exception as preservation_error:
                        detail += f"; recovery incomplete: {preservation_error}"
                    detail += f"; evidence: {session.directory}"
                if not isinstance(exc, Exception):
                    exc.add_note(detail)
                    raise
                if res is None:
                    res = DeliverResult(False, session.attempt if session else 0, None, model=spec)
                res.accepted = False
                res.final = JudgeResult(False, 0, 0, failing_tests=[detail])
            res.worktree_path = wt
            res.recovery_path = str(session.directory) if session is not None else None
            if not res.accepted and res.final is not None:
                res.final.failing_tests.append(f"Worktree retained at {wt}; evidence: {res.recovery_path}")
            return res

    def _run_one(task: SliceTask):
        if not simulation:
            recovered = recover_collected(repo_dir, ledger.path, task, git_runner)
            if recovered is not None:
                record, directory = recovered
                candidate_data = {**record["candidate"]}
                candidate_data["files_changed"] = tuple(candidate_data["files_changed"])
                candidate = Candidate(**candidate_data)
                delivery = record["delivery"]
                final = JudgeResult(**delivery["final"])
                return DeliverResult(True, delivery["attempts"], final, history=[final],
                    files_changed=list(candidate.files_changed), diff_lines=_count_diff_lines(candidate.diff),
                    model=delivery["model"], effort=delivery["effort"], token_usage=delivery["token_usage"],
                    final_rung=delivery["final_rung"], candidate=candidate,
                    collection={**record["collection"], "base": candidate.base,
                                "tests_fingerprint": candidate.tests_fingerprint},
                    recovery_path=directory, worktree_path=record["worktree"])
        if rung_planner is None:
            ex, spec = _executor_for(task)
            source = "tag" if task.executor else "default"
            if not simulation:
                return _worktree_delivery(task, ex, spec, max_retries, source, "workhorse")
            return deliver_slice(task, executor=ex, judge_fn=judge_fn, max_retries=max_retries,
                test_runner=test_runner, model=spec, source=source, rung="workhorse", simulation=True)

        rungs = rung_planner(task) or [("workhorse", _resolve_spec(task), max_retries)]
        last = None
        for i, (rung, spec, budget) in enumerate(rungs):
            if i:
                emit("escalate", slice_id=task.id, from_rung=rungs[i - 1][0], to_rung=rung)
            source = "tag" if task.executor else ("escalated" if i else "default")
            ex = executor_factory(spec) if executor_factory is not None else executor
            if not simulation:
                res = _worktree_delivery(task, ex, spec, max(budget - 1, 0), source, rung)
            else:
                res = deliver_slice(task, executor=ex, judge_fn=judge_fn,
                    max_retries=max(budget - 1, 0), test_runner=test_runner, model=spec,
                    source=source, rung=rung, simulation=True)
            last = res
            if res.accepted:
                res.final_rung = rung
                return res
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
            failing = list(deliver_res.final.failing_tests) if deliver_res.final is not None else []
            status = "needs_repair" if deliver_res.needs_repair else (
                "completed" if deliver_res.accepted else "failed")
            persisted_status = DONE if status == "completed" else status
            previous = deepcopy(ledger.get(task.id))
            ledger.set(task.id, status=persisted_status, attempts=deliver_res.attempts,
                       model=deliver_res.model, effort=deliver_res.effort,
                       token_usage=deliver_res.token_usage, complexity=task.complexity,
                       final_rung=deliver_res.final_rung,
                       chosen_by=("you" if task.executor else "rec"),
                       commit=deliver_res.collection.get("commit"), collection=deliver_res.collection,
                       recovery_path=deliver_res.recovery_path, worktree_path=deliver_res.worktree_path)
            try:
                ledger.save()
            except BaseException as exc:
                # A failed save must not leave this in-memory ledger saying DONE.
                if previous is None:
                    ledger.entries.pop(task.id, None)
                else:
                    ledger.entries[task.id] = previous
                exc.add_note(f"Ledger save failed; worktree retained at {deliver_res.worktree_path}; "
                             f"collection {deliver_res.collection}; evidence {deliver_res.recovery_path}")
                raise
            detail = SliceDetail(slice_id=task.id, status=status,
                files_changed=list(deliver_res.files_changed), attempts=deliver_res.attempts,
                diff_lines=deliver_res.diff_lines, failing_tests=failing,
                commit=deliver_res.collection.get("commit"), recovery_path=deliver_res.recovery_path,
                worktree_path=deliver_res.worktree_path)
            if deliver_res.accepted and not simulation:
                try:
                    wt = deliver_res.worktree_path
                    expected = f"{os.path.abspath(repo_dir)}-wt-slice-{task.id}"
                    if os.path.abspath(wt) != expected:
                        raise CaptureError(f"Unrecognized cleanup path: {wt}")
                    if os.path.exists(wt):
                        CandidateVerifier(git_runner, wt, task, base=deliver_res.candidate.base).verify_unchanged(deliver_res.candidate)
                        remove_worktree(repo_dir, wt, runner=git_runner)
                except Exception as exc:
                    detail.cleanup_warning = f"Cleanup incomplete; worktree retained at {wt}: {exc}"
            {"completed": result.completed, "failed": result.failed,
             "needs_repair": result.needs_repair}[status].append(task.id)
            result.details[task.id] = detail
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
