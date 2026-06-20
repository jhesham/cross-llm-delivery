from dataclasses import dataclass, field
import re
from typing import Callable

@dataclass
class JudgeResult:
    passed: bool
    tests_passed: int
    tests_failed: int
    failing_tests: list[str] = field(default_factory=list)
    disallowed_edits: list[str] = field(default_factory=list)
    raw_output: str = ""

def parse_pytest_output(output: str) -> tuple[int, int, list[str]]:
    passed = 0
    failed = 0
    failing_tests = []
    
    passed_match = re.search(r'(\d+)\s+passed', output)
    if passed_match:
        passed = int(passed_match.group(1))
        
    failed_match = re.search(r'(\d+)\s+failed', output)
    if failed_match:
        failed = int(failed_match.group(1))
        
    for match in re.finditer(r'FAILED\s+(\S+)', output):
        failing_tests.append(match.group(1))
        
    return passed, failed, failing_tests

def check_diff_rule(files_changed: list[str], allowed: list[str]) -> list[str]:
    allowed_set = set(allowed)
    disallowed = [f for f in files_changed if f not in allowed_set]
    return sorted(disallowed)

def judge(files_changed: list[str], allowed: list[str], *, run_tests: Callable[[], str]) -> JudgeResult:
    raw_output = run_tests()
    passed, failed, failing_tests = parse_pytest_output(raw_output)
    disallowed_edits = check_diff_rule(files_changed, allowed)
    
    is_passed = (failed == 0) and (passed > 0) and (len(disallowed_edits) == 0)
    
    return JudgeResult(
        passed=is_passed,
        tests_passed=passed,
        tests_failed=failed,
        failing_tests=failing_tests,
        disallowed_edits=disallowed_edits,
        raw_output=raw_output
    )
