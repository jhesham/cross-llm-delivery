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
        evidence={"opencode/deepseek-v4-pro": "verified"})
    by_spec = {c.spec: c for c in idx}
    # default workhorse always present (catalog); now antigravity:Gemini 3.1 Pro (High)
    assert "antigravity:Gemini 3.1 Pro (High)" in by_spec
    # opencode ids present, evidence overlay applied
    ds = by_spec["opencode:opencode/deepseek-v4-pro"]
    assert ds.executor == "opencode" and ds.provider == "deepseek"
    assert ds.headless_status == "verified"  # from evidence overlay
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


def test_browse_filter_default_hides_untested_and_revalidate():
    cs = [_mc("a", "verified"), _mc("b", "likely"), _mc("c", "untested"), _mc("d", "revalidate")]
    assert [c.spec for c in browse_filter(cs)] == ["a", "b"]


def test_browse_filter_show_all_keeps_untested_but_not_revalidate():
    cs = [_mc("a", "verified"), _mc("c", "untested"), _mc("d", "revalidate")]
    assert [c.spec for c in browse_filter(cs, headless_only=False)] == ["a", "c"]


def test_rank_orders_verified_first_and_caps():
    cs = [_mc(f"m{i}", "untested") for i in range(15)]
    cs.insert(7, _mc("VERIFIED", "verified"))
    cs.insert(3, _mc("LIKELY", "likely"))
    ranked = rank_provider_models(cs, n=5)
    assert ranked[0].spec == "VERIFIED"
    assert ranked[1].spec == "LIKELY"
    assert len(ranked) == 5


def test_rank_is_base_models_only_no_effort_rows():
    base = ModelChoice(spec="cursor:claude-opus-4-8", executor="cursor", provider="claude",
                       model="claude-opus-4-8", label="Opus 4.8", cost_class="metered-unknown",
                       headless_status="likely", efforts=["low", "medium", "high"], default_effort="high")
    ranked = rank_provider_models([base], n=12)
    assert len(ranked) == 1 and ranked[0].efforts == ["low", "medium", "high"]


from cld.models import (render_executor_level, render_provider_level,
                        render_model_level, render_effort_level)


def _idx():
    return build_model_index(
        opencode_ids=["opencode/deepseek-v4-pro", "opencode/gpt-5"], cursor_models=[],
        evidence={"opencode/deepseek-v4-pro": "verified"})


def test_executor_level_lists_executors_and_search():
    lines, ordered = render_executor_level(_idx())
    blob = "\n".join(lines)
    assert "antigravity" in blob and "opencode" in blob
    assert any("Search" in l for l in lines)
    assert "antigravity" in ordered and "opencode" in ordered


def test_provider_level_lists_providers_under_executor():
    lines, ordered = render_provider_level(_idx(), executor="opencode")
    assert "deepseek" in ordered and "gpt" in ordered
    assert any("Search" in l for l in lines)


def test_model_level_topN_plus_search():
    lines, ordered = render_model_level(_idx(), executor="opencode", provider="deepseek")
    assert any("deepseek-v4-pro" in l for l in lines)
    assert any("Search" in l for l in lines)
    import re
    for l in lines:
        m = re.match(r"\s*(\d+)\)\s+(\S+)", l)
        if m:
            assert m.group(2) == ordered[int(m.group(1)) - 1].spec


def test_effort_level_only_when_efforts_present():
    base = ModelChoice(spec="cursor:claude-opus-4-8", executor="cursor", provider="claude",
                       model="claude-opus-4-8", label="Opus", cost_class="metered-unknown",
                       headless_status="likely", efforts=["low", "high"], default_effort="high")
    lines, ordered = render_effort_level(base)
    assert ordered == ["low", "high"]
    assert any("high" in l and "default" in l.lower() for l in lines)
    plain = ModelChoice(spec="opencode:opencode/gpt-5", executor="opencode", provider="gpt",
                        model="gpt-5", label="gpt-5", cost_class="metered-unknown",
                        headless_status="untested")
    lines2, ordered2 = render_effort_level(plain)
    assert ordered2 == []


def test_nav_render_cp1252_safe():
    for fn_lines in (render_executor_level(_idx())[0],
                     render_provider_level(_idx(), executor="opencode")[0],
                     render_model_level(_idx(), executor="opencode", provider="gpt")[0]):
        "\n".join(fn_lines).encode("cp1252")


from cld.models import search_models


