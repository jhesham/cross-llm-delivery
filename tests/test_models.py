"""Model catalog + list_models (the picker's data layer).

MODEL_METADATA is curated human-authored data (refreshed by evidence, not scraped).
list_models parses `opencode models` via an injected runner. recommend() (T7) filters
+ buckets + annotates for the picker.
"""

from cld.models import MODEL_METADATA, ModelInfo, list_models


def test_metadata_has_opencode_gemini_workhorse():
    # OpenCode also fronts gemini-3.1-pro (via OpenCode's account, NOT the flat-rate
    # Google AI Pro sub) -> a workhorse option, but metered, not flat, and not yet
    # proven through OpenCode's harness.
    g = MODEL_METADATA["opencode/gemini-3.1-pro"]
    assert g.capability_class == "workhorse"
    assert g.cost_class != "flat"        # not the flat-rate sub
    assert g.headless_status in ("likely", "untested")


def test_metadata_has_seed_workhorse():
    # the proven flat-rate workhorse must be present and tagged correctly
    g = MODEL_METADATA["gemini:gemini-3.1-pro-preview"]
    assert g.cost_class == "flat"
    assert g.capability_class == "workhorse"
    assert g.headless_status == "proven"


def test_metadata_entries_are_modelinfo():
    assert all(isinstance(v, ModelInfo) for v in MODEL_METADATA.values())
    # every entry carries the picker-relevant axes
    for info in MODEL_METADATA.values():
        assert info.cost_class in ("free", "flat", "cheap-metered", "premium-metered")
        assert info.capability_class in ("workhorse", "heavy", "quick")
        assert info.headless_status in ("proven", "likely", "untested", "known-bad")


def test_list_models_parses_opencode_output():
    def fake_runner(args, cwd):
        assert "models" in args
        return (0, "opencode/gemini-3.1-pro\nopencode/claude-opus-4-8\n"
                   "opencode/deepseek-v4-flash-free\n")

    ids = list_models(runner=fake_runner)
    assert "opencode/gemini-3.1-pro" in ids
    assert "opencode/deepseek-v4-flash-free" in ids
    assert len(ids) == 3


def test_list_models_empty_on_failure():
    def boom(args, cwd):
        return (1, "opencode not found")

    assert list_models(runner=boom) == []


def test_list_models_resolves_platform_command(monkeypatch):
    # On Windows the npm shim is opencode.cmd; bare "opencode" raises WinError 2.
    # list_models must invoke the platform-correct command, not bare "opencode".
    import cld.models as m
    monkeypatch.setattr(m.os, "name", "nt", raising=False)
    seen = {}

    def fake_runner(args, cwd):
        seen["cmd"] = args[0]
        return (0, "opencode/gemini-3.1-pro\n")

    m.list_models(runner=fake_runner)
    assert seen["cmd"] in ("opencode.cmd", "opencode")  # resolved, platform-aware


def test_list_models_survives_missing_cli():
    # The real default runner raises FileNotFoundError when the CLI isn't on PATH;
    # list_models must degrade to [] (picker -> "Gemini only"), never crash.
    def raising(args, cwd):
        raise FileNotFoundError("[WinError 2] cannot find opencode")

    assert list_models(runner=raising) == []


# ---- interactive picker (the CLI prompt surface) ----

from cld.models import pick_executor


def _recs_for_picker():
    return recommend(available_ids=[
        "gemini:gemini-3.1-pro-preview",      # proven workhorse (default)
        "opencode/claude-opus-4-8",           # premium -> confirm_cost
        "opencode/deepseek-v4-flash-free",    # free / untested
    ])


def test_pick_executor_default_on_empty_input():
    # pressing enter selects the default (proven workhorse) -> gemini spec
    out = []
    spec = pick_executor(_recs_for_picker(), input_fn=lambda _: "", output_fn=out.append)
    assert spec == "gemini:gemini-3.1-pro-preview"
    # the shortlist was actually shown
    shown = "\n".join(out)
    assert "deepseek" in shown and "claude-opus" in shown
    assert "default" in shown.lower()


def test_pick_executor_numeric_choice_maps_to_opencode_spec():
    recs = _recs_for_picker()
    # choose the deepseek free line by its number; find its index (1-based)
    idx = next(i for i, r in enumerate(recs, 1) if "deepseek-v4-flash-free" in r.id)
    spec = pick_executor(recs, input_fn=lambda _: str(idx), output_fn=lambda _s: None)
    assert spec == "opencode:opencode/deepseek-v4-flash-free"


