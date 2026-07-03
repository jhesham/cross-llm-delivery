"""Model catalog + list_models (the picker's data layer).

MODEL_METADATA is curated human-authored data (refreshed by evidence, not scraped).
list_models parses `opencode models` via an injected runner. recommend() (T7) filters
+ buckets + annotates for the picker.
"""

from cld.models import MODEL_METADATA, ModelInfo, list_models


def test_metadata_has_opencode_gemini_workhorse():
    # OpenCode also fronts gemini-3.1-pro (via OpenCode's account, NOT the flat-rate
    # Google AI Pro sub) -> a workhorse option, but metered, not flat, and not yet
    # verified through OpenCode's harness.
    g = MODEL_METADATA["opencode/gemini-3.1-pro"]
    assert g.capability_class == "workhorse"
    assert g.cost_class != "flat"        # not the flat-rate sub
    assert g.headless_status in ("likely", "untested")


def test_metadata_has_seed_workhorse():
    # the default flat-rate workhorse is antigravity's Gemini 3.1 Pro (High)
    g = MODEL_METADATA["antigravity:Gemini 3.1 Pro (High)"]
    assert g.cost_class == "flat"
    assert g.capability_class == "workhorse"
    assert g.headless_status == "verified"


def test_metadata_entries_are_modelinfo():
    assert all(isinstance(v, ModelInfo) for v in MODEL_METADATA.values())
    # every entry carries the picker-relevant axes
    for info in MODEL_METADATA.values():
        assert info.cost_class in ("free", "flat", "cheap-metered", "premium-metered")
        assert info.capability_class in ("workhorse", "heavy", "quick")
        assert info.headless_status in ("verified", "likely", "untested", "revalidate")


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
        "antigravity:Gemini 3.1 Pro (High)",  # flat-rate workhorse (default)
        "opencode/claude-opus-4-8",           # premium -> confirm_cost
        "opencode/deepseek-v4-flash-free",    # free / untested
    ])


def test_pick_executor_default_on_empty_input():
    # pressing enter selects the default (flat-rate workhorse) -> antigravity spec
    out = []
    spec = pick_executor(_recs_for_picker(), input_fn=lambda _: "", output_fn=out.append)
    assert spec == "antigravity:Gemini 3.1 Pro (High)"
    # the shortlist was actually shown
    shown = "\n".join(out)
    assert "deepseek" in shown and "claude-opus" in shown
    assert "default" in shown.lower()


def test_pick_executor_numeric_choice_maps_to_opencode_spec():
    from cld.models import render_shortlist
    recs = _recs_for_picker()
    # find the shortlist index (1-based) of deepseek in the bucket-ordered list
    _, ordered = render_shortlist(recs)
    idx = next(i for i, r in enumerate(ordered, 1) if "deepseek-v4-flash-free" in r.id)
    spec = pick_executor(recs, input_fn=lambda _: str(idx), output_fn=lambda _s: None)
    assert spec == "opencode:opencode/deepseek-v4-flash-free"


def test_pick_executor_premium_requires_confirmation():
    from cld.models import render_shortlist
    recs = _recs_for_picker()
    # find the shortlist index (1-based) of the premium model in the bucket-ordered list
    _, ordered = render_shortlist(recs)
    idx = next(i for i, r in enumerate(ordered, 1) if "claude-opus-4-8" in r.id)
    # first prompt: pick the premium model; second prompt (confirm): "n" -> declines,
    # falls back to the default workhorse rather than dispatching a billed model.
    answers = iter([str(idx), "n"])
    out = []
    spec = pick_executor(recs, input_fn=lambda _: next(answers), output_fn=out.append)
    assert spec == "antigravity:Gemini 3.1 Pro (High)"  # declined -> default
    assert any("bill" in line.lower() or "$" in line for line in out)  # warned about cost


