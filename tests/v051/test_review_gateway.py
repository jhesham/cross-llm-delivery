"""v0.5.1 review (GATEWAY2): gateway routing must match what a --restricted dispatch actually loads."""
import json

from tests.evidence._lazy import resolve
from tests.v051._red import must

P = "cld_providers.claude.preflight"


def _settings(path, env):
    path.write_text(json.dumps({"env": env}), encoding="utf-8")
    return path


def _resolve(mode, environ, tmp_path, user=None, managed=None):
    user_file = _settings(tmp_path / "user.json", user) if user is not None else tmp_path / "no-user.json"
    managed_file = _settings(tmp_path / "managed.json", managed) if managed is not None else tmp_path / "no-managed.json"
    return must(resolve(P, "resolve_gateway"), mode, environ, user_settings=user_file, managed_settings=managed_file)


def test_subscription_ignores_user_settings_routing_that_restricted_mode_ignores(tmp_path):
    assert _resolve("subscription", {}, tmp_path, user={"ANTHROPIC_BASE_URL": "https://u.example.invalid"}) == (None, None)


def test_subscription_sees_managed_routing(tmp_path):
    host, problem = _resolve("subscription", {}, tmp_path, managed={"ANTHROPIC_BASE_URL": "https://m.example.invalid"})
    assert host == "m.example.invalid" and problem is None


def test_gateway_from_environment_needs_a_credential(tmp_path):
    ok = _resolve("gateway", {"ANTHROPIC_BASE_URL": "https://gw.example.invalid", "ANTHROPIC_AUTH_TOKEN": "x"}, tmp_path)
    assert ok == ("gw.example.invalid", None)
    host, problem = _resolve("gateway", {"ANTHROPIC_BASE_URL": "https://gw.example.invalid"}, tmp_path)
    assert problem and "ANTHROPIC_AUTH_TOKEN" in problem


def test_gateway_from_user_settings_only_is_refused(tmp_path):
    host, problem = _resolve("gateway", {}, tmp_path,
                             user={"ANTHROPIC_BASE_URL": "https://u.example.invalid", "ANTHROPIC_AUTH_TOKEN": "x"})
    assert problem and "environment" in problem.lower() and "settings.json" in problem


def test_gateway_from_managed_settings(tmp_path):
    host, problem = _resolve("gateway", {}, tmp_path, managed={"ANTHROPIC_BASE_URL": "https://m.example.invalid"})
    assert host == "m.example.invalid" and problem is None


def test_problem_text_never_contains_secret_values(tmp_path):
    _, problem = _resolve("gateway", {}, tmp_path,
                          user={"ANTHROPIC_BASE_URL": "https://u.example.invalid", "ANTHROPIC_AUTH_TOKEN": "tok-SECRET"})
    assert problem and "tok-SECRET" not in problem


def test_managed_settings_path_is_platform_specific():
    path = must(resolve(P, "managed_settings_file"))
    assert path.name == "managed-settings.json"
