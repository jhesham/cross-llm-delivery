from pathlib import Path

from cld.executors.cursor import parse_cursor_usage

_SAMPLE = Path(__file__).resolve().parents[1] / "fixtures" / "cursor-run-sample.json"


def test_parses_real_sample_tokens():
    usage = parse_cursor_usage(_SAMPLE.read_text(encoding="utf-8"))
    # exact counts from the committed live capture (usage.inputTokens/outputTokens)
    assert usage["input"] == 14801
    assert usage["output"] == 37
    assert usage["total"] == 14838   # input + output
    assert all(isinstance(v, int) for v in usage.values())


def test_parses_inline_sample():
    raw = ('{"type":"result","is_error":false,'
           '"usage":{"inputTokens":100,"outputTokens":20,'
           '"cacheReadTokens":5,"cacheWriteTokens":0}}')
    u = parse_cursor_usage(raw)
    assert u["input"] == 100 and u["output"] == 20 and u["total"] == 120


def test_unparseable_returns_empty():
    assert parse_cursor_usage("not json") == {}
    assert parse_cursor_usage("") == {}
    assert parse_cursor_usage('{"type":"result"}') == {}  # no usage key
