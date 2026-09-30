"""v0.3.1 fix 1: validation evidence keyed by provider-relevant environment only."""
from datetime import datetime, timezone

from cld.admission import validation_context
from cld.evidence import fresh_record
from cld.providers_api import get_provider, load_providers


def _ctx(**kw):
    return validation_context("codex:gpt-x@low", cli_paths=[], repo=".",
                              env_patterns=("CODEX_HOME", "OPENAI_*"), **kw)


def test_unrelated_env_change_keeps_fingerprint(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-one")
    first = _ctx()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-two")
    monkeypatch.setenv("VSCODE_GIT_IPC_HANDLE", "pipe-new")
    assert _ctx() == first


def test_selected_env_change_invalidates(monkeypatch):
    monkeypatch.setenv("CODEX_HOME", "/one")
    first = _ctx()
    monkeypatch.setenv("CODEX_HOME", "/two")
    assert _ctx()["fingerprint"] != first["fingerprint"]


def test_prefix_and_base_proxy_invalidate(monkeypatch):
    first = _ctx()
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example")
    second = _ctx()
    monkeypatch.setenv("HTTPS_PROXY", "http://corp:8080")
    assert len({first["fingerprint"], second["fingerprint"], _ctx()["fingerprint"]}) == 3


def test_lowercase_proxy_is_selected(monkeypatch):
    first = _ctx()
    monkeypatch.setenv("http_proxy", "http://corp:8080")
    assert _ctx()["fingerprint"] != first["fingerprint"]


def test_values_never_stored_only_names(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    ctx = _ctx()
    assert "OPENAI_API_KEY" in ctx["env_names"]
    assert "sk-secret-value" not in repr(ctx)


def test_contract_two_and_old_evidence_is_stale():
    ctx = _ctx()
    assert ctx["contract"] == 2
    old = {**ctx, "contract": 1}
    record = {"status": "verified", "context": old,
              "validated_at": datetime.now(timezone.utc).isoformat()}
    assert not fresh_record(record, ctx, 3600)


def test_providers_declare_context_env():
    load_providers()
    assert "CODEX_HOME" in get_provider("codex").context_env
    assert "OPENAI_*" in get_provider("codex").context_env
    assert "OPENCODE_*" in get_provider("opencode").context_env
    assert "CURSOR_*" in get_provider("cursor").context_env
    assert "AGY_CMD" in get_provider("antigravity").context_env
