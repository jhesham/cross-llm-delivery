def test_antigravity_provider_registration():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    p = get_provider("antigravity")
    assert p.default_workhorse == "antigravity:Gemini 3.1 Pro (High)"
    ids = {m.id for m in p.catalog}
    assert len(ids) == 8
    assert "antigravity:Gemini 3.1 Pro (High)" in ids
    assert "antigravity:Claude Opus 4.6 (Thinking)" in ids
    # list_models returns the static 8 (agy models is TTY-only)
    assert len(p.list_models(lambda a, c: (0, ""))) == 8


def test_antigravity_tiers_and_buckets():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    by_id = {m.id: m for m in get_provider("antigravity").catalog}
    # exactly one quick-tier and one workhorse-tier model (deterministic auto-routing)
    workhorse_tier = [m.id for m in by_id.values() if m.tier == "workhorse"]
    quick_tier = [m.id for m in by_id.values() if m.tier == "quick"]
    assert workhorse_tier == ["antigravity:Gemini 3.1 Pro (High)"]
    assert quick_tier == ["antigravity:Gemini 3.5 Flash (Medium)"]
    # Opus is the heavy display bucket but NOT auto-routed (tier None)
    assert by_id["antigravity:Claude Opus 4.6 (Thinking)"].capability_class == "heavy"
    assert by_id["antigravity:Claude Opus 4.6 (Thinking)"].tier is None
    assert all(m.cost_class == "flat" for m in by_id.values())
