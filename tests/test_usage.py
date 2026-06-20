from cld.usage import parse_opencode_stats

# the real `opencode stats` box-drawing output (a trimmed, representative sample)
SAMPLE = """
|                    COST & TOKENS                       |
|Total Cost                                        $5.64 |
|Input                                              1.3M |
|Output                                            70.7K |
"""


def test_parses_total_cost_and_tokens():
    s = parse_opencode_stats(SAMPLE)
    assert s["total_cost"] == 5.64
    assert s["input"] == "1.3M"      # keep human strings as-is (display)
    assert s["output"] == "70.7K"


def test_unparseable_returns_empty_dict():
    assert parse_opencode_stats("") == {}
    assert parse_opencode_stats("garbage with no fields") == {}


from cld.usage import render_usage_table


class _Entry:
    def __init__(self, sid, model, tu, cost=None):
        self.slice_id, self.model, self.token_usage, self.cost = sid, model, tu, cost


class _Ledger:
    def __init__(self, entries): self._e = {e.slice_id: e for e in entries}
    @property
    def entries(self): return self._e


# ---------------------------------------------------------------------------
# Helpers for fake provider registration
# ---------------------------------------------------------------------------

def _make_fake_provider(name, account_section_fn=None, catalog=()):
    """Build a minimal fake Provider for use in usage tests."""
    from cld.providers_api import Provider

    def _noop_make_executor(**k):
        raise NotImplementedError

    def _noop_list_models(runner):
        return []

    return Provider(
        name=name,
        make_executor=_noop_make_executor,
        catalog=catalog,
        default_workhorse=f"{name}:default",
        list_models=_noop_list_models,
        account_stats=None,
        account_block=None,
        account_section=account_section_fn,
        skill_fragment="",
        setup_notes="",
    )


def _setup_fake_registry(*providers):
    """Clear registry and register *providers*; returns the old registry dict snapshot."""
    from cld.providers_api import _REGISTRY, register_provider
    snapshot = dict(_REGISTRY)
    _REGISTRY.clear()
    for p in providers:
        register_provider(p)
    return snapshot


def _restore_registry(snapshot):
    from cld.providers_api import _REGISTRY
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)


import contextlib
from unittest.mock import patch


@contextlib.contextmanager
def _fake_providers(*providers):
    """Context manager: seed the registry with fake providers and suppress load_providers()."""
    snap = _setup_fake_registry(*providers)
    with patch("cld.providers_api.load_providers"):  # prevent real providers from overwriting fakes
        try:
            yield
        finally:
            _restore_registry(snap)


# ---------------------------------------------------------------------------
# render_usage_table tests (provider-blind: register fake providers)
# ---------------------------------------------------------------------------

def test_renders_combined_markdown_table():
    # opencode account_section returns cost block for this build
    oc_section = lambda: ["## OpenCode account", "Total cost: $5.64", "Input: 1.3M"]
    with _fake_providers(_make_fake_provider("opencode", account_section_fn=oc_section)):
        led = _Ledger([
            _Entry("T1", "gemini:gemini-3.1-pro-preview", {"total": 100}, 0.0),
            _Entry("T2", "opencode/claude-sonnet-4-6", {"total": 250}, 0.03),
        ])
        out = render_usage_table(led)
        assert "T1" in out and "T2" in out
        assert "gemini:gemini-3.1-pro-preview" in out and "opencode/claude-sonnet-4-6" in out
        assert "350" in out          # build-total tokens (100 + 250)
        assert "5.64" in out         # the opencode account aggregate
        assert "|" in out            # markdown table
        out.encode("cp1252")         # Windows-console-safe


def test_degraded_when_opencode_stats_missing():
    # opencode account_section returns "unavailable" block (mirrors real behaviour when stats fail)
    oc_section = lambda: ["## OpenCode account", "OpenCode stats unavailable"]
    with _fake_providers(_make_fake_provider("opencode", account_section_fn=oc_section)):
        led = _Ledger([_Entry("T1", "opencode/deepseek-v4-pro", {"total": 100})])
        out = render_usage_table(led)
        assert "T1" in out
        assert "unavailable" in out.lower()  # notes OpenCode stats missing, doesn't crash


