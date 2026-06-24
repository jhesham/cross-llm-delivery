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

    # When the verdict is a non-pass with NO identifiable failing test, ALWAYS surface a
    # concrete reason instead of the silent "(no test id)" that hid two real bugs:
    #  - collection/import errors (pytest reports ERROR, not FAILED) — e.g. project-in-subdir;
    #  - 0 tests collected (wrong path/selector);
    #  - an unrecognized/empty summary (the concurrency false-negative: pytest produced no
    #    "passed"/"failed"/"error" line at all). Surfacing the raw tail makes such a case
    #    diagnosable instead of an inexplicable "(no test id)". (BUG B-2 + concurrency report)
    if not failing_tests and passed == 0 and failed == 0:
        if re.search(r'\d+\s+error', output):
            cause = re.search(r'((?:ModuleNotFoundError|ImportError|[A-Za-z_]*Error):[^\n]*)', output)
            detail = cause.group(1).strip() if cause else "test collection failed"
            failing_tests.append(f"COLLECTION ERROR: {detail}")
        elif re.search(r'no tests ran', output) or 'collected 0 items' in output:
            failing_tests.append(
                "NO TESTS COLLECTED (0 selected) — check acceptance_test_path / selector")
        elif output.strip():
            excerpt = " ".join(output.split())[:200]
            failing_tests.append(f"INDETERMINATE JUDGE OUTPUT (no pass/fail/error summary): {excerpt}")
        else:
            failing_tests.append("EMPTY JUDGE OUTPUT (pytest produced no output)")

    return passed, failed, failing_tests

def check_diff_rule(files_changed: list[str], allowed: list[str]) -> list[str]:
    allowed_set = set(allowed)
    disallowed = [f for f in files_changed if f not in allowed_set]
    return sorted(disallowed)

def _extract_rc(output: str):
    """Return the pytest exit code the runner prepended (`__CLD_PYTEST_RC__=N`), or None
    when absent (legacy callers / unit tests that feed raw pytest text directly)."""
    m = re.search(r'__CLD_PYTEST_RC__=(-?\d+)', output or "")
    return int(m.group(1)) if m else None


def judge(files_changed: list[str], allowed: list[str], *, run_tests: Callable[[], str]) -> JudgeResult:
    raw_output = run_tests()
    rc = _extract_rc(raw_output)
    passed, failed, failing_tests = parse_pytest_output(raw_output)
    disallowed_edits = check_diff_rule(files_changed, allowed)

    if rc is not None:
        # EXIT CODE is authoritative: pytest's `-q` summary line ("N passed") is
        # demonstrably unreliable on Windows capture (omitted even when pytest exits 0),
        # which produced false-negatives that scraping the text could never get right.
        #   0 = all passed, 1 = tests failed, 2 = usage, 5 = no tests collected.
        is_passed = (rc == 0) and (len(disallowed_edits) == 0)
        if is_passed:
            failing_tests = []  # a passing slice has no failing tests (ignore absent-summary noise)
        elif rc != 0 and not failing_tests:
            failing_tests = [f"pytest exit code {rc}"]
    else:
        # Legacy / no-rc path: fall back to scraping the summary text.
        is_passed = (failed == 0) and (passed > 0) and (len(disallowed_edits) == 0)

    return JudgeResult(
        passed=is_passed,
        tests_passed=passed,
        tests_failed=failed,
        failing_tests=failing_tests,
        disallowed_edits=disallowed_edits,
        raw_output=raw_output
    )
