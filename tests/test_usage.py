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


