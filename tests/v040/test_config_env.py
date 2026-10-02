"""v0.4.0 R03: credentials referenced by OpenCode config key validation evidence.

Red by AssertionError only: the config_env hook is resolved lazily.
"""
import json

from cld.admission import validation_context
from cld.providers_api import get_provider, load_providers


def _config_env():
    load_providers()
    hook = getattr(get_provider("opencode"), "config_env", None)
    assert hook is not None, "opencode provider has no config_env"
    return hook


def _ctx(config):
    hook = _config_env()
    patterns = (*get_provider("opencode").context_env, *hook([config]))
    return validation_context("opencode:anthropic/x", cli_paths=[], config_paths=[config],
                              repo=".", env_patterns=patterns)


def test_config_referenced_credential_changes_fingerprint(tmp_path, monkeypatch):
    config = tmp_path / "opencode.json"
    config.write_text(json.dumps({"provider": {"gw": {"options": {
        "apiKey": "{env:MY_GATEWAY_KEY}", "baseURL": "{env:MY_GATEWAY_URL}"}}}}))
    monkeypatch.setenv("MY_GATEWAY_KEY", "sk-one")
    monkeypatch.setenv("MY_GATEWAY_URL", "https://a")
    first = _ctx(config)
    monkeypatch.setenv("MY_GATEWAY_KEY", "sk-two")
    second = _ctx(config)
    monkeypatch.setenv("MY_GATEWAY_URL", "https://b")
    third = _ctx(config)
    assert len({first["fingerprint"], second["fingerprint"], third["fingerprint"]}) == 3
    assert "sk-two" not in json.dumps(second)
    assert {"MY_GATEWAY_KEY", "MY_GATEWAY_URL"} <= {n.upper() for n in third["env_names"]}


def test_unrelated_session_variable_still_ignored(tmp_path, monkeypatch):
    config = tmp_path / "opencode.json"
    config.write_text('{"apiKey": "{env:MY_GATEWAY_KEY}"}')
    first = _ctx(config)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "other")
    assert _ctx(config)["fingerprint"] == first["fingerprint"]


def test_missing_config_files_are_harmless(tmp_path):
    assert _config_env()([tmp_path / "absent.json"]) == ()