def test_render_chat_picker_is_complete_dialog():
    # The agent-surface picker MUST be a single helper that emits the WHOLE dialog so
    # the agent can't hand-assemble it wrong (a live-build failure: shortlist + Other
    # but no 'Browse all models...'). render_chat_picker returns the verbatim shortlist
    # PLUS a numbered 'Browse all models...' PLUS a numbered 'Other' escape hatch.
    from cld.models import render_chat_picker, render_shortlist
    recs = _recs_for_picker()
    text = render_chat_picker(recs)
    # 1) contains the shortlist verbatim
    short_lines, ordered = render_shortlist(recs)
    for line in short_lines:
        assert line in text
    # 2) contains the literal Browse-all entry (the thing the agent dropped)
    assert "Browse all models" in text
    # 3) contains an Other / free-text escape hatch
    assert "Other" in text
    # 4) Browse-all and Other are numbered AFTER the shortlist options (continuing the count)
    n_short = len(ordered)
    assert f"{n_short + 1})" in text   # Browse all = next number
    assert f"{n_short + 2})" in text   # Other = number after that
    # 5) Browse comes before Other in the dialog
    assert text.index("Browse all models") < text.index("Other")
    # 6) cp1252-safe (Windows console / chat)
    text.encode("cp1252")


def test_render_chat_picker_returns_str():
    from cld.models import render_chat_picker
    assert isinstance(render_chat_picker(_recs_for_picker()), str)


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
    from cld.models import render_shortlist
    recs = _recs_for_picker()
    # find the shortlist index (1-based) of the premium model in the bucket-ordered list
    _, ordered = render_shortlist(recs)
    idx = next(i for i, r in enumerate(ordered, 1) if "claude-opus-4-8" in r.id)
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
        assert r.headless_status in ("verified", "likely", "untested")  # never revalidate
        if r.headless_status == "untested":
            assert r.warning  # untested carries a warning
        assert r.cost_class   # cost always annotated
        assert r.why          # one-line rationale present


def test_recommend_always_includes_verified_default_even_if_unavailable():
    # BUG (found in live skill test): passing only `opencode models` ids excludes
    # the default workhorse, so the shortlist had NO default/workhorse.
    # recommend() must always surface the default workhorse.
    recs = recommend(available_ids=["opencode/deepseek-v4-flash-free"])  # no antigravity
    ids = [r.id for r in recs]
    assert "antigravity:Gemini 3.1 Pro (High)" in ids
    default = next(r for r in recs if r.is_default)
    assert default.id == "antigravity:Gemini 3.1 Pro (High)"
    assert default.headless_status == "verified"


def test_recommend_default_is_verified_workhorse():
    recs = recommend(available_ids=["antigravity:Gemini 3.1 Pro (High)",
                                    "opencode/deepseek-v4-flash-free"])
    defaults = [r for r in recs if r.is_default]
    assert len(defaults) == 1
    assert defaults[0].capability_class == "workhorse"
    assert defaults[0].headless_status == "verified"  # antigravity workhorse live-validated 2026-06-22


