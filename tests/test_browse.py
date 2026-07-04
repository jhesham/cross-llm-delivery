"""browse_models: group ALL available ids by provider, annotate from the catalog,
default uncatalogued models to untested, infer cost from the id, self-include the
flat-rate Gemini-CLI workhorse, and honor session known-bad marks."""

from cld.models import DEFAULT_WORKHORSE_ID, BrowseItem, browse_models

IDS = [
    "opencode/claude-opus-4-8",         # catalogued (premium-metered/heavy/likely)
    "opencode/gpt-5.2",                 # uncatalogued -> untested, metered-unknown
    "opencode/deepseek-v4-flash-free",  # catalogued (free/quick/untested)
    "opencode/nemotron-3-ultra-free",   # uncatalogued, -free suffix, unknown provider
    "opencode/gemini-3.1-pro",          # catalogued (cheap-metered/workhorse/likely)
    "opencode/big-pickle",              # uncatalogued, unknown provider -> other
]


def _ids(group):
    return [i.id for i in group]


def test_groups_by_provider_token():
    g = browse_models(IDS)
    assert "opencode/claude-opus-4-8" in _ids(g["claude"])
    assert "opencode/gpt-5.2" in _ids(g["gpt"])
    assert "opencode/deepseek-v4-flash-free" in _ids(g["deepseek"])
    assert "opencode/gemini-3.1-pro" in _ids(g["gemini"])
    # unknown providers collapse into "other"
    assert "opencode/big-pickle" in _ids(g["other"])
    assert "opencode/nemotron-3-ultra-free" in _ids(g["other"])


def test_uncatalogued_default_untested_and_cost_inferred():
    g = browse_models(IDS)
    gpt = next(i for i in g["gpt"] if i.id == "opencode/gpt-5.2")
    assert isinstance(gpt, BrowseItem)
    assert gpt.in_catalog is False
    assert gpt.headless_status == "untested"
    assert gpt.cost_class == "metered-unknown"
    nem = next(i for i in g["other"] if "nemotron" in i.id)
    assert nem.cost_class == "free"  # -free suffix


def test_catalogued_items_copy_metadata():
    g = browse_models(IDS)
    opus = next(i for i in g["claude"] if "opus-4-8" in i.id)
    assert opus.in_catalog is True
    assert opus.cost_class == "premium-metered"
    assert opus.headless_status == "likely"


def test_workhorse_always_self_included():
    g = browse_models([])  # OpenCode down -> still offers the flat-rate workhorse
    assert list(g.keys()) == ["gemini"]
    assert _ids(g["gemini"]) == [DEFAULT_WORKHORSE_ID]
    wh = g["gemini"][0]
    assert wh.in_catalog is True and wh.headless_status == "verified"


def test_group_order_catalogued_first_then_alpha():
    g = browse_models(IDS)
    # claude/deepseek/gemini have catalogued items -> first (alpha);
    # antigravity default now maps to "gemini", so "other" has no in_catalog items,
    # sorting after gpt (both uncatalogued -> alpha order)
    assert list(g.keys()) == ["claude", "deepseek", "gemini", "gpt", "other"]


def test_session_known_bad_filtered_out():
    g = browse_models(IDS, session_known_bad={"opencode/gpt-5.2"})
    assert "gpt" not in g or "opencode/gpt-5.2" not in _ids(g["gpt"])


from cld.models import render_browse_list


def test_render_numbering_round_trips_to_ids():
    lines, ordered = render_browse_list(browse_models(IDS))
    # every numbered line N) contains the spec of ordered[N-1]
    import re
    for ln in lines:
        m = re.match(r"\s*(\d+)\)\s+(.+?)\s{2,}", ln)  # spec ends at 2+ spaces
        if not m:
            continue
        n, spec = int(m.group(1)), m.group(2).strip()
        item = ordered[n - 1]
        # ids that already contain ":" are already spec-shaped (gemini:, antigravity:, etc.)
        expected = item.id if ":" in item.id else f"opencode:{item.id}"
        assert spec == expected


def test_render_marks_untested_and_premium():
    lines, _ = render_browse_list(browse_models(IDS))
    blob = "\n".join(lines)
    assert "(!)" in blob          # untested marker present
    assert "$" in blob            # premium (claude-opus) billed marker
    assert "CLAUDE" in blob       # provider headers


def test_render_is_cp1252_safe():
    lines, _ = render_browse_list(browse_models(IDS))
    "\n".join(lines).encode("cp1252")  # raises on a bad glyph


def test_browse_evidence_overlay_promotes_and_excludes():
    # evidence (durable verdicts) overrides catalog/default status in the browse view
    g = browse_models(IDS, evidence={"opencode/gpt-5.2": "verified"})
    gpt = next(i for i in g["gpt"] if i.id == "opencode/gpt-5.2")
    assert gpt.headless_status == "verified"  # promoted from default untested
    # a revalidate verdict hides the model (same treatment as catalog revalidate)
    g2 = browse_models(IDS, evidence={"opencode/gpt-5.2": "revalidate"})
    assert "gpt" not in g2 or "opencode/gpt-5.2" not in [i.id for i in g2["gpt"]]