def test_pick_executor_premium_requires_confirmation():
    recs = _recs_for_picker()
    idx = next(i for i, r in enumerate(recs, 1) if "claude-opus-4-8" in r.id)
    # first prompt: pick the premium model; second prompt (confirm): "n" -> declines,
    # falls back to the default workhorse rather than dispatching a billed model.
    answers = iter([str(idx), "n"])
    out = []
    spec = pick_executor(recs, input_fn=lambda _: next(answers), output_fn=out.append)
    assert spec == "gemini:gemini-3.1-pro-preview"  # declined -> default
    assert any("bill" in line.lower() or "$" in line for line in out)  # warned about cost


def test_picker_output_is_windows_console_safe():
    # The picker must not emit non-cp1252 chars (e.g. the warning glyph) or it
    # crashes on the default Windows console. All output must encode to cp1252.
    from cld.models import render_shortlist
    recs = _recs_for_picker()
    lines, _ = render_shortlist(recs)
    blob = "\n".join(lines)
    blob.encode("cp1252")  # raises UnicodeEncodeError on a bad glyph
    # also the cost-confirm and warning prompt strings
    out = []
    answers = iter(["x", ""])  # bad choice -> falls to default; no second prompt
    pick_executor(recs, input_fn=lambda _: next(answers, ""), output_fn=out.append)
    "\n".join(out).encode("cp1252")


def test_pick_executor_premium_confirmed_yes():
    recs = _recs_for_picker()
    idx = next(i for i, r in enumerate(recs, 1) if "claude-opus-4-8" in r.id)
    answers = iter([str(idx), "y"])
    spec = pick_executor(recs, input_fn=lambda _: next(answers), output_fn=lambda _s: None)
    assert spec == "opencode:opencode/claude-opus-4-8"


# ---- T7: recommend() — filter / bucket / annotate for the picker ----

from cld.models import recommend, Recommendation


def test_recommend_filters_to_available_and_catalogued():
    available = ["opencode/deepseek-v4-flash-free", "opencode/claude-opus-4-8",
                 "opencode/some-unknown-model"]
    recs = recommend(available_ids=available)
    ids = [r.id for r in recs]
    # only models that are BOTH in available AND in our curated catalog appear
    assert "opencode/some-unknown-model" not in ids
    for r in recs:
        assert r.headless_status in ("proven", "likely", "untested")  # never known-bad
        if r.headless_status == "untested":
            assert r.warning  # untested carries a warning
        assert r.cost_class   # cost always annotated
        assert r.why          # one-line rationale present


def test_recommend_always_includes_proven_default_even_if_unavailable():
    # BUG (found in live skill test): passing only `opencode models` ids excludes
    # gemini:gemini-3.1-pro-preview, so the shortlist had NO default/workhorse.
    # recommend() must always surface the proven default workhorse.
    recs = recommend(available_ids=["opencode/deepseek-v4-flash-free"])  # no gemini
    ids = [r.id for r in recs]
    assert "gemini:gemini-3.1-pro-preview" in ids
    default = next(r for r in recs if r.is_default)
    assert default.id == "gemini:gemini-3.1-pro-preview"
    assert default.headless_status == "proven"


def test_recommend_default_is_proven_workhorse():
    recs = recommend(available_ids=["gemini:gemini-3.1-pro-preview",
                                    "opencode/deepseek-v4-flash-free"])
    defaults = [r for r in recs if r.is_default]
    assert len(defaults) == 1
    assert defaults[0].capability_class == "workhorse"
    assert defaults[0].headless_status == "proven"


def test_recommend_buckets_and_cost_flags():
    available = ["gemini:gemini-3.1-pro-preview", "opencode/claude-opus-4-8",
                 "opencode/deepseek-v4-flash-free"]
    recs = recommend(available_ids=available)
    buckets = {r.bucket for r in recs}
    assert "workhorse" in buckets
    # premium model is flagged for cost confirmation
    opus = next((r for r in recs if "opus" in r.id), None)
    assert opus is not None
    assert opus.cost_class == "premium-metered"
    assert opus.confirm_cost is True
    # free model does NOT require cost confirmation
    free = next((r for r in recs if "free" in r.id), None)
    assert free is not None
    assert free.confirm_cost is False


