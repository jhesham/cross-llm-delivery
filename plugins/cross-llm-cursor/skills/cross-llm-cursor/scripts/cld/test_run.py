"""Authoritative test process result and explicit legacy runner adapters."""
from dataclasses import dataclass, replace
import re
import subprocess


@dataclass(frozen=True)
class TestRun:
    __test__ = False
    returncode: int | None
    output: str = ""
    log_path: str | None = None
    timed_out: bool = False
    error: str | None = None
    candidate_id: str | None = None
    tests_run: int | None = None

    @property
    def passed(self):
        return (type(self.returncode) is int and self.returncode == 0
                and not self.timed_out and self.error is None and self.tests_run != 0)


def legacy_result(output, *, allow_prose=False):
    """Adapt injected pre-T07 runners. Prose is allowed only in explicit simulation."""
    if not isinstance(output, str):
        raise ValueError("Test runner must return TestRun or legacy text")
    # Only the transport prefix is a return code, never a line printed by a test.
    match = re.match(r"\A__CLD_PYTEST_RC__=(-?\d+)\r?\n", output)
    if match:
        return TestRun(int(match[1]), output[match.end():])
    if allow_prose:
        passed = bool(re.search(r"\b[1-9]\d* passed\b", output))
        failed = bool(re.search(r"\b[1-9]\d* (?:failed|errors?)\b", output))
        return TestRun(0 if passed and not failed else 1, output)
    return TestRun(None, output, error="missing_returncode")


def test_result(value, *, candidate_id=None):
    result = value if isinstance(value, TestRun) else legacy_result(value)
    if (not isinstance(result.output, str) or type(result.timed_out) is not bool
            or (result.returncode is not None and type(result.returncode) is not int)
            or (result.tests_run is not None and (type(result.tests_run) is not int or result.tests_run < 0))):
        raise ValueError("Malformed test process result")
    if candidate_id and result.candidate_id not in (None, candidate_id):
        return replace(result, error="candidate_identity_mismatch")
    return replace(result, candidate_id=candidate_id or result.candidate_id)


test_result.__test__ = False


def process_failure(exc):
    """Preserve partial process output on timeout/launch failure."""
    def text(value):
        return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")
    timed_out = isinstance(exc, subprocess.TimeoutExpired)
    output = text(getattr(exc, "stdout", None)) + text(getattr(exc, "stderr", None))
    return TestRun(None, output + "\n" + str(exc), timed_out=timed_out,
                   error="timeout" if timed_out else "launch_error")
