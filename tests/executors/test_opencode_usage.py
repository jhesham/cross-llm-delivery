"""parse_opencode_usage parsed against the REAL captured JSONL (T1 fixture).

OpenCode `--format json` is JSONL: one event per line. Tokens live on the
step_finish event at part.tokens {total,input,output,reasoning,cache}. Multiple
step_finish events (multi-step runs) must be summed. Fixture captured from a real multi-step opencode run.
"""

from pathlib import Path

from cld.executors.opencode import parse_opencode_usage

# tests/executors/test_opencode_usage.py -> repo root is parents[2]
_SAMPLE = (Path(__file__).resolve().parents[1] / "fixtures" / "opencode-run-sample.json")


def test_parses_real_sample_tokens():
    raw = _SAMPLE.read_text(encoding="utf-8")
    usage = parse_opencode_usage(raw)
    # Exact numbers from the committed live capture (single step_finish event).
    assert usage["input"] == 8129
    assert usage["output"] == 2
    assert usage["total"] == 8145
    assert usage["reasoning"] == 14
    assert all(isinstance(v, int) for v in usage.values())


def test_sums_multiple_step_finish_events():
    jsonl = (
        '{"type":"text","part":{"text":"hi"}}\n'
        '{"type":"step_finish","part":{"tokens":{"input":100,"output":10,"total":110}}}\n'
        '{"type":"step_finish","part":{"tokens":{"input":50,"output":5,"total":55}}}\n'
    )
    usage = parse_opencode_usage(jsonl)
    assert usage["input"] == 150
    assert usage["output"] == 15
    assert usage["total"] == 165


def test_unparseable_returns_empty():
    assert parse_opencode_usage("not json at all") == {}
    assert parse_opencode_usage("") == {}
    # valid JSONL but no step_finish / no tokens -> empty
    assert parse_opencode_usage('{"type":"text","part":{"text":"hi"}}\n') == {}
