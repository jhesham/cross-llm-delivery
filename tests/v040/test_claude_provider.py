"""v0.4.0 Claude executor: dispatch, isolation, accounting and registration (offline)."""
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess

import pytest

from cld.executors.base import SliceTask
from cld.native_cli import NativeCommand
from cld.providers_api import get_provider, load_providers

FIXTURE = (Path(__file__).parents[1] / "fixtures" / "claude" / "success.json").read_text()
MODEL = next(iter(json.loads(FIXTURE)["modelUsage"]))
HELP = "Usage: claude\n" + "\n".join(f"  {f} <x>" for f in (
    "-p", "--output-format", "--model", "--effort", "--safe-mode", "--restricted", "--strict-mcp-config",
    "--mcp-config", "--tools", "--permission-mode", "--allowed-tools", "--settings", "--no-session-persistence"))


@dataclass
class Proc:
    returncode: int | None = 0
    stdout: str = ""
    stderr: str = ""
    error: str | None = None

    def metadata(self):
        return {"returncode": self.returncode, "error": self.error}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 0\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "b"], cwd=tmp_path, check=True)
    return tmp_path


def _git(argv, cwd):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout


def _executor(repo, result, calls, model=None):
    from cld_providers.claude.provider import ClaudeExecutor

    def runner(argv, cwd, **kwargs):
        calls.append((argv, kwargs))
        if argv[1:] == ["--version"]:
            return Proc(stdout="2.1.286 (Claude Code)\n")
        if argv[1:] == ["--help"]:
            return Proc(stdout=HELP)
        (Path(cwd) / "a.py").write_text("x = 1\n")
        return result
    return ClaudeExecutor(model=model or MODEL, effort="low", runner=runner, git_runner=_git)


def _task():
    return SliceTask("s", "b", ["a.py"], "t.py")


def test_successful_dispatch_captures_diff_and_usage(repo):
    expected = json.loads(FIXTURE)
    out = _executor(repo, Proc(stdout=FIXTURE), []).run(_task(), repo)
    assert out.ok is True and out.files_changed == ["a.py"]
    usage = expected["usage"]
    assert out.token_usage == {"input": usage["input_tokens"], "output": usage["output_tokens"],
                               "cache_read": usage["cache_read_input_tokens"],
                               "cache_write": usage["cache_creation_input_tokens"]}
    assert out.usage_raw["cost_estimate_usd"] == expected["total_cost_usd"]
    assert out.usage_raw["cost_source"] == "cli_estimate_subscription"
    assert "cost" not in out.token_usage


def test_executor_strips_api_credentials(repo):
    calls = []
    _executor(repo, Proc(stdout=FIXTURE), calls).run(_task(), repo)
    argv, kwargs = calls[-1]
    assert kwargs["unset_env"] == ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
    assert kwargs["stdin"] and kwargs["stdin"] not in " ".join(argv)


def test_executor_child_marks_depth_and_ambient_depth_blocks(repo, monkeypatch):
    calls = []
    _executor(repo, Proc(stdout=FIXTURE), calls).run(_task(), repo)
    assert calls[-1][1]["env"]["CLD_EXECUTOR_DEPTH"] == "1"
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    calls.clear()
    out = _executor(repo, Proc(stdout=FIXTURE), calls).run(_task(), repo)
    assert out.ok is False and out.process["error"] == "recursive_dispatch" and calls == []


@pytest.mark.parametrize("proc,error", [
    (Proc(stdout=json.dumps({**json.loads(FIXTURE), "modelUsage": {"claude-other-1": {}}})), "model_mismatch"),
    (Proc(returncode=1, stderr="Not logged in. Please run /login"), "not_logged_in"),
    (Proc(returncode=1, stderr="You are out of extra usage"), "usage_limit"),
    (Proc(stdout="garbage"), "malformed_output"),
    (Proc(stdout=json.dumps({**json.loads(FIXTURE), "usage": {"input_tokens": -1}})), "malformed_output"),
    (Proc(returncode=None, error="timeout"), "timeout"),
])
def test_failures_never_capture(repo, proc, error):
    out = _executor(repo, proc, []).run(_task(), repo)
    assert out.ok is False and out.diff == "" and out.process["error"] == error


def test_unresolvable_cli_is_missing_binary_before_any_process(repo, monkeypatch):
    from cld_providers.claude import provider
    from cld.native_cli import NativeCliError

    def boom():
        raise NativeCliError("set CLAUDE_CLI_CMD")

    monkeypatch.setattr(provider, "resolve_claude_command", boom)
    out = provider.ClaudeExecutor(model=MODEL, effort="low").run(_task(), repo)
    assert out.process["error"] == "missing_binary" and "CLAUDE_CLI_CMD" in out.raw_log


def test_registration_and_policy():
    load_providers()
    p = get_provider("claude")
    assert p.catalog == () and p.default_workhorse == ""
    assert set(p.context_env) == {"CLAUDE_CLI_CMD", "CLAUDE_CONFIG_DIR", "ANTHROPIC_*"}
    from cld.models import model_policy, resolve_spec
    assert resolve_spec("claude:claude-sonnet-5@low") == (
        "claude:claude-sonnet-5@low", "claude", {"model": "claude-sonnet-5", "effort": "low"})
    assert model_policy("claude:claude-sonnet-5@low") == ("untested", "metered-unknown")


def test_context_extra_reflects_account(monkeypatch):
    from cld_providers.claude import provider
    from cld_providers.claude.preflight import parse_auth_status
    provider.reset_preflight_cache()
    status = parse_auth_status(json.dumps({"loggedIn": True, "authMethod": "claude.ai",
                                           "orgId": "org-A", "subscriptionType": "pro"}))
    monkeypatch.setattr(provider, "_preflight", lambda: (NativeCommand("/abs/claude", {}), status, None))
    assert provider.PROVIDER.context_extra() == "claude-account:org-A:pro"
    assert provider.PROVIDER.launch_problem() is None
    assert provider.PROVIDER.cli_invocation() == ["/abs/claude"]
    monkeypatch.setattr(provider, "_preflight", lambda: (None, None, "set CLAUDE_CLI_CMD"))
    assert provider.PROVIDER.launch_problem() == "set CLAUDE_CLI_CMD"
    assert provider.PROVIDER.cli_invocation() == ["claude"]
    assert provider.PROVIDER.context_extra() == ""
