"""F01: pytest transport policy, frozen red/green candidates and provider errors."""
import inspect
import json
from pathlib import Path
import sys
import threading

import pytest

from cld import cli, validate
from cld.candidate import CandidateVerifier
from cld.executors._capture import CaptureError
from cld.executors.base import ExecutorResult, SliceTask
from cld.judge import judge
from cld.orchestrator import deliver_slice
from cld.process import ProcessResult, run_process
from tests.integration.harness import init_repo, real_git_runner

LABEL = "authentication" + " failed"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)


def commit(repo):
    for args in (["git", "add", "-A"], ["git", "commit", "-qm", "frozen regression"]):
        rc, output = real_git_runner(args, str(repo))
        assert rc == 0, output


@pytest.fixture
def project(tmp_path):
    repo = Path(init_repo(tmp_path / "project with spaces"))
    (repo / "target.py").write_text("VALUE = 0\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\naddopts = -vv\n", encoding="utf-8")
    (repo / "test_target.py").write_text(
        "import pytest\nfrom target import VALUE\n"
        f"@pytest.mark.parametrize('value', [1], ids=[{LABEL!r}])\n"
        "def test_label(value):\n    assert value == 1\n"
        "def test_value():\n    assert VALUE == 1\n", encoding="utf-8")
    commit(repo)
    return repo


