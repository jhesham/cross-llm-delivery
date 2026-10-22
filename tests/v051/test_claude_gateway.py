"""v0.5.1 GATEWAY: opt-in gateway mode for the Claude executor; subscription mode stays the default and honest."""
import json

import pytest

from tests.evidence._lazy import resolve
from tests.v051._red import must
from tests.v040.test_claude_provider import FIXTURE, Proc, _executor, _task, repo  # noqa: F401  (fixture)

P, C = "cld_providers.claude.preflight", "cld_providers.claude.contract"
GATEWAY_MODEL = "global.anthropic.claude-opus-5-5"


def _status(**kw):
    return resolve(P, "AuthStatus")(**{"logged_in": True, "auth_method": "oauth_token",
                                       "org_id": None, "subscription_type": None, **kw})


def _settings(tmp_path, env):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"env": env}), encoding="utf-8")
    return path


def test_mode_defaults_to_subscription_and_rejects_unknown():
    mode = resolve(P, "claude_mode")
    assert mode({}) == "subscription"
    assert mode({"CLD_CLAUDE_MODE": "gateway"}) == "gateway"
    with pytest.raises(ValueError):
        mode({"CLD_CLAUDE_MODE": "something-else"})


def test_gateway_host_from_env_or_settings_never_returns_secrets(tmp_path):
    host = resolve(P, "gateway_host")
    assert host({"ANTHROPIC_BASE_URL": "https://gw.example.invalid/v1"}, tmp_path / "none.json") == "gw.example.invalid"
    settings = _settings(tmp_path, {"ANTHROPIC_BASE_URL": "https://proxy.example.invalid",
                                    "ANTHROPIC_AUTH_TOKEN": "tok-SECRET"})
    assert host({}, settings) == "proxy.example.invalid"
    assert host({}, tmp_path / "none.json") is None


def test_subscription_mode_refuses_a_gateway_routed_cli():
    problem = must(resolve(P, "auth_problem"), _status(auth_method="claude.ai"), mode="subscription",
                                         gateway="gw.example.invalid")
    assert problem and "gateway" in problem.lower() and "CLD_CLAUDE_MODE" in problem


def test_subscription_mode_unchanged_without_gateway():
    problem = resolve(P, "auth_problem")
    assert must(problem, _status(auth_method="claude.ai"), mode="subscription", gateway=None) is None
    assert must(problem, _status(auth_method="oauth_token"), mode="subscription", gateway=None)


def test_gateway_mode_accepts_gateway_auth_and_requires_a_route():
    problem = resolve(P, "auth_problem")
    assert must(problem, _status(auth_method="oauth_token"), mode="gateway", gateway="gw.example.invalid") is None
    missing = must(problem, _status(auth_method="oauth_token"), mode="gateway", gateway=None)
    assert missing and "ANTHROPIC_BASE_URL" in missing


def test_gateway_account_context_is_keyed_to_the_host():
    ctx = must(resolve(P, "account_context"), _status(), mode="gateway", gateway="gw.example.invalid")
    assert ctx == "claude-gateway:gw.example.invalid"


def test_gateway_invocation_keeps_route_and_accepts_gateway_model_ids(tmp_path):
    (tmp_path / ".git").mkdir()
    build = resolve(C, "build_invocation")
    call = must(build, GATEWAY_MODEL, tmp_path, "p", effort="low", gateway=True)
    assert "ANTHROPIC_BASE_URL" not in call.unset_env and "ANTHROPIC_AUTH_TOKEN" not in call.unset_env
    assert call.argv[call.argv.index("--model") + 1] == GATEWAY_MODEL
    with pytest.raises(resolve(C, "ClaudeContractError")):
        build(GATEWAY_MODEL, tmp_path, "p", effort="low")  # subscription mode keeps exact claude-* IDs


def test_both_modes_suppress_test_caches(tmp_path):
    (tmp_path / ".git").mkdir()
    for kw in ({}, {"gateway": True}):
        model = GATEWAY_MODEL if kw else "claude-opus-5-5"
        env = must(resolve(C, "build_invocation"), model, tmp_path, "p", effort="low", **kw).env
        assert env.get("PYTHONDONTWRITEBYTECODE") == "1" and "no:cacheprovider" in env.get("PYTEST_ADDOPTS", "")


def test_gateway_dispatch_labels_usage_as_gateway(repo, monkeypatch):  # noqa: F811
    monkeypatch.setenv("CLD_CLAUDE_MODE", "gateway")
    calls = []
    out = _executor(repo, Proc(stdout=FIXTURE), calls, model=GATEWAY_MODEL).run(_task(), repo)
    assert out.ok is True, out.raw_log
    assert out.usage_raw["cost_source"] == "gateway_api"
    dispatch = calls[-1][1]
    assert "ANTHROPIC_BASE_URL" not in dispatch.get("unset_env", ())