def test_recommend_hides_session_known_bad():
    # a model that failed validation this session is hidden on re-present
    recs = recommend(
        available_ids=["opencode/deepseek-v4-flash-free", "opencode/claude-opus-4-8"],
        session_known_bad={"opencode/deepseek-v4-flash-free"},
    )
    ids = [r.id for r in recs]
    assert "opencode/deepseek-v4-flash-free" not in ids
    assert "opencode/claude-opus-4-8" in ids
    # the proven default is still there and still default
    assert any(r.is_default and r.id == "gemini:gemini-3.1-pro-preview" for r in recs)


def test_recommend_evidence_overlay():
    # a durable proven verdict upgrades a catalogued-untested model (warning cleared)
    recs = recommend(available_ids=["opencode/deepseek-v4-flash-free"],
                     evidence={"opencode/deepseek-v4-flash-free": "proven"})
    ds = next(r for r in recs if "flash-free" in r.id)
    assert ds.headless_status == "proven"
    assert ds.warning == ""
    # a durable known-bad verdict excludes the model from the shortlist
    recs2 = recommend(available_ids=["opencode/deepseek-v4-flash-free"],
                      evidence={"opencode/deepseek-v4-flash-free": "known-bad"})
    assert all("flash-free" not in r.id for r in recs2)


def test_catalog_has_kimi_and_sonnet_shortlist_entries():
    # Picker main shortlist additions. kimi-k2.6 + claude-sonnet-4-6 verified live;
    # kimi-k2.7 catalogued AHEAD of availability (not yet on this opencode plan) — it
    # stays filtered out of the shortlist until `opencode models` lists it (see
    # test_kimi_k27_hidden_until_available / test_recommend_surfaces_kimi_k27).
    kimi = MODEL_METADATA["opencode/kimi-k2.6"]
    assert kimi.capability_class == "heavy"
    assert kimi.cost_class == "cheap-metered"
    assert kimi.headless_status == "untested"   # never cleanly validated -> validate-first

    sonnet = MODEL_METADATA["opencode/claude-sonnet-4-6"]
    assert sonnet.capability_class == "heavy"
    assert sonnet.cost_class == "premium-metered"
    assert sonnet.headless_status == "likely"


def test_catalog_has_kimi_k27_entry_mirroring_k26():
    k27 = MODEL_METADATA["opencode/kimi-k2.7"]
    assert k27.capability_class == "heavy"
    assert k27.cost_class == "cheap-metered"
    assert k27.headless_status == "untested"   # validate-first until proven


def test_recommend_surfaces_kimi_and_sonnet():
    recs = recommend(available_ids=[
        "opencode/kimi-k2.6", "opencode/claude-sonnet-4-6", "opencode/gemini-3.1-pro",
    ])
    ids = [r.id for r in recs]
    assert "opencode/kimi-k2.6" in ids
    assert "opencode/claude-sonnet-4-6" in ids
    assert any(r.is_default and r.id == "gemini:gemini-3.1-pro-preview" for r in recs)


def test_recommend_surfaces_kimi_k27_when_available():
    # When opencode reports k2.7 available, it appears in the shortlist (HEAVY bucket).
    recs = recommend(available_ids=["opencode/kimi-k2.7", "opencode/kimi-k2.6"])
    by_id = {r.id: r for r in recs}
    assert "opencode/kimi-k2.7" in by_id
    assert by_id["opencode/kimi-k2.7"].bucket == "heavy"


def test_kimi_k27_hidden_until_available():
    # Catalogued but NOT in available_ids -> must not surface (no phantom shortlist row).
    recs = recommend(available_ids=["opencode/kimi-k2.6"])
    assert "opencode/kimi-k2.7" not in [r.id for r in recs]


def test_cursor_composer_never_in_first_shortlist():
    # Cursor models never come through `opencode models`, so even though Composer is in
    # the catalog it must never reach the first-selection shortlist (its long-prompt
    # dispatch is a known cursor-agent defect; it lives only in the Browse drill-down).
    recs = recommend(available_ids=[
        "opencode/kimi-k2.6", "opencode/claude-opus-4-8", "cursor:composer-2.5",
    ])
    assert "cursor:composer-2.5" not in [r.id for r in recs]
