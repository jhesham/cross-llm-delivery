from dataclasses import dataclass, field
from typing import Callable

from cld.judge import parse_pytest_output


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
    raw_output = run_full_suite()
    passed_count, failed_count, failing_tests = parse_pytest_output(raw_output)
    
    passed = (failed_count == 0 and passed_count > 0)
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
