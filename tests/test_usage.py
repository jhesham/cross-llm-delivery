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


def test_usage_nests_subslices_under_parent():
    from cld.usage import render_usage_table
    class E:
        def __init__(s, sid, model, tu, cost=None):
            s.slice_id, s.model, s.token_usage, s.cost = sid, model, tu, cost
    class L:
        def __init__(s, e): s._e = {x.slice_id: x for x in e}
        @property
        def entries(s): return s._e
    out = render_usage_table(L([
        E("P", "gemini:gemini-3.1-pro-preview", {"total": 0}),
        E("P/Pa", "cursor:composer-2.5", {"total": 50}, 0.0),
        E("P/Pb", "opencode:opencode/deepseek-v4-pro", {"total": 80}, 0.01),
    ]), {})
    # child rows present and recognizable as children of P
    assert "P/Pa" in out and "P/Pb" in out
    assert "cursor:composer-2.5" in out and "opencode:opencode/deepseek-v4-pro" in out
    # build total includes children
    assert "130" in out  # 50 + 80 (+0)
    # a parent's children render AFTER the parent row and BEFORE any later top-level slice
    pos_parent = out.index("| P |")
    pos_pa = out.index("P/Pa")
    pos_pb = out.index("P/Pb")
    assert pos_parent < pos_pa < pos_pb


def test_usage_nesting_robust_to_out_of_order_entries():
    # Children inserted BEFORE the parent (and interleaved with another slice) must
    # still group under their parent, not rely on accidental insertion order.
    from cld.usage import render_usage_table
    class E:
        def __init__(s, sid, model, tu, cost=None):
            s.slice_id, s.model, s.token_usage, s.cost = sid, model, tu, cost
    class L:
        def __init__(s, e): s._e = {x.slice_id: x for x in e}
        @property
        def entries(s): return s._e
    out = render_usage_table(L([
        E("P/Pb", "gemini:gemini-3.1-pro-preview", {"total": 80}),  # child first
        E("Q", "gemini:gemini-3.1-pro-preview", {"total": 5}),      # other top-level
        E("P", "gemini:gemini-3.1-pro-preview", {"total": 0}),      # parent later
        E("P/Pa", "cursor:composer-2.5", {"total": 50}),
    ]), {})
    pos_parent = out.index("| P |")
    pos_pa = out.index("P/Pa")
    pos_pb = out.index("P/Pb")
    # both children follow the parent regardless of insertion order
    assert pos_parent < pos_pa and pos_parent < pos_pb
    assert "135" in out  # 80 + 5 + 0 + 50 -> total counts every entry


def test_usage_orphan_child_without_parent_still_rendered():
    # A child key whose parent isn't in the ledger must still appear (no crash, no drop).
    from cld.usage import render_usage_table
    class E:
        def __init__(s, sid, model, tu, cost=None):
            s.slice_id, s.model, s.token_usage, s.cost = sid, model, tu, cost
    class L:
        def __init__(s, e): s._e = {x.slice_id: x for x in e}
        @property
        def entries(s): return s._e
    out = render_usage_table(L([
        E("X/Xa", "gemini:gemini-3.1-pro-preview", {"total": 7}),
    ]), {})
    assert "X/Xa" in out and "7" in out
