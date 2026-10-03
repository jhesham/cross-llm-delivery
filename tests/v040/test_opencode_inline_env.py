"""N03: inline OpenCode credentials and routes scope validation evidence."""
import json

import pytest

from cld.admission import validation_context
from cld_providers.opencode.provider import PROVIDER


def context(paths=()):
    return validation_context(
        "opencode:gateway/example", cli_paths=[], config_paths=paths, repo=".",
        env_patterns=PROVIDER.context_env + PROVIDER.config_env(paths))


@pytest.mark.parametrize("variable", ["MY_GATEWAY_KEY", "MY_GATEWAY_URL"])
def test_inline_reference_changes_invalidate_context(monkeypatch, variable):
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", json.dumps({"provider": {
        "gateway": {"options": {"apiKey": "{env:MY_GATEWAY_KEY}",
                                "baseURL": "{env:MY_GATEWAY_URL}"}}}}))
    monkeypatch.setenv("MY_GATEWAY_KEY", "synthetic-secret-one")
    monkeypatch.setenv("MY_GATEWAY_URL", "https://first.invalid")
    first = context()
    monkeypatch.setenv(variable, "synthetic-changed-value")
    changed = context()
    monkeypatch.delenv(variable)
    removed = context()
    assert len({c["fingerprint"] for c in (first, changed, removed)}) == 3
    assert variable in changed["env_names"]
    assert "synthetic-secret-one" not in json.dumps(first)
    assert "synthetic-changed-value" not in json.dumps(changed)


def test_inline_and_file_references_are_combined(tmp_path, monkeypatch):
    config = tmp_path / "opencode.json"
    config.write_text('{"apiKey":"{env:FILE_KEY}","url":"{env:SHARED_URL}"}')
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT",
                       '{"apiKey":"{env:INLINE_KEY}","url":"{env:SHARED_URL}"}')
    assert PROVIDER.config_env([config]) == ("FILE_KEY", "INLINE_KEY", "SHARED_URL")


def test_unrelated_session_change_does_not_invalidate_inline_context(monkeypatch):
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", '{"apiKey":"{env:INLINE_KEY}"}')
    monkeypatch.setenv("INLINE_KEY", "synthetic-key")
    first = context()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "new-lead-session")
    assert context() == first


def test_changed_inline_credential_blocks_cached_admission(tmp_path, monkeypatch):
    from cld.admission import Admission
    from cld.evidence import EvidenceStore
    from cld.validate import _evidence_key

    spec = "opencode:gateway/example"
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", '{"apiKey":"{env:INLINE_KEY}"}')
    monkeypatch.setenv("INLINE_KEY", "synthetic-first-key")
    store = EvidenceStore(tmp_path / "evidence.json")
    store.record(_evidence_key(spec), "verified", context=context())

    def unexpected_validation(_):
        pytest.fail("deny policy must not dispatch a validation probe")

    admission = Admission(store=store, validate_fn=unexpected_validation,
                          context_of=lambda _: context(), policy="deny",
                          policy_of=lambda _: ("untested", "metered-unknown"))
    assert admission.check(spec).proceeded
    monkeypatch.setenv("INLINE_KEY", "synthetic-second-key")
    verdict = admission.check(spec)
    assert verdict.status == "blocked" and not verdict.proceeded


@pytest.mark.parametrize("inline", [None, "", "{}"])
def test_absent_or_empty_inline_config_preserves_file_references(tmp_path, monkeypatch, inline):
    config = tmp_path / "opencode.json"
    config.write_text('{"apiKey":"{env:FILE_KEY}"}')
    if inline is None:
        monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
    else:
        monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", inline)
    assert PROVIDER.config_env([config]) == ("FILE_KEY",)
