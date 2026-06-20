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
    register_provider(_p("gemini", "gemini:gemini-3.1-pro-preview"))
    assert default_workhorse() == "gemini:gemini-3.1-pro-preview"  # many -> the gemini one


def test_load_providers_noop_when_empty(monkeypatch):
    # with no provider submodules, load_providers() must not raise
    from cld.providers_api import load_providers, _REGISTRY
    _REGISTRY.clear()
    load_providers()        # empty cld_providers -> no providers registered, no error
    assert all_providers() == []
