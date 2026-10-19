"""v0.5 Task 7: Codex evidence invocation (full access) without loosening code slices."""
import pytest

from tests.evidence._lazy import resolve
from tests.test_t16_codex_adapter import FakeCodexRunner, FakeProcess

C = "cld_providers.codex.contract"


def evidence_call(cwd, prompt="answer the question"):
    build = resolve(C, "build_invocation")
    error = None
    try:
        return build("gpt-example", cwd, prompt, evidence=True)
    except TypeError as exc:
        error = str(exc)
    assert error is None, f"build_invocation(evidence=True) not supported: {error}"


def evidence_executor(runner):
    from cld_providers.codex.provider import CodexExecutor
    error = None
    try:
        return CodexExecutor(model="gpt-example", runner=runner, evidence=True)
    except TypeError as exc:
        error = str(exc)
    assert error is None, f"CodexExecutor(evidence=True) not supported: {error}"


def test_evidence_invocation_uses_full_access_outside_git(tmp_path):
    call = evidence_call(tmp_path)
    assert call.argv[call.argv.index("--sandbox") + 1] == "danger-full-access"
    assert call.env == {"CLD_EXECUTOR_DEPTH": "1"}


def test_evidence_prompt_names_runner_and_bundle(tmp_path):
    call = evidence_call(tmp_path)
    text = call.stdin
    assert "evidence executor" in text.lower() and "evidence.json" in text
    assert "run_sql.py" in text and "--step" in text and "--ask" in text  # names the only allowed CLD use and the forbidden ones
    assert "interpret" in text.lower()


def test_code_invocation_still_rejects_full_access(tmp_path):
    (tmp_path / ".git").mkdir()
    error = resolve(C, "CodexContractError")
    with pytest.raises(error):
        resolve(C, "build_invocation")("gpt-example", tmp_path, "p", sandbox="danger-full-access")


def test_code_invocation_still_requires_git_root(tmp_path):
    with pytest.raises(resolve(C, "CodexContractError")):
        resolve(C, "build_invocation")("gpt-example", tmp_path, "p")


def test_run_evidence_dispatches_full_access_without_diff(tmp_path):
    runner = FakeCodexRunner()
    executor = evidence_executor(runner)
    run_evidence = getattr(executor, "run_evidence", None)
    assert run_evidence is not None, "CodexExecutor.run_evidence not implemented"
    result = run_evidence("answer the question", tmp_path)
    exec_argv = [argv for argv, _, _ in runner.calls if argv[:2] == ["codex", "exec"] and "--sandbox" in argv][0]
    assert exec_argv[exec_argv.index("--sandbox") + 1] == "danger-full-access"
    assert result.ok is True and result.diff == ""


def test_only_codex_declares_evidence_support():
    from cld.providers_api import all_providers, load_providers
    load_providers()
    support = {p.name: getattr(p, "supports_evidence", None) for p in all_providers()}
    assert support.get("codex") is True
    assert all(v is False for k, v in support.items() if k != "codex"), support