def test_search_compo_matches_only_via_substring():
    idx = build_model_index(opencode_ids=["opencode/deepseek-v4-pro"],
                            cursor_models=[("composer-2.5", "Composer 2.5")], evidence={})
    res = search_models(idx, "compo", headless_only=False)
    assert any("composer" in c.model.lower() for c in res)
    assert all("composer" in (c.model + c.label).lower() for c in res)


def test_search_31_matches_multiple_routings_labeled():
    idx = build_model_index(opencode_ids=["opencode/gemini-3.1-pro"], cursor_models=[], evidence={})
    res = search_models(idx, "3.1", headless_only=False)
    specs = {c.spec for c in res}
    # default workhorse is now antigravity:Gemini 3.1 Pro (High); search for "3.1" matches it
    assert "antigravity:Gemini 3.1 Pro (High)" in specs
    assert "opencode:opencode/gemini-3.1-pro" in specs
    assert {c.executor for c in res} >= {"antigravity", "opencode"}


def test_search_respects_headless_filter_and_empty():
    idx = build_model_index(opencode_ids=["opencode/gpt-5"], cursor_models=[], evidence={})
    assert search_models(idx, "gpt-5", headless_only=True) == []   # untested hidden
    assert search_models(idx, "zzz-nomatch", headless_only=False) == []


from cld.models import spec_with_effort, ModelChoice


def test_spec_with_effort_appends_at_marker():
    base = ModelChoice(spec="cursor:claude-opus-4-8", executor="cursor", provider="claude",
                       model="claude-opus-4-8", label="Opus", cost_class="metered-unknown",
                       headless_status="likely", efforts=["low", "medium"], default_effort="medium")
    assert spec_with_effort(base, "low") == "cursor:claude-opus-4-8@low"
    # choosing the default effort omits the @marker (= CLI default)
    assert spec_with_effort(base, "medium") == "cursor:claude-opus-4-8"
    # no effort / None -> bare spec
    assert spec_with_effort(base, None) == "cursor:claude-opus-4-8"


from cld.models import list_cursor_models

_CUR_RAW = """auto - Auto
claude-opus-4-8-low - Opus 4.8 Low
claude-opus-4-8-medium - Opus 4.8 Medium
claude-opus-4-8-high - Opus 4.8
composer-2.5 - Composer 2.5 (current)
composer-2.5-fast - Composer 2.5 Fast (default)
"""


def test_list_cursor_models_parses_id_label():
    models = list_cursor_models(runner=lambda a, c: (0, _CUR_RAW))
    ids = [m[0] for m in models]
    assert "claude-opus-4-8-high" in ids and "composer-2.5" in ids
    assert "auto" not in ids  # auto is skipped
    # returns (id, label) tuples
    assert any(i == "composer-2.5" and "Composer 2.5" in lbl for i, lbl in models)


def test_list_cursor_models_empty_on_failure():
    assert list_cursor_models(runner=lambda a, c: (1, "")) == []


def test_index_groups_cursor_efforts_into_base():
    models = list_cursor_models(runner=lambda a, c: (0, _CUR_RAW))
    idx = build_model_index(opencode_ids=[], cursor_models=models, evidence={})
    opus = [c for c in idx if c.executor == "cursor" and c.model == "claude-opus-4-8"]
    assert len(opus) == 1                       # ONE base entry, not 3
    assert set(opus[0].efforts) >= {"low", "medium", "high"}
    assert opus[0].default_effort == "high"     # the plain/unlabeled "Opus 4.8" is the default


from cld.models import resolve_composer_default


def test_resolve_composer_prefers_current():
    raw = ("composer-2.5 - Composer 2.5 (current)\n"
           "composer-2.5-fast - Composer 2.5 Fast (default)\n")
    assert resolve_composer_default(runner=lambda a, c: (0, raw)) == "composer-2.5"


def test_resolve_composer_falls_back_to_static_on_empty():
    assert resolve_composer_default(runner=lambda a, c: (1, "")) == "composer-2.5"


def test_composer_in_catalog_and_spec_for_passthrough():
    from cld.models import MODEL_METADATA, _spec_for
    assert "cursor:composer-2.5" in MODEL_METADATA
    entry = MODEL_METADATA["cursor:composer-2.5"]
    assert entry.cost_class == "cheap-metered"
    assert entry.headless_status == "verified"  # direct-node dispatch live-validated 2026-06-22

    class _C:
        id = "cursor:composer-2.5"
    assert _spec_for(_C()) == "cursor:composer-2.5"  # already spec-shaped -> unchanged
