"""v0.5.2 GATEWAYSPEC: gateway model IDs pass spec parsing, admission and dry runs, not just the invocation builder."""
import json
import subprocess

import pytest

from tests.evidence._lazy import resolve
from tests.v051._red import must

GATEWAY_SPEC = "claude:global.anthropic.claude-opus-5-5@low"


def _resolve(spec):
    from cld.providers_api import load_providers
    load_providers()
    return resolve("cld.models", "resolve_spec")(spec)


def test_gateway_mode_accepts_and_keeps_the_full_gateway_id(monkeypatch):
    monkeypatch.setenv("CLD_CLAUDE_MODE", "gateway")
    canonical, provider, kwargs = must(_resolve, GATEWAY_SPEC)
    assert provider == "claude" and kwargs["model"] == "global.anthropic.claude-opus-5-5"
    assert canonical == GATEWAY_SPEC


@pytest.mark.parametrize("mode", [None, "subscription"])
def test_subscription_mode_still_rejects_gateway_ids(monkeypatch, mode):
    if mode is None:
        monkeypatch.delenv("CLD_CLAUDE_MODE", raising=False)
    else:
        monkeypatch.setenv("CLD_CLAUDE_MODE", mode)
    with pytest.raises(ValueError, match="claude-sonnet-5"):
        _resolve(GATEWAY_SPEC)


def test_gateway_mode_rejects_aliases_and_accepts_plain_ids(monkeypatch):
    monkeypatch.setenv("CLD_CLAUDE_MODE", "gateway")
    with pytest.raises(ValueError):
        _resolve("claude:sonnet@low")
    assert must(_resolve, "claude:claude-opus-5-5@low")[2]["model"] == "claude-opus-5-5"


def test_gateway_error_message_quotes_the_gateway_rule(monkeypatch):
    monkeypatch.setenv("CLD_CLAUDE_MODE", "gateway")
    with pytest.raises(ValueError) as info:
        _resolve("claude:sonnet@low")
    assert "claude-sonnet-5" not in str(info.value) and "gateway" in str(info.value).lower()


def test_invalid_mode_still_raises(monkeypatch):
    monkeypatch.setenv("CLD_CLAUDE_MODE", "sometimes")
    with pytest.raises(ValueError, match="CLD_CLAUDE_MODE"):
        _resolve(GATEWAY_SPEC)


def test_one_shared_validator_for_parser_and_contract(monkeypatch, tmp_path):
    """The spec parser and the invocation builder must agree for every ID and mode."""
    (tmp_path / ".git").mkdir()
    build = resolve("cld_providers.claude.contract", "build_invocation")
    for mode, gateway in (("subscription", False), ("gateway", True)):
        monkeypatch.setenv("CLD_CLAUDE_MODE", mode)
        for model in ("claude-opus-5-5", "global.anthropic.claude-opus-5-5", "sonnet", "anthropic/claude-x"):
            try:
                _resolve(f"claude:{model}@low")
                parsed = True
            except ValueError:
                parsed = False
            try:
                build(model, tmp_path, "p", effort="low", gateway=gateway)
                built = True
            except ValueError:
                built = False
            assert parsed == built, (mode, model, parsed, built)


def _plan_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                                       encoding="utf-8")
    (repo / ".gitignore").write_text(".cld/\n", encoding="utf-8")
    (repo / "plan.md").write_text("## SLICE: A\nbrief: Fix add.\nfiles: calc.py\nacceptance_test_path: test_calc.py\n"
                                  "deps:\ncomplexity: easy\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    return repo


def test_dry_run_rejects_a_spec_the_step_would_reject(tmp_path, capsys, monkeypatch):
    from cld import cli
    monkeypatch.delenv("CLD_CLAUDE_MODE", raising=False)
    repo = _plan_repo(tmp_path)
    code = cli.main([str(repo / "plan.md"), "--repo", str(repo), "--executor", "claude:sonnet@low", "--dry-run"])
    capsys.readouterr()
    assert code != 0


def test_step_in_gateway_mode_reaches_validation_dispatch(tmp_path, capsys, monkeypatch):
    """Driver level: --step with gateway settings must get past spec parsing and admission to an executor."""
    from cld import cli
    from cld.executors.base import ExecutorResult
    repo = _plan_repo(tmp_path)
    monkeypatch.setenv("CLD_CLAUDE_MODE", "gateway")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://gateway.example.invalid")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "synthetic-token")
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)
    made = []

    class Declining:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=False, diff="", raw_log="synthetic", process={"error": "nonzero_exit"})

    def get_executor(name, **kwargs):
        made.append((name, kwargs.get("model")))
        return Declining()

    monkeypatch.setattr(cli, "_preflight_executor", lambda spec: None)
    monkeypatch.setattr(cli, "get_executor", get_executor)
    monkeypatch.setattr(cli, "_available_ids_for", lambda provider: [])
    cli.main([str(repo / "plan.md"), "--repo", str(repo), "--step", "--workers", "1", "--executor", GATEWAY_SPEC,
              "--validation-policy", "allow", "--budget-attempts", "2", "--json"])
    out = capsys.readouterr().out
    assert ("claude", "global.anthropic.claude-opus-5-5") in made, out[-1500:]
