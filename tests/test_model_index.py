from cld.models import ModelChoice, _provider_of


def test_modelchoice_fields():
    c = ModelChoice(spec="cursor:composer-2.5", executor="cursor", provider="other",
                    model="composer-2.5", label="Composer 2.5", cost_class="cheap-metered",
                    headless_status="untested", efforts=["low", "high"], default_effort="high")
    assert c.spec == "cursor:composer-2.5" and c.efforts == ["low", "high"]
    assert c.default_effort == "high"


def test_provider_of_recognizes_more_providers():
    assert _provider_of("opencode/grok-build-0.1") == "grok"
    assert _provider_of("opencode/kimi-k2.6") == "kimi"
    assert _provider_of("opencode/qwen3.5-plus") == "qwen"
    assert _provider_of("opencode/glm-5") == "glm"
    assert _provider_of("opencode/minimax-m2.5") == "minimax"
    assert _provider_of("opencode/claude-opus-4-8") == "claude"
    assert _provider_of("opencode/big-pickle") == "other"


from cld.models import build_model_index


def test_build_index_merges_opencode_and_gemini_with_evidence():
    idx = build_model_index(
        opencode_ids=["opencode/deepseek-v4-pro", "opencode/gpt-5"],
        cursor_models=[],  # part 2 supplies these
        evidence={"opencode/deepseek-v4-pro": "proven"})
    by_spec = {c.spec: c for c in idx}
    # gemini workhorse always present (catalog)
    assert "gemini:gemini-3.1-pro-preview" in by_spec
    # opencode ids present, evidence overlay applied
    ds = by_spec["opencode:opencode/deepseek-v4-pro"]
    assert ds.executor == "opencode" and ds.provider == "deepseek"
    assert ds.headless_status == "proven"  # from evidence overlay
    # an uncatalogued opencode id -> untested/metered-unknown, provider classified
    gpt = by_spec["opencode:opencode/gpt-5"]
    assert gpt.provider == "gpt" and gpt.headless_status == "untested"
    assert gpt.cost_class == "metered-unknown"


def test_build_index_no_cursor_has_empty_efforts():
    idx = build_model_index(opencode_ids=["opencode/gpt-5"], cursor_models=[], evidence={})
    gpt = next(c for c in idx if c.spec == "opencode:opencode/gpt-5")
    assert gpt.efforts == [] and gpt.default_effort is None


from cld.models import browse_filter, rank_provider_models


def _mc(spec, status):
    return ModelChoice(spec=spec, executor="opencode", provider="gpt", model="m",
                       label="m", cost_class="metered-unknown", headless_status=status)


def test_browse_filter_default_hides_untested_and_known_bad():
    cs = [_mc("a", "proven"), _mc("b", "likely"), _mc("c", "untested"), _mc("d", "known-bad")]
    assert [c.spec for c in browse_filter(cs)] == ["a", "b"]


def test_browse_filter_show_all_keeps_untested_but_not_known_bad():
    cs = [_mc("a", "proven"), _mc("c", "untested"), _mc("d", "known-bad")]
    assert [c.spec for c in browse_filter(cs, headless_only=False)] == ["a", "c"]


def test_rank_orders_proven_first_and_caps():
    cs = [_mc(f"m{i}", "untested") for i in range(15)]
    cs.insert(7, _mc("PROVEN", "proven"))
    cs.insert(3, _mc("LIKELY", "likely"))
    ranked = rank_provider_models(cs, n=5)
    assert ranked[0].spec == "PROVEN"
    assert ranked[1].spec == "LIKELY"
    assert len(ranked) == 5


def test_rank_is_base_models_only_no_effort_rows():
    base = ModelChoice(spec="cursor:claude-opus-4-8", executor="cursor", provider="claude",
                       model="claude-opus-4-8", label="Opus 4.8", cost_class="metered-unknown",
                       headless_status="likely", efforts=["low", "medium", "high"], default_effort="high")
    ranked = rank_provider_models([base], n=12)
    assert len(ranked) == 1 and ranked[0].efforts == ["low", "medium", "high"]
