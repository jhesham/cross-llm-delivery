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
