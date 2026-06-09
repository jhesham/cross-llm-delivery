from dataclasses import dataclass, field
from typing import Any, Callable

from cld.executors.base import SliceTask
from cld.judge import JudgeResult
from cld.ledger import Ledger, DONE, FAILED, IN_PROGRESS

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
    max_retries: int = 2
) -> DeliverResult:
    history = []
    final_judge_result = None
    total_attempts = max_retries + 1
    
    for attempt in range(1, total_attempts + 1):
        result = executor.run(task, task.id)
        
        judge_result = judge_fn(
            files_changed=result.files_changed,
            allowed=task.files,
            run_tests=lambda: result.raw_log
        )
        
        history.append(judge_result)
        final_judge_result = judge_result
        
        if judge_result.passed:
            return DeliverResult(
                accepted=True,
                attempts=attempt,
                final=final_judge_result,
                history=history
            )
            
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