@pytest.mark.parametrize("adapter", ["delivery", "validation"])
def test_frozen_candidate_accepts_red_and_green_with_diagnostic_item(project, adapter):
    runner = cli.pytest_test_runner if adapter == "delivery" else validate._pytest
    task = SliceTask("F01", "Implement value", ["target.py"], "test_target.py")
    verifier = CandidateVerifier(real_git_runner, str(project), task)
    observed = []
    def run(directory):
        result = runner(directory, task.acceptance_test_path)
        # Do not reproduce the diagnostic label in the outer frozen red summary.
        if result.error is not None:
            raise AssertionError("Pytest text was mistaken for a provider failure")
        observed.append(result)
        return result
    verifier.preflight(run)
    assert not verifier.baseline_passed
    assert observed[-1].returncode == 1 and LABEL in observed[-1].output
    (project / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    candidate = verifier.capture()
    with verifier.snapshot(candidate) as frozen:
        result = runner(frozen, task.acceptance_test_path)
        verdict = judge(files_changed=list(candidate.files), allowed=task.files, run_tests=lambda: result)
    assert result.passed and verdict.passed
    verifier.verify_unchanged(candidate)


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_process_can_disable_only_output_classification(tmp_path, stream):
    if "classify_output" not in inspect.signature(run_process).parameters:
        raise AssertionError("Add an explicit process output classification policy")
    code = f"import sys;print({LABEL!r},file=sys.{stream});sys.exit(1)"
    result = run_process([sys.executable, "-I", "-S", "-c", code], str(tmp_path),
                         artifact_dir=tmp_path / "logs", classify_output=False)
    assert result.returncode == 1 and result.error == "nonzero_exit"
    assert LABEL in result.output
    assert json.loads(Path(result.stdout_path).with_name("result.json").read_text())["error"] == "nonzero_exit"


@pytest.mark.parametrize("adapter", ["delivery", "validation"])
def test_pytest_adapters_request_transport_policy(tmp_path, monkeypatch, adapter):
    seen = []
    out, err = tmp_path / "stdout", tmp_path / "stderr"
    out.write_text("1 failed\n", encoding="utf-8")
    err.write_text("", encoding="utf-8")
    def process(argv, cwd, **options):
        seen.append(options)
        return ProcessResult(1, str(out), str(err), "nonzero_exit")
    monkeypatch.setattr(cli if adapter == "delivery" else validate, "run_process", process)
    runner = cli.pytest_test_runner if adapter == "delivery" else validate._pytest
    result = runner(str(tmp_path), "test_target.py")
    if seen[0].get("classify_output") is not False:
        raise AssertionError("Pytest adapter must select transport-only process diagnostics")
    assert result.returncode == 1 and result.error is None and not result.passed


@pytest.mark.parametrize("mode", ["timeout", "cancelled", "missing_binary"])
def test_transport_policy_keeps_real_lifecycle_errors(tmp_path, mode):
    if "classify_output" not in inspect.signature(run_process).parameters:
        raise AssertionError("Add an explicit process output classification policy")
    event = threading.Event()
    if mode == "cancelled":
        event.set()
    argv = ([str(tmp_path / "missing-cli")] if mode == "missing_binary" else
            [sys.executable, "-I", "-S", "-c",
             f"import time;print({LABEL!r},flush=True);time.sleep(60)"])
    result = run_process(argv, str(tmp_path), classify_output=False, timeout=1,
                         cancel=event, artifact_dir=tmp_path / "logs")
    assert result.error == mode


@pytest.mark.parametrize("adapter", ["delivery", "validation"])
@pytest.mark.parametrize("error", ["timeout", "cancelled", "missing_binary", "access_denied", "launch_error", "authentication"])
def test_pytest_adapters_preserve_process_failures(tmp_path, monkeypatch, adapter, error):
    out, err = tmp_path / "stdout", tmp_path / "stderr"
    out.write_text("1 passed\n", encoding="utf-8")
    err.write_text("", encoding="utf-8")
    monkeypatch.setattr(cli if adapter == "delivery" else validate, "run_process",
        lambda *args, **kwargs: ProcessResult(0, str(out), str(err), error))
    runner = cli.pytest_test_runner if adapter == "delivery" else validate._pytest
    result = runner(str(tmp_path), "test_target.py")
    assert result.error == error and not result.passed
    assert result.timed_out == (error == "timeout")


@pytest.mark.parametrize("adapter", ["delivery", "validation"])
def test_pytest_missing_returncode_is_not_success(tmp_path, monkeypatch, adapter):
    out, err = tmp_path / "stdout", tmp_path / "stderr"
    out.write_text("1 passed\n", encoding="utf-8")
    err.write_text("", encoding="utf-8")
    monkeypatch.setattr(cli if adapter == "delivery" else validate, "run_process",
        lambda *args, **kwargs: ProcessResult(None, str(out), str(err)))
    runner = cli.pytest_test_runner if adapter == "delivery" else validate._pytest
    assert not runner(str(tmp_path), "test_target.py").passed


@pytest.mark.parametrize("adapter", ["delivery", "validation"])
@pytest.mark.parametrize("mode", ["collection", "configuration", "no-tests"])
def test_invalid_pytest_runs_remain_invalid_baselines(project, adapter, mode):
    runner = cli.pytest_test_runner if adapter == "delivery" else validate._pytest
    if mode == "collection":
        (project / "test_target.py").write_text("this is not valid python!\n", encoding="utf-8")
        selector = "test_target.py"
    elif mode == "configuration":
        (project / "pytest.ini").write_text("[pytest]\naddopts = --f01-invalid-option\n", encoding="utf-8")
        selector = "test_target.py"
    else:
        selector = 'test_target.py -k "f01_no_matching_test"'
    if mode != "no-tests":
        commit(project)
    result = runner(str(project), selector)
    assert result.returncode in (2, 4, 5) and not result.passed
    verifier = CandidateVerifier(real_git_runner, str(project),
        SliceTask("F01", "brief", ["target.py"], selector))
    with pytest.raises(CaptureError, match="Baseline must pass or fail assertions"):
        verifier.preflight(lambda where: runner(where, selector))


def test_provider_authentication_still_stops_after_one_dispatch(tmp_path):
    class Executor:
        calls = 0
        def run(self, task, workdir, feedback=None):
            self.calls += 1
            proc = run_process([sys.executable, "-I", "-S", "-c",
                f"import sys;print({LABEL!r},file=sys.stderr);sys.exit(1)"], str(tmp_path))
            assert proc.error == "authentication"
            return ExecutorResult(False, "", raw_log=proc.output, process=proc.metadata())
    executor = Executor()
    result = deliver_slice(SliceTask("F01", "brief", ["target.py"], "test_target.py"),
        executor=executor, judge_fn=judge, test_runner=lambda where: "1 failed",
        simulation=True, workdir=str(tmp_path), max_retries=2)
    assert executor.calls == 1 and not result.accepted and result.final_error == "authentication"
