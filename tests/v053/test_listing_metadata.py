"""v0.5.3 LISTING: Claude plugin manifests carry the plugin-directory listing fields."""
import pytest

from tests.test_marketplace_metadata import PROJECT, PROVIDERS, generated, manifest  # noqa: F401  (fixture)

LABELS = {"antigravity": "Antigravity", "opencode": "OpenCode", "cursor": "Cursor",
          "codex": "Codex", "claude": "Claude Code"}


@pytest.mark.parametrize("provider", PROVIDERS)
def test_claude_manifest_has_directory_listing_fields(generated, provider):  # noqa: F811
    _, output = generated
    _, data = manifest(output, "claude-code", provider)
    assert data.get("displayName") == f"Cross-LLM {LABELS[provider]}", data.get("displayName")
    assert data.get("documentationUrl") == f"{PROJECT}#readme"
    assert data.get("privacyPolicyUrl") == f"{PROJECT}/blob/main/PRIVACY.md"
    keywords = data.get("keywords") or []
    assert provider in keywords and "acceptance-tests" in keywords, keywords
    assert len(keywords) == len(set(keywords)) <= 8, keywords
    assert all(k == k.lower() and " " not in k for k in keywords), keywords
    assert "termsOfServiceUrl" not in data, "an MIT project has no terms of service"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_codex_manifest_keeps_its_own_schema(generated, provider):  # noqa: F811
    _, output = generated
    _, data = manifest(output, "codex", provider)
    assert not {"documentationUrl", "privacyPolicyUrl", "keywords"} & set(data), sorted(data)
