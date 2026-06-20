"""Test cursor provider registration (Task 5)."""


def test_cursor_provider():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    p = get_provider("cursor")
    assert p.default_workhorse == "cursor:composer-2.5"
    ids = p.list_models(lambda a, c: (0, "composer-2.5 - Composer 2.5 (current)\n"))
    assert "composer-2.5" in ids
    assert {m.id for m in p.catalog} >= {"cursor:composer-2.5"}
    # cursor account block from `about`
    assert p.account_block is not None
