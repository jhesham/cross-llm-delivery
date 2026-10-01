"""v0.3.1 fixes 3, 5 (runtime) and 7: final executor errors stop immediately.

CLD slice FINAL_ERRORS. Red by AssertionError only: new names are resolved lazily.
"""
import importlib
import inspect
import subprocess

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.judge import judge
from cld.validate import _pytest

EXPECTED = {"authentication", "missing_binary", "access_denied", "launch_error",
            "missing_capability", "invalid_invocation", "recursive_dispatch",
            "service_tier_warning", "service_tier_mismatch", "timeout",
            "network_unavailable", "diff_capture",
            # v0.4.0 Claude executor additions
            "usage_limit", "model_mismatch", "not_logged_in"}


def _attr(module, name):
    value = getattr(importlib.import_module(module), name, None)
    assert value is not None, f"{module}.{name} not implemented"
    return value


def _git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


@pytest.fixture
def repo(tmp_path):
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return None\n", encoding="utf-8")
    (tmp_path / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    return tmp_path


class Failing:
    def __init__(self, error, log="failed"):
        self.error, self.log, self.calls = error, log, 0

    def run(self, task, workdir, feedback=None):
        self.calls += 1
        return ExecutorResult(ok=False, diff="", raw_log=self.log, process={"error": self.error})


def _deliver(repo, executor):
    from cld.orchestrator import deliver_slice
    return deliver_slice(SliceTask("s", "brief", ["calc.py"], "test_calc.py"), executor=executor,
                         judge_fn=judge, workdir=str(repo), git_runner=_git, test_runner=_pytest,
                         model="codex:gpt-x@low")


def test_final_error_set_is_exact():
    assert set(_attr("cld.executors.base", "FINAL_EXECUTOR_ERRORS")) == EXPECTED


@pytest.mark.parametrize("error", ["authentication", "timeout", "service_tier_warning", "missing_binary"])
def test_final_error_dispatches_once(repo, error):
    executor = Failing(error)
    result = _deliver(repo, executor)
    assert executor.calls == 1
    assert result.accepted is False
    assert getattr(result, "final_error", None) == error


@pytest.mark.parametrize("error,needle", [("timeout", "CLD_DISPATCH_TIMEOUT"),
                                          ("network_unavailable", "network"),
                                          ("service_tier_warning", "+fast")])
def test_final_error_message_is_actionable(error, needle):
    message = _attr("cld.executors.base", "final_error_message")(error)
    assert needle in message


def test_final_error_reaches_failing_tests(repo):
    result = _deliver(repo, Failing("timeout", log="killed after 600s"))
    text = " ".join(result.final.failing_tests)
    assert "CLD_DISPATCH_TIMEOUT" in text and "killed after 600s" in text


@pytest.mark.parametrize("error", ["nonzero_exit", "turn_failed", "malformed_output"])
def test_retryable_error_still_retries(repo, error):
    executor = Failing(error, log="model produced nothing useful")
    result = _deliver(repo, executor)
    assert executor.calls == 3
    assert getattr(result, "final_error", "absent") is None


@pytest.mark.parametrize("log", ["getaddrinfo failed", "Could not resolve host: api.openai.com",
                                 "stream disconnected before completion", "os error 10013",
                                 "connect ECONNREFUSED 1.2.3.4:443"])
def test_network_failure_is_final(repo, log):
    executor = Failing("nonzero_exit", log=log)
    result = _deliver(repo, executor)
    assert executor.calls == 1
    assert getattr(result, "final_error", None) == "network_unavailable"


def test_successful_dispatch_is_not_network_classified(repo):
    class Succeeds:
        calls = 0

        def run(self, task, workdir, feedback=None):
            Succeeds.calls += 1
            (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            return ExecutorResult(ok=True, diff="", raw_log="retried after connection refused; done")

    result = _deliver(repo, Succeeds())
    assert result.accepted is True
    assert getattr(result, "final_error", None) is None


def test_network_error_helper():
    network_error = _attr("cld.process", "network_error")
    assert network_error("Error: getaddrinfo ENOTFOUND api.openai.com")
    assert not network_error("1 failed, 2 passed in 0.10s")


def test_network_block_reason_from_codex_sandbox():
    reason = _attr("cld.process", "network_block_reason")
    assert reason({"CODEX_SANDBOX_NETWORK_DISABLED": "1"})
    assert reason({"CODEX_SANDBOX_NETWORK_DISABLED": "0"}) is None
    assert reason({}) is None


def test_final_error_does_not_escalate_and_blocks(tmp_path):
    from cld.ledger import Ledger
    from cld.orchestrator import run_plan_parallel
    seen = []

    def factory(spec):
        seen.append(spec)
        return Failing("authentication")

    result = run_plan_parallel(
        [SliceTask("s", "b", ["calc.py"], "test_calc.py")], Ledger(str(tmp_path / "ledger.json")),
        executor_factory=factory,
        rung_planner=lambda task: [("workhorse", "a:m", 1), ("escalated", "b:m", 1)],
        judge_fn=judge, test_runner=lambda *a: "__CLD_PYTEST_RC__=1\n1 failed", simulation=True)
    assert seen == ["a:m"]
    assert "s" in result.blocked


def test_source_labels():
    slice_source = _attr("cld.orchestrator", "slice_source")
    assert slice_source(tag=None, rung_index=0, default_source="chosen") == "chosen"
    assert slice_source(tag="codex:m@low", rung_index=0, default_source="chosen") == "tag"
    assert slice_source(tag=None, rung_index=1, default_source="chosen") == "escalated"
    assert slice_source(tag=None, rung_index=0, default_source="default") == "default"


def test_run_plan_parallel_accepts_default_source():
    from cld.orchestrator import run_plan_parallel
    assert "default_source" in inspect.signature(run_plan_parallel).parameters


def test_deliver_slice_has_no_fabricated_model_default():
    from cld.orchestrator import deliver_slice
    assert inspect.signature(deliver_slice).parameters["model"].default is None
