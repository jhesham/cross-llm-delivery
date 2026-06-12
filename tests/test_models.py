"""Model catalog + list_models (the picker's data layer).

MODEL_METADATA is curated human-authored data (refreshed by evidence, not scraped).
list_models parses `opencode models` via an injected runner. recommend() (T7) filters
+ buckets + annotates for the picker.
"""

from cld.models import MODEL_METADATA, ModelInfo, list_models


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
