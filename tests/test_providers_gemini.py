def test_gemini_provider_registers_and_shapes():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    p = get_provider("gemini")
    assert p.default_workhorse == "gemini:gemini-3.1-pro-preview"
    assert p.list_models(lambda a, c: (0, "")) == []          # gemini has no CLI model list
    ex = p.make_executor(model="gemini-3.1-pro-preview")
    from cld.executors.base import Executor
    assert isinstance(ex, Executor)
    ids = [m.id for m in p.catalog]
    assert "gemini:gemini-3.1-pro-preview" in ids


def test_gemini_demoted_to_revalidate():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    m = get_provider("gemini").catalog[0]
    assert m.headless_status == "revalidate"
