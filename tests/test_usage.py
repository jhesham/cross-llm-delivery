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


def test_renders_combined_markdown_table():
    led = _Ledger([
        _Entry("T1", "gemini:gemini-3.1-pro-preview", {"total": 100}, 0.0),
        _Entry("T2", "opencode/claude-sonnet-4-6", {"total": 250}, 0.03),
    ])
    out = render_usage_table(led, {"total_cost": 5.64, "input": "1.3M"})
    assert "T1" in out and "T2" in out
    assert "gemini:gemini-3.1-pro-preview" in out and "opencode/claude-sonnet-4-6" in out
    assert "350" in out          # build-total tokens (100 + 250)
    assert "5.64" in out         # the opencode account aggregate
    assert "|" in out            # markdown table
    out.encode("cp1252")         # Windows-console-safe


def test_degraded_when_opencode_stats_missing():
    led = _Ledger([_Entry("T1", "gemini:gemini-3.1-pro-preview", {"total": 100})])
    out = render_usage_table(led, {})   # no opencode stats
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
    # build WITH a cursor slice -> Cursor account block present
    out = render_usage_table(_L([_E("T1", "cursor:composer-2.5", {"total": 50})]),
                             {}, cursor_about={"tier": "Pro", "model": "Composer 2.5"})
    assert "Cursor account" in out and "Pro" in out
    assert "/usage" in out or "cursor.com" in out  # server-side pointer
    out.encode("cp1252")  # ascii-safe
    # gemini-only build -> NO cursor block
    out2 = render_usage_table(_L([_E("T2", "gemini:gemini-3.1-pro-preview", {"total": 9})]),
                              {}, cursor_about={"tier": "Pro", "model": "Composer 2.5"})
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
    out = render_usage_table(L([
        E("S1", "gemini:gemini-3.1-pro-preview", {"total": 100}, 0.0, "standard", "workhorse"),
        E("S2", "opencode:opencode/deepseek-v4-pro", {"total": 50}, 0.01, "complex", "orchestrator"),
    ]), {})
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
    out = render_usage_table(L([E()]), {})
    assert "X" in out
    out.encode("cp1252")


