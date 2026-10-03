"""CLD slice CONTRACT: offline Claude CLI contract. Red by AssertionError only."""
import importlib
import json

import pytest

FLAGS = ("-p", "--output-format", "--model", "--effort", "--safe-mode", "--restricted",
         "--strict-mcp-config", "--mcp-config", "--tools", "--permission-mode", "--allowed-tools",
         "--settings", "--no-session-persistence")
HELP = "Usage: claude [options]\n" + "\n".join(f"  {flag} <value>   description" for flag in FLAGS)
TOOLS = "Read,Edit,Write,Glob,Grep,Bash"


def _contract():
    try:
        module = importlib.import_module("cld_providers.claude.contract")
    except ImportError:
        module = None
    assert module is not None, "cld_providers.claude.contract not implemented"
    return module


def _result(**overrides):
    body = {"type": "result", "subtype": "success", "is_error": False, "result": "done",
            "total_cost_usd": 0.0123, "num_turns": 3,
            "usage": {"input_tokens": 120, "output_tokens": 30,
                      "cache_read_input_tokens": 900, "cache_creation_input_tokens": 50},
            "modelUsage": {"claude-sonnet-5": {"inputTokens": 120}}}
    body.update(overrides)
    return json.dumps(body)


def _parse(stdout, stderr="", rc=0, model="claude-sonnet-5", **kw):
    return _contract().parse_result(stdout, stderr, rc, model=model, **kw)


def test_capabilities_accept_current_cli():
    assert _contract().check_capabilities("2.1.286 (Claude Code)\n", HELP) == "2.1.286 (Claude Code)"


@pytest.mark.parametrize("flag", FLAGS)
def test_each_missing_flag_is_rejected(flag):
    contract = _contract()
    text = "\n".join(line for line in HELP.splitlines() if f"  {flag} " not in line)
    with pytest.raises(contract.ClaudeContractError, match=flag.replace("-", r"\-")):
        contract.check_capabilities("2.1.286 (Claude Code)", text)


def test_flag_must_be_whole_token():
    contract = _contract()
    text = HELP.replace("  --safe-mode <value>", "  --safe-mode-extended <value>")
    with pytest.raises(contract.ClaudeContractError):
        contract.check_capabilities("2.1.286 (Claude Code)", text)


def test_unrecognized_version_rejected():
    contract = _contract()
    with pytest.raises(contract.ClaudeContractError):
        contract.check_capabilities("codex-cli 0.159.2", HELP)


def test_invocation_is_exact_and_isolated(tmp_path):
    contract = _contract()
    (tmp_path / ".git").mkdir()
    inv = contract.build_invocation("claude-sonnet-5", str(tmp_path), "do the slice", effort="low")
    assert inv.argv == ["claude", "-p", "--output-format", "json", "--model", "claude-sonnet-5",
                        "--effort", "low", "--safe-mode", "--restricted", "--strict-mcp-config",
                        "--mcp-config", '{"mcpServers":{}}', "--tools", TOOLS, "--permission-mode",
                        "dontAsk", "--allowed-tools", TOOLS, "--settings", '{"autoMemoryEnabled":false}',
                        "--no-session-persistence"]
    assert inv.stdin.endswith("do the slice") and "do the slice" not in " ".join(inv.argv)
    assert "git" in inv.stdin.lower() and "cld" in inv.stdin.lower()
    assert inv.env == {"CLD_EXECUTOR_DEPTH": "1", "CLAUDE_CODE_EFFORT_LEVEL": "low"}
    assert inv.unset_env == ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
    assert "bypassPermissions" not in inv.argv and "--dangerously-skip-permissions" not in inv.argv


@pytest.mark.parametrize("model,effort,prompt", [
    ("sonnet", "low", "x"), ("claude-sonnet-5\n", "low", "x"), ("claude-sonnet-5", None, "x"),
    ("claude-sonnet-5", "ultra", "x"), ("claude-sonnet-5", "low", "  ")])
def test_invalid_invocations_rejected(tmp_path, model, effort, prompt):
    contract = _contract()
    (tmp_path / ".git").mkdir()
    with pytest.raises(contract.ClaudeContractError):
        contract.build_invocation(model, str(tmp_path), prompt, effort=effort)


def test_cwd_must_be_git_root(tmp_path):
    contract = _contract()
    with pytest.raises(contract.ClaudeContractError):
        contract.build_invocation("claude-sonnet-5", str(tmp_path), "x", effort="low")


def test_success_maps_usage_and_estimate():
    outcome = _parse(_result())
    assert outcome.ok is True and outcome.error is None
    assert outcome.usage == {"input": 120, "output": 30, "cache_read": 900, "cache_write": 50, "total": 150}
    assert outcome.cost_estimate == 0.0123
    assert outcome.usage_raw["cache_read_input_tokens"] == 900


def test_missing_usage_stays_unknown():
    body = json.loads(_result())
    body.pop("usage")
    outcome = _parse(json.dumps(body))
    assert outcome.ok is True and outcome.usage == {}


def test_dated_model_key_accepted_but_other_model_is_mismatch():
    assert _parse(_result(modelUsage={"claude-sonnet-5-20261001": {}})).ok is True
    assert _parse(_result(modelUsage={"claude-sonnet-5-5": {}})).error == "model_mismatch"


def test_helper_model_without_requested_is_mismatch():
    outcome = _parse(_result(modelUsage={"claude-haiku-4-5": {}}))
    assert outcome.ok is False and outcome.error == "model_mismatch"


def test_usage_limit_is_classified():
    assert _parse(_result(is_error=True, subtype="error_during_execution",
                          result="Claude usage limit reached; resets at 5pm")).error == "usage_limit"
    assert _parse("", stderr="You are out of extra usage", rc=1).error == "usage_limit"


def test_not_logged_in_is_classified():
    assert _parse("", stderr="Not logged in. Please run /login", rc=1).error == "not_logged_in"


@pytest.mark.parametrize("stdout", ["", "not json", _result() + "\n" + _result(),
                                    json.dumps({"type": "assistant"})])
def test_malformed_output(stdout):
    assert _parse(stdout).error == "malformed_output"


def test_error_subtype_is_retryable_turn_failure():
    assert _parse(_result(is_error=True, subtype="error_max_turns")).error == "turn_failed"


def test_invalid_usage():
    assert _parse(_result(usage={"input_tokens": -1})).error == "invalid_usage"


def test_process_error_and_nonzero_exit():
    assert _parse("", process_error="timeout").error == "timeout"
    assert _parse("", stderr="boom", rc=2).error == "nonzero_exit"


def test_success_text_mentioning_login_is_not_misclassified():
    """A successful result may legitimately talk about auth (e.g. a slice writing preflight code)."""
    outcome = _parse(_result(result="Added a hint to run `claude auth login`; handles invalid API key."))
    assert outcome.ok is True and outcome.error is None


def test_login_text_in_failed_stdout_or_error_result_is_not_logged_in():
    assert _parse("Not logged in. Please run /login", rc=1).error == "not_logged_in"
    assert _parse(_result(is_error=True, subtype="error_during_execution",
                          result="Invalid API key · Please run /login")).error == "not_logged_in"