def test_recommend_buckets_and_cost_flags():
    available = ["antigravity:Gemini 3.1 Pro (High)", "opencode/claude-opus-4-8",
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
    # the default is still there and still default
    assert any(r.is_default and r.id == "antigravity:Gemini 3.1 Pro (High)" for r in recs)


def test_recommend_evidence_overlay():
    # a durable verified verdict upgrades a catalogued-untested model (warning cleared)
    recs = recommend(available_ids=["opencode/deepseek-v4-flash-free"],
                     evidence={"opencode/deepseek-v4-flash-free": "verified"})
    ds = next(r for r in recs if "flash-free" in r.id)
    assert ds.headless_status == "verified"
    assert ds.warning == ""
    # a durable revalidate verdict excludes the model from the shortlist
    recs2 = recommend(available_ids=["opencode/deepseek-v4-flash-free"],
                      evidence={"opencode/deepseek-v4-flash-free": "revalidate"})
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
    k27 = MODEL_METADATA["opencode/kimi-k2.7-code"]
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
    assert any(r.is_default and r.id == "antigravity:Gemini 3.1 Pro (High)" for r in recs)


def test_recommend_surfaces_kimi_k27_when_available():
    # When opencode reports k2.7 available, it appears in the shortlist (HEAVY bucket).
    recs = recommend(available_ids=["opencode/kimi-k2.7-code", "opencode/kimi-k2.6"])
    by_id = {r.id: r for r in recs}
    assert "opencode/kimi-k2.7-code" in by_id
    assert by_id["opencode/kimi-k2.7-code"].bucket == "heavy"


def test_kimi_k27_hidden_until_available():
    # Catalogued but NOT in available_ids -> must not surface (no phantom shortlist row).
    recs = recommend(available_ids=["opencode/kimi-k2.6"])
    assert "opencode/kimi-k2.7-code" not in [r.id for r in recs]


def test_cursor_composer_now_in_shortlist_after_validation():
    # Cursor's long-prompt dispatch was a known cursor-agent defect, so Composer used to be
    # excluded from the first-selection shortlist. The direct-node fix is live-validated
    # (2026-06-22), so Composer is now offered normally when it's in available_ids.
    recs = recommend(available_ids=[
        "opencode/kimi-k2.6", "opencode/claude-opus-4-8", "cursor:composer-2.5",
    ])
    cursor_recs = [r for r in recs if r.id == "cursor:composer-2.5"]
    assert len(cursor_recs) == 1
    assert cursor_recs[0].headless_status == "verified"


def test_catalog_uses_verified_not_proven():
    from cld.models import MODEL_METADATA
    # the verified default uses the new vocabulary
    assert MODEL_METADATA["antigravity:Gemini 3.1 Pro (High)"].headless_status == "verified"
    # no entry may carry the old vocabulary
    assert all(m.headless_status != "proven" for m in MODEL_METADATA.values())
    assert all(m.headless_status != "known-bad" for m in MODEL_METADATA.values())


def test_recommend_hides_revalidate_via_evidence():
    from cld.models import recommend
    recs = recommend(
        available_ids=["opencode/deepseek-v4-flash-free"],
        evidence={"opencode/deepseek-v4-flash-free": "revalidate"},
    )
    assert "opencode/deepseek-v4-flash-free" not in [r.id for r in recs]


def test_recommend_default_workhorse_still_resolves():
    from cld.models import recommend
    recs = recommend(available_ids=["antigravity:Gemini 3.1 Pro (High)"])
    assert any(r.is_default and r.headless_status == "verified" for r in recs)


def test_modelinfo_has_tier_and_values_are_valid():
    from cld.models import MODEL_METADATA, TIERS
    assert TIERS == ("quick", "workhorse")
    for info in MODEL_METADATA.values():
        assert info.tier in ("quick", "workhorse", None)


def test_catalog_tier_assignments():
    from cld.models import MODEL_METADATA as M
    assert M["antigravity:Gemini 3.1 Pro (High)"].tier == "workhorse"
    assert M["opencode/deepseek-v4-flash-free"].tier == "quick"
    assert M["opencode/deepseek-v4-pro"].tier == "workhorse"
    assert M["opencode/gemini-3.1-pro"].tier == "workhorse"
    assert M["cursor:composer-2.5"].tier == "workhorse"      # heavy capability, workhorse ROLE
    # premium models are NOT executor tiers (orchestrator domain)
    assert M["opencode/claude-opus-4-8"].tier is None
    assert M["opencode/claude-sonnet-4-6"].tier is None


# ---- T2: resolve_tier_model — cheapest viable model in a provider tier ----

def test_resolve_tier_model_picks_cheapest_viable():
    from cld.models import resolve_tier_model
    # opencode workhorse tier: deepseek-v4-pro + gemini-3.1-pro (both cheap-metered, likely),
    # kimi-k2.6 revalidate (skip). Cheapest-then-id => deepseek-v4-pro.
    spec = resolve_tier_model(
        "opencode", "workhorse",
        evidence={"opencode/kimi-k2.6": "revalidate"},
        available_ids=["opencode/deepseek-v4-pro", "opencode/gemini-3.1-pro", "opencode/kimi-k2.6"],
    )
    assert spec == "opencode:opencode/deepseek-v4-pro"


def test_resolve_tier_model_antigravity_default_always_available():
    from cld.models import resolve_tier_model
    # provider antigravity, workhorse: the flat workhorse resolves even with empty available_ids
    # (antigravity is the default workhorse, so it is always injected into the available set)
    spec = resolve_tier_model("antigravity", "workhorse", evidence={}, available_ids=[])
    assert spec == "antigravity:Gemini 3.1 Pro (High)"


def test_resolve_tier_model_skips_revalidate_returns_none():
    from cld.models import resolve_tier_model
    spec = resolve_tier_model(
        "opencode", "quick",
        evidence={"opencode/deepseek-v4-flash-free": "revalidate"},
        available_ids=["opencode/deepseek-v4-flash-free"],
    )
    assert spec is None    # the only quick model is revalidate -> nothing viable


def test_resolve_tier_model_untested_only_when_nothing_better():
    from cld.models import resolve_tier_model
    # kimi-k2.7 is untested workhorse; with no verified/likely available it's returned
    spec = resolve_tier_model(
        "opencode", "workhorse", evidence={},
        available_ids=["opencode/kimi-k2.7-code"],
    )
    assert spec == "opencode:opencode/kimi-k2.7-code"


# ---- T3: COMPLEXITY_ROUTING + plan_rungs ----

def test_complexity_routing_table():
    from cld.models import COMPLEXITY_ROUTING
    assert COMPLEXITY_ROUTING["easy"] == ("quick", 1)
    assert COMPLEXITY_ROUTING["standard"] == ("workhorse", 2)
    assert COMPLEXITY_ROUTING["complex"] == ("workhorse", 1)


def _task(cid="S", complexity="standard", executor=None):
    from cld.executors.base import SliceTask
    return SliceTask(id=cid, brief="b", files=["x"], acceptance_test_path="t.py",
                     complexity=complexity, executor=executor)


def test_plan_rungs_easy_climbs_quick_then_workhorse():
    from cld.models import plan_rungs
    rungs = plan_rungs(_task(complexity="easy"), provider="opencode", evidence={},
                       available_ids=["opencode/deepseek-v4-flash-free", "opencode/deepseek-v4-pro"])
    assert [r[0] for r in rungs] == ["quick", "workhorse"]
    assert rungs[0][1] == "opencode:opencode/deepseek-v4-flash-free" and rungs[0][2] == 1
    assert rungs[1][1] == "opencode:opencode/deepseek-v4-pro" and rungs[1][2] == 2


def test_plan_rungs_standard_workhorse_only():
    from cld.models import plan_rungs
    rungs = plan_rungs(_task(complexity="standard"), provider="antigravity", evidence={}, available_ids=[])
    assert [r[0] for r in rungs] == ["workhorse"]
    assert rungs[0][1] == "antigravity:Gemini 3.1 Pro (High)" and rungs[0][2] == 2


def test_plan_rungs_complex_workhorse_budget_1():
    from cld.models import plan_rungs
    rungs = plan_rungs(_task(complexity="complex"), provider="antigravity", evidence={}, available_ids=[])
    assert rungs == [("workhorse", "antigravity:Gemini 3.1 Pro (High)", 1)]


def test_plan_rungs_tagged_slice_pins_single_rung():
    from cld.models import plan_rungs
    rungs = plan_rungs(_task(executor="opencode:opencode/claude-opus-4-8"),
                       provider="opencode", evidence={}, available_ids=[], max_retries=2)
    assert rungs == [("workhorse", "opencode:opencode/claude-opus-4-8", 2)]


# ---- T1: render_routing_plan — one-screen per-slice plan table ----

def test_render_routing_plan_basics():
    from cld.models import render_routing_plan
    from cld.executors.base import SliceTask
    slices = [
        SliceTask(id="S1", brief="b", files=["a"], acceptance_test_path="t.py", complexity="easy"),
        SliceTask(id="S2", brief="b", files=["b"], acceptance_test_path="t.py", complexity="complex"),
        SliceTask(id="S3", brief="b", files=["c"], acceptance_test_path="t.py",
                  executor="opencode:opencode/claude-opus-4-8"),   # pinned
    ]
    out = render_routing_plan(slices, provider="antigravity", evidence={}, available_ids=[])
    assert "S1" in out and "S2" in out and "S3" in out
    # easy/standard slices recommend the workhorse for the build provider (antigravity default)
    assert "antigravity:Gemini 3.1 Pro (High)" in out
    # complex slice flagged
    assert "!" in out
    # pinned slice shows its tag + [you]; auto-routed show [rec]
    assert "opencode:opencode/claude-opus-4-8" in out
    assert "[you]" in out and "[rec]" in out
    out.encode("cp1252")   # safe


def test_render_routing_plan_shows_complexity():
    from cld.models import render_routing_plan
    from cld.executors.base import SliceTask
    out = render_routing_plan(
        [SliceTask(id="S1", brief="b", files=["a"], acceptance_test_path="t.py", complexity="easy")],
        provider="antigravity", evidence={}, available_ids=[])
    assert "easy" in out


def test_provider_of_maps_antigravity_to_family():
    from cld.models import _provider_of
    assert _provider_of("antigravity:Gemini 3.1 Pro (High)") == "gemini"
    assert _provider_of("antigravity:Claude Opus 4.6 (Thinking)") == "claude"
    assert _provider_of("antigravity:GPT-OSS 120B (Medium)") == "gpt"
    assert _provider_of("gemini:gemini-3.1-pro-preview") == "gemini"   # unchanged
