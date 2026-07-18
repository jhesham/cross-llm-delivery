from cld.providers_api import (Provider, register_provider, get_provider,
                               all_providers, catalog, default_workhorse, _REGISTRY)
from cld.models import ModelInfo
import pytest


def _p(name, wh, models=()):
    return Provider(name=name, make_executor=lambda **k: object(), catalog=tuple(models),
                    default_workhorse=wh, list_models=lambda r: [], account_stats=None,
                    account_block=None, skill_fragment="", setup_notes="")


def setup_function(_):
    _REGISTRY.clear()


def test_register_and_get():
    p = _p("gemini", "gemini:gemini-3.1-pro-preview")
    register_provider(p)
    assert get_provider("gemini") is p
    assert [x.name for x in all_providers()] == ["gemini"]


def test_get_unknown_raises_listing_registered():
    register_provider(_p("gemini", "g"))
    with pytest.raises(ValueError) as e:
        get_provider("nope")
    assert "gemini" in str(e.value)


def test_register_is_idempotent_by_name():
    register_provider(_p("gemini", "g"))
    register_provider(_p("gemini", "g2"))   # same name re-registers, no dup
    assert len(all_providers()) == 1
    assert get_provider("gemini").default_workhorse == "g2"


def test_catalog_assembles_from_providers():
    mi = ModelInfo(id="opencode/x", provider="opencode", cost_class="cheap-metered",
                   capability_class="workhorse", headless_status="likely", rework_risk="low",
                   note="", tier="workhorse")
    register_provider(_p("opencode", "opencode:opencode/x", models=(mi,)))
    assert catalog()["opencode/x"] is mi


def test_default_workhorse_single_and_multi():
    register_provider(_p("opencode", "opencode:opencode/x"))
    assert default_workhorse() == "opencode:opencode/x"        # single -> its own
    register_provider(_p("antigravity", "antigravity:Gemini 3.1 Pro (High)"))
    assert default_workhorse() == "antigravity:Gemini 3.1 Pro (High)"  # many -> the preferred one


def test_load_providers_noop_when_empty(monkeypatch):
    # load_providers() must not raise; after registration the antigravity provider is present.
    # The original "assert all_providers() == []" was written before any provider
    # submodules existed.  Now that the providers are installed, load_providers()
    # legitimately registers them.  We just verify it does not raise.
    from cld.providers_api import load_providers, _REGISTRY
    _REGISTRY.clear()
    load_providers()        # registers the installed providers, no error
    # At minimum antigravity should be registered; other providers may be present too.
    names = [p.name for p in all_providers()]
    assert "antigravity" in names


def test_get_executor_resolves_via_registry():
    from cld.executors import get_executor
    from cld.providers_api import load_providers, _REGISTRY
    _REGISTRY.clear(); load_providers()
    from cld_providers.antigravity.provider import AntigravityExecutor
    assert isinstance(get_executor("antigravity", model="Gemini 3.1 Pro (High)"), AntigravityExecutor)


def test_catalog_matches_all_providers():
    from cld.providers_api import load_providers, _REGISTRY, catalog
    _REGISTRY.clear(); load_providers()
    # every catalogued id belongs to a registered provider; antigravity default present
    assert "antigravity:Gemini 3.1 Pro (High)" in catalog()
    assert "opencode/deepseek-v4-pro" in catalog()
    assert "cursor:composer-2.5" in catalog()


def test_all_providers_register_in_monorepo():
    from cld.providers_api import load_providers, all_providers, _REGISTRY
    _REGISTRY.clear(); load_providers()
    assert sorted(p.name for p in all_providers()) == ["antigravity", "cursor", "opencode"]


def test_assembled_catalog_has_expected_ids():
    from cld.providers_api import load_providers, _REGISTRY, catalog
    _REGISTRY.clear(); load_providers()
    ids = set(catalog())
    # the 17 catalogued models (opencode 8 + cursor 1 + antigravity 8)
    assert "cursor:composer-2.5" in ids
    assert {"opencode/deepseek-v4-pro", "opencode/claude-opus-4-8",
            "opencode/kimi-k2.7-code", "opencode/glm-5.2"} <= ids
    assert "antigravity:Gemini 3.1 Pro (High)" in ids
    assert "gemini:gemini-3.1-pro-preview" not in ids
    assert len(ids) == 17


def test_default_workhorse_prefers_antigravity():
    from cld.providers_api import _REGISTRY, load_providers, default_workhorse
    _REGISTRY.clear(); load_providers()
    assert default_workhorse() == "antigravity:Gemini 3.1 Pro (High)"
