"""Offline T16 adapter acceptance: fake Codex process, real Git diff, no inference."""

from dataclasses import dataclass
from pathlib import Path
import subprocess

import pytest

from cld.executors.base import SliceTask
from cld_providers.codex.provider import CodexExecutor


FIXTURE = Path(__file__).parent / "fixtures" / "codex" / "success.jsonl"
HELP = """Usage: codex exec [OPTIONS] [PROMPT]
  --json --ephemeral --sandbox --cd --model --config
  Initial instructions for the agent. If not provided (or if `-` is used),
  instructions are read from stdin.
"""


@dataclass
class FakeProcess:
    returncode: int | None = 0
    stdout: str = ""
    stderr: str = ""
    error: str | None = None

    def metadata(self):
        return {"returncode": self.returncode, "error": self.error,
                "stdout_path": "synthetic-stdout", "stderr_path": "synthetic-stderr"}


class FakeCodexRunner:
    def __init__(self, *, help_text=HELP, exec_result=None, version_result=None,
                 help_result=None, write=None):
        self.help_text = help_text
        self.exec_result = exec_result or FakeProcess(stdout=FIXTURE.read_text(encoding="utf-8"))
        self.version_result = version_result or FakeProcess(stdout="codex-cli 0.155.1\n")
        self.help_result = help_result or FakeProcess(stdout=help_text)
        self.write = write
        self.calls = []

    def __call__(self, argv, cwd, **kwargs):
        self.calls.append((list(argv), str(cwd), kwargs))
        if argv == ["codex", "--version"]:
            return self.version_result
        if argv == ["codex", "exec", "--help"]:
            return self.help_result
        assert argv[:2] == ["codex", "exec"]
        if self.write is not None:
            self.write(Path(cwd))
        return self.exec_result


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo with spaces"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t16@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "T16 test"], check=True)
    (root / "value.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "test_value.py").write_text("from value import VALUE\ndef test_value(): assert VALUE == 2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "value.py", "test_value.py"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
    return root


def task(brief="Make VALUE equal 2"):
    return SliceTask("A", brief, ["value.py"], "test_value.py")


def test_bounded_stdin_dispatch_and_real_git_diff(repo):
    runner = FakeCodexRunner(write=lambda cwd: (cwd / "value.py").write_text("VALUE = 2\n", encoding="utf-8"))
    brief = "Implement café Ω\n" * 200
    result = CodexExecutor(model="gpt-example-codex", effort="medium", runner=runner,
                           timeout=43, artifact_dir=repo.parent / "artifacts").run(task(brief), repo)
    assert result.ok
    assert result.files_changed == ["value.py"]
    assert "+VALUE = 2" in result.diff
    assert result.token_usage == {"input": 120, "output": 45, "cache_read": 20}
    assert result.usage_raw["reasoning_output_tokens"] == 10
    assert "cost" not in result.token_usage and "total" not in result.token_usage
    assert len(runner.calls) == 3
    argv, cwd, options = runner.calls[-1]
    assert argv[:2] == ["codex", "exec"] and argv[-1] == "-"
    assert argv[argv.index("--model") + 1] == "gpt-example-codex"
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert argv[argv.index("--cd") + 1] == str(repo.resolve())
    assert cwd == str(repo.resolve())
    assert brief in options["stdin"] and "test_value.py" in options["stdin"]
    assert options["env"] == {"CLD_EXECUTOR_DEPTH": "1"}
    assert options["timeout"] == 43
    assert options["artifact_dir"] == repo.parent / "artifacts"
    assert all("stdin" not in call[2] for call in runner.calls[:2])


@pytest.mark.parametrize("response,expected", [
    (FakeProcess(stdout='{"type":"turn.started"}\n'), "malformed_output"),
    (FakeProcess(stdout='{"type":"thread.started"}\n{"type":"turn.started"}\n{"type":"turn.failed"}\n'), "turn_failed"),
    (FakeProcess(returncode=1, stderr="authentication failed", error="authentication"), "authentication"),
    (FakeProcess(returncode=None, error="timeout"), "timeout"),
    (FakeProcess(returncode=None, error="cancelled"), "cancelled"),
], ids=["missing-completion", "turn-failure", "auth", "timeout", "cancelled"])
def test_failure_never_captures_diff(repo, response, expected):
    runner = FakeCodexRunner(exec_result=response,
                             write=lambda cwd: (cwd / "value.py").write_text("VALUE = 2\n", encoding="utf-8"))
    result = CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    assert not result.ok and result.diff == "" and result.files_changed == []
    assert result.process["error"] == expected


def test_missing_capability_blocks_before_dispatch(repo):
    runner = FakeCodexRunner(help_text=HELP.replace("--ephemeral", ""))
    result = CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    assert not result.ok and result.diff == ""
    assert "--ephemeral" in result.raw_log
    assert len(runner.calls) == 2


def test_nonzero_probe_blocks_even_with_supported_help_text(repo):
    runner = FakeCodexRunner(version_result=FakeProcess(returncode=1, stdout="codex-cli 0.155.1\n"))
    result = CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    assert not result.ok and result.process["error"] == "nonzero_exit"
    assert len(runner.calls) == 1


def test_recursive_dispatch_guard_precedes_process(repo, monkeypatch):
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    runner = FakeCodexRunner()
    result = CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    assert not result.ok and result.process["error"] == "recursive_dispatch"
    assert runner.calls == []


def test_file_event_does_not_override_actual_git_diff(repo):
    event = ('{"type":"thread.started"}\n{"type":"turn.started"}\n'
             '{"type":"item.completed","item":{"type":"file_change","path":"value.py"}}\n'
             '{"type":"turn.completed"}\n')
    runner = FakeCodexRunner(exec_result=FakeProcess(stdout=event),
                             write=lambda cwd: (cwd / "outside.py").write_text("X = 1\n", encoding="utf-8"))
    result = CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    assert result.ok
    assert result.files_changed == ["outside.py"]
    assert "value.py" not in result.files_changed
    assert result.token_usage == {}