from cld.usage import parse_cursor_about


CUR_ABOUT = """About Cursor CLI
CLI Version 2026.06.12
Model Composer 2.5 Fast
Subscription Tier Pro
User Email x@y.z
"""


def test_parse_cursor_about():
    a = parse_cursor_about(CUR_ABOUT)
    assert a["tier"] == "Pro"
    assert "Composer" in a["model"]


def test_parse_cursor_about_empty():
    assert parse_cursor_about("") == {}


class _E:
    def __init__(self, sid, model, tu, cost=None):
        self.slice_id, self.model, self.token_usage, self.cost = sid, model, tu, cost


class _L:
    def __init__(self, e): self._e = {x.slice_id: x for x in e}
    @property
    def entries(self): return self._e


def test_cursor_block_only_when_cursor_slice_present():
    cur_section = lambda: [
        "## Cursor account",
        "Tier: Pro   Default model: Composer 2.5",
        "Token/cost totals are server-side - run /usage in the Cursor TUI or see cursor.com.",
    ]
    with _fake_providers(_make_fake_provider("cursor", account_section_fn=cur_section)):
        # build WITH a cursor slice -> Cursor account block present
        out = render_usage_table(_L([_E("T1", "cursor:composer-2.5", {"total": 50})]))
        assert "Cursor account" in out and "Pro" in out
        assert "/usage" in out or "cursor.com" in out  # server-side pointer
        out.encode("cp1252")  # ascii-safe
        # gemini-only build -> NO cursor block (cursor provider not matched)
        out2 = render_usage_table(_L([_E("T2", "gemini:gemini-3.1-pro-preview", {"total": 9})]))
        assert "Cursor account" not in out2


def test_usage_table_has_complexity_and_rung_columns():
    from cld.usage import render_usage_table
    class E:
        def __init__(s, sid, model, tu, cost=None, complexity=None, final_rung=None):
            s.slice_id, s.model, s.token_usage, s.cost = sid, model, tu, cost
            s.complexity, s.final_rung = complexity, final_rung
    class L:
        def __init__(s, e): s._e = {x.slice_id: x for x in e}
        @property
        def entries(s): return s._e

    with _fake_providers(_make_fake_provider("opencode")):
        out = render_usage_table(L([
            E("S1", "gemini:gemini-3.1-pro-preview", {"total": 100}, 0.0, "standard", "workhorse"),
            E("S2", "opencode:opencode/deepseek-v4-pro", {"total": 50}, 0.01, "complex", "orchestrator"),
        ]))
        assert "Complexity" in out and "Rung" in out
        assert "standard" in out and "workhorse" in out
        assert "complex" in out and "orchestrator" in out
        assert "150" in out          # build total tokens
        out.encode("cp1252")


def test_usage_account_blocks_are_separate_helpers():
    from cld.usage import opencode_account_block, cursor_account_block
    oc = opencode_account_block({"total_cost": 5.64, "input": "1.3M"})
    assert any("5.64" in ln for ln in oc)
    cur = cursor_account_block({"tier": "Pro", "model": "Composer 2.5"})
    assert any("Pro" in ln for ln in cur)


def test_usage_handles_missing_routing_fields_gracefully():
    # entries without complexity/final_rung (older builds) render with a placeholder, no crash
    from cld.usage import render_usage_table
    class E:
        def __init__(s):
            s.slice_id, s.model, s.token_usage, s.cost = "X", "gemini:gemini-3.1-pro-preview", {"total": 1}, None
            s.complexity = None; s.final_rung = None
    class L:
        def __init__(s, e): s._e = {x.slice_id: x for x in e}
        @property
        def entries(s): return s._e

    with _fake_providers():   # empty registry — gemini has no section
        out = render_usage_table(L([E()]))
        assert "X" in out
        out.encode("cp1252")
