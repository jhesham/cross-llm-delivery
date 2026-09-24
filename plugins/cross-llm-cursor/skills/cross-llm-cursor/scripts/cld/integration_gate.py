from dataclasses import dataclass, field
from typing import Callable

from cld.judge import judge


@dataclass
class GateResult:
    passed: bool
    batch: list[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    failing_tests: list[str] = field(default_factory=list)
    rework_batch: list[str] = field(default_factory=list)
    raw_output: str = ""


def integration_gate(batch: list[str], *, run_full_suite: Callable[[], str]) -> GateResult:
    verdict = judge([], [], run_tests=run_full_suite)
    raw_output = verdict.raw_output
    passed_count, failed_count, failing_tests = verdict.tests_passed, verdict.tests_failed, verdict.failing_tests
    passed = verdict.passed
    rework_batch = [] if passed else list(batch)
    
    return GateResult(
        passed=passed,
        batch=list(batch),
        tests_passed=passed_count,
        tests_failed=failed_count,
        failing_tests=failing_tests,
        rework_batch=rework_batch,
        raw_output=raw_output
    )
