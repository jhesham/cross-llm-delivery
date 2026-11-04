"""v0.5.2 review (SPECOPTS): model-free spec checks cover Codex options, and control characters are never trimmed away."""
import pytest

from tests.evidence._lazy import resolve
from tests.v052.test_gateway_spec import _plan_repo


def _resolve(spec):
    from cld.providers_api import load_providers
    load_providers()
    return resolve("cld.models", "resolve_spec")(spec)


def _rejected(spec):
    try:
        _resolve(spec)
    except ValueError as exc:
        return str(exc)
    return None


def test_codex_effort_is_validated_when_parsing():
    error = _rejected("codex:gpt-example@banana")
    assert error is not None and "effort" in error.lower(), error


def test_valid_codex_specs_still_parse():
    assert _resolve("codex:gpt-example@high")[2]["effort"] == "high"
    assert _resolve("codex:gpt-example@max+fast")[2]["service_tier"] == "fast"


@pytest.mark.parametrize("flag", [[], ["--json"]])
def test_dry_run_rejects_an_invalid_codex_effort(tmp_path, capsys, flag):
    from cld import cli
    repo = _plan_repo(tmp_path)
    code = cli.main([str(repo / "plan.md"), "--repo", str(repo), "--executor", "codex:gpt-example@banana",
                     "--dry-run", *flag])
    out = capsys.readouterr().out
    assert code != 0 or '"gate_code": 5' in out, out[-500:]


@pytest.mark.parametrize("spec", ["claude:global.anthropic.claude-opus-5-5\n@low", "claude:\tclaude-opus-5-5@low",
                                  "codex:gpt-example\r@high"])
def test_control_characters_are_rejected_not_trimmed(monkeypatch, spec):
    monkeypatch.setenv("CLD_CLAUDE_MODE", "gateway")
    assert _rejected(spec) is not None, spec
