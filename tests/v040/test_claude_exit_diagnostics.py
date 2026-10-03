"""v0.4.1 N02: Claude login/usage-limit diagnostics survive the production nonzero-exit label.

The shared runner labels any exit code 1 `nonzero_exit`; that generic label must
not hide the CLI's own diagnostic, or delivery retries and escalates instead of
stopping once at the resumable final-error gate. Real subprocesses throughout.
"""
import json
import subprocess
import sys

import pytest

from cld.executors.base import FINAL_EXECUTOR_ERRORS, SliceTask
from cld.judge import judge
from cld.process import run_process
from cld.validate import _pytest
from cld_providers.claude.contract import parse_result

MODEL = "claude-sonnet-5"
HELP = "Usage: claude\n" + "\n".join(f"  {f} <x>" for f in (
    "-p", "--output-format", "--model", "--effort", "--safe-mode", "--restricted", "--strict-mcp-config",
    "--mcp-config", "--tools", "--permission-mode", "--allowed-tools", "--settings", "--no-session-persistence"))

LOGIN = "Not logged in. Please run /login"
USAGE = "You are out of extra usage"
LIMIT_JSON = json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                         "result": "Claude usage limit reached. Your limit will reset at 5pm."})


def _child(stdout="", stderr="", code=1):
    script = (f"import sys; sys.stdout.write({stdout!r}); sys.stderr.write({stderr!r}); "
              f"sys.exit({code})")
    return [sys.executable, "-c", script]


def _parse_real(tmp_path, **child):
    proc = run_process(_child(**child), str(tmp_path), timeout=60)
    return proc, parse_result(proc.stdout, proc.stderr, proc.returncode, model=MODEL, process_error=proc.error)


@pytest.mark.parametrize("child,expected", [
    (dict(stderr=LOGIN), "not_logged_in"),
    (dict(stderr=USAGE), "usage_limit"),
    (dict(stdout=LIMIT_JSON), "usage_limit"),
    (dict(stderr="something else broke"), "nonzero_exit"),
])
def test_real_nonzero_exit_keeps_diagnostic(tmp_path, child, expected):
    proc, outcome = _parse_real(tmp_path, **child)
    assert proc.error == "nonzero_exit"
    assert outcome.ok is False and outcome.error == expected


def test_nonzero_exit_never_accepts_a_success_result(tmp_path):
    success = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "done",
                          "modelUsage": {MODEL: {}}, "usage": {}})
    _, outcome = _parse_real(tmp_path, stdout=success)
    assert outcome.ok is False and outcome.error == "nonzero_exit"


@pytest.mark.parametrize("error", ["timeout", "cancelled", "missing_binary", "launch_error"])
def test_lifecycle_errors_stay_authoritative(error):
    outcome = parse_result("", LOGIN, None, model=MODEL, process_error=error)
    assert outcome.ok is False and outcome.error == error


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return None\n")
    (tmp_path / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "b"], cwd=tmp_path, check=True)
    return tmp_path


def _git(argv, cwd):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


@pytest.mark.parametrize("child,expected", [
    (dict(stderr=LOGIN), "not_logged_in"),
    (dict(stderr=USAGE), "usage_limit"),
    (dict(stdout=LIMIT_JSON), "usage_limit"),
])
def test_adapter_to_orchestrator_stops_after_one_dispatch(repo, child, expected):
    from cld.orchestrator import deliver_slice
    from cld_providers.claude.provider import ClaudeExecutor
    dispatches = []

    def runner(argv, cwd, **kwargs):
        if argv[1:] == ["--version"]:
            return run_process(_child(stdout="2.1.286 (Claude Code)\n", code=0), cwd, timeout=60)
        if argv[1:] == ["--help"]:
            return run_process(_child(stdout=HELP, code=0), cwd, timeout=60)
        dispatches.append(argv)
        return run_process(_child(**child), cwd, timeout=60)

    executor = ClaudeExecutor(model=MODEL, effort="low", runner=runner, git_runner=_git)
    result = deliver_slice(SliceTask("s", "b", ["calc.py"], "test_calc.py"), executor=executor,
                           judge_fn=judge, workdir=str(repo), git_runner=_git, test_runner=_pytest,
                           model=f"claude:{MODEL}@low")
    assert expected in FINAL_EXECUTOR_ERRORS
    assert len(dispatches) == 1
    assert result.final_error == expected
