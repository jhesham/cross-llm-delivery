from dataclasses import dataclass, field
from typing import Any, Callable

from cld.executors.base import SliceTask
from cld.judge import JudgeResult

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
