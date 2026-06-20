def test_opencode_provider():
    from cld.providers_api import _REGISTRY, load_providers, get_provider
    _REGISTRY.clear(); load_providers()
    p = get_provider("opencode")
    assert p.default_workhorse == "opencode:opencode/deepseek-v4-pro"
    # list_models parses the CLI output via the injected runner
    ids = p.list_models(lambda a, c: (0, "opencode/deepseek-v4-pro\nopencode/gemini-3.1-pro\n"))
    assert "opencode/deepseek-v4-pro" in ids
    # account block renders from parsed stats
    assert p.account_block is not None
    blk = p.account_block({"total_cost": 5.64})
    assert any("5.64" in ln for ln in blk)
    assert {m.id for m in p.catalog} >= {"opencode/deepseek-v4-pro", "opencode/claude-opus-4-8"}
