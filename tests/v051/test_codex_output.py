"""v0.5.1 CODEXOUT: unrelated stderr is diagnostics, not auth failure; known usage survives failures."""
from pathlib import Path

from tests.evidence._lazy import resolve
from tests.test_t16_codex_adapter import FakeCodexRunner, FakeProcess, repo, task  # noqa: F401  (fixture)

STREAM = (Path(__file__).parents[1] / "fixtures" / "codex" / "success.jsonl").read_text(encoding="utf-8")
PLUGIN_401 = ("WARN failed to warm featured plugin ids cache: request to "
              "https://plugins.example.invalid/featured failed with status 401 Unauthorized\n"
              "WARN mcp server 'docs' failed to start: missing token\n")
parse = lambda *a, **k: resolve("cld_providers.codex.contract", "parse_exec_output")(*a, **k)  # noqa: E731


def test_completed_turn_with_peripheral_401_succeeds():
    outcome = parse(STREAM, PLUGIN_401, 0)
    assert outcome.ok is True, outcome.error
    assert outcome.usage.get("input") is not None


def test_nonzero_exit_with_auth_stderr_is_still_authentication():
    outcome = parse("", "error: authentication failed: 401 Unauthorized\n", 1)
    assert outcome.ok is False and outcome.error == "authentication"


def test_zero_exit_without_completed_turn_and_auth_stderr_is_authentication():
    stream = '{"type":"thread.started"}\n{"type":"turn.started"}\n'
    outcome = parse(stream, "error: 401 Unauthorized from model provider\n", 0)
    assert outcome.ok is False and outcome.error == "authentication"


def test_structured_turn_failure_stays_a_failure():
    stream = '{"type":"thread.started"}\n{"type":"turn.started"}\n{"type":"turn.failed"}\n'
    assert parse(stream, PLUGIN_401, 0).ok is False


def test_failed_run_keeps_known_usage():
    outcome = parse(STREAM, "boom\n", 1)
    assert outcome.ok is False and outcome.usage.get("input") is not None, outcome


def test_executor_reports_known_usage_on_failure(repo):  # noqa: F811
    from cld_providers.codex.provider import CodexExecutor
    runner = FakeCodexRunner(exec_result=FakeProcess(returncode=1, stdout=STREAM, stderr="boom\n"))
    result = CodexExecutor(model="gpt-example", runner=runner).run(task(), repo)
    assert result.ok is False and result.token_usage.get("input") is not None, result.token_usage
