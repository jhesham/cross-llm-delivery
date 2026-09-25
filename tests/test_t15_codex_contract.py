"""Offline acceptance for the optional Codex executor contract; no live CLI call."""

from pathlib import Path

import pytest

from cld_providers.codex.contract import (
    CodexContractError,
    build_invocation,
    check_capabilities,
    parse_exec_output,
)


FIXTURES = Path(__file__).parent / "fixtures" / "codex"
HELP = """Usage: codex exec [OPTIONS] [PROMPT]
  --json
  --ephemeral
  --sandbox <SANDBOX_MODE>
  --cd <DIR>
  --model <MODEL>
  --config <key=value>
  If PROMPT is '-' read from stdin.
"""


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_capability_probe_is_feature_based():
    assert check_capabilities("codex-cli 0.155.1", HELP) == "codex-cli 0.155.1"
    with pytest.raises(CodexContractError, match="--ephemeral"):
        check_capabilities("codex-cli 0.100.0", HELP.replace("--ephemeral", ""))
    with pytest.raises(CodexContractError, match="stdin|PROMPT| -"):
        check_capabilities("codex-cli 0.155.1", HELP.replace("If PROMPT is '-' read from stdin.", ""))
    with pytest.raises(CodexContractError, match="version|Codex"):
        check_capabilities("garbage", HELP)


def test_invocation_is_fresh_explicit_and_isolated(tmp_path):
    # A real Git worktree is the only permitted working root.
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    prompt = "Implement café Ω\n" * 100
    call = build_invocation("gpt-example-codex", tmp_path, prompt, effort="high")
    assert call.argv[:2] == ["codex", "exec"]
    for flag in ("--json", "--ephemeral", "--sandbox", "--cd", "--model", "--config"):
        assert flag in call.argv
    assert call.argv[-1] == "-"
    assert call.argv[call.argv.index("--model") + 1] == "gpt-example-codex"
    assert call.argv[call.argv.index("--sandbox") + 1] == "workspace-write"
    assert call.argv[call.argv.index("--cd") + 1] == str(tmp_path.resolve())
    assert call.argv[call.argv.index("--config") + 1] == 'model_reasoning_effort="high"'
    assert prompt in call.stdin
    assert "Do not invoke CLD" in call.stdin
    assert call.cwd == str(tmp_path.resolve())
    assert call.env == {"CLD_EXECUTOR_DEPTH": "1"}
    assert not any(x in call.argv for x in ("resume", "--last", "--skip-git-repo-check", "--dangerously-bypass-approvals-and-sandbox"))


@pytest.mark.parametrize("model,effort,sandbox,depth", [
    ("", None, "workspace-write", 0),
    ("bad\nmodel", None, "workspace-write", 0),
    ("gpt-example", "invented", "workspace-write", 0),
    ("gpt-example", None, "danger-full-access", 0),
    ("gpt-example", None, "workspace-write", 1),
])
def test_invocation_rejects_unsafe_configuration(tmp_path, model, effort, sandbox, depth):
    with pytest.raises(CodexContractError):
        build_invocation(model, tmp_path, "task", effort=effort, sandbox=sandbox, depth=depth)


def test_invocation_rejects_non_git_root(tmp_path):
    with pytest.raises(CodexContractError, match="Git|worktree"):
        build_invocation("gpt-example", tmp_path, "task")


def test_success_usage_is_reported_without_double_counting():
    result = parse_exec_output(fixture("success.jsonl"), "", 0)
    assert result.ok and result.error is None
    assert result.usage == {"input": 120, "output": 45, "cache_read": 20, "total": 165}
    assert result.usage_raw["reasoning_output_tokens"] == 10
    assert "cost" not in result.usage and "cache_write" not in result.usage


@pytest.mark.parametrize("stdout,stderr,rc,process_error,error", [
    ("turn-failed.jsonl", "", 0, None, "turn_failed"),
    ("truncated.jsonl", "", 0, None, "malformed_output"),
    ("success.jsonl", "", 1, None, "nonzero_exit"),
    ("success.jsonl", "authentication failed", 1, None, "authentication"),
    ("success.jsonl", "login required", 0, None, "authentication"),
    ("success.jsonl", "", 0, "timeout", "timeout"),
    ("success.jsonl", "", 0, "cancelled", "cancelled"),
], ids=["turn-failure", "truncated", "nonzero", "auth-nonzero", "auth-zero", "timeout", "cancelled"])
def test_failures_never_become_success(stdout, stderr, rc, process_error, error):
    result = parse_exec_output(fixture(stdout), stderr, rc, process_error=process_error)
    assert not result.ok and result.error == error


def test_completion_cardinality_and_event_integrity():
    success = fixture("success.jsonl")
    completion = success.splitlines()[-1] + "\n"
    for altered in (success.replace(completion, ""), success + completion,
                    success.replace('{"type":"turn.started"}\n', ""),
                    success + '{"type":"error","message":"late failure"}\n'):
        assert not parse_exec_output(altered, "", 0).ok


def test_missing_usage_is_unknown_and_invalid_usage_fails():
    success = fixture("success.jsonl")
    without_usage = success.replace(',"usage":{"input_tokens":120,"cached_input_tokens":20,"output_tokens":45,"reasoning_output_tokens":10}', "")
    result = parse_exec_output(without_usage, "", 0)
    assert result.ok and result.usage == {} and result.usage_raw == {}
    invalid = success.replace('"input_tokens":120', '"input_tokens":-1')
    assert not parse_exec_output(invalid, "", 0).ok
