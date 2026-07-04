"""Acceptance test for the --status 'by model' rollup (model-switching visibility).

render_status must add a line grouping slices by the model that ran them, with each
model's slice ids, summed tokens, and the source/reason (tag/default/auto/escalated).
"""
import datetime

from cld.status import render_status

_BASE = datetime.datetime(2026, 6, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _ts(o):
    return (_BASE + datetime.timedelta(seconds=o)).isoformat()


def _events():
    return [
        {"type": "run_start", "run_id": "a1", "ts": _ts(0)},
        {"type": "layer_start", "layer": 0, "slice_ids": ["T1", "T2"], "total": 1, "ts": _ts(0)},
        {"type": "slice_start", "slice_id": "T1", "ts": _ts(0)},
        {"type": "dispatch_start", "slice_id": "T1", "model": "antigravity:Gemini 3.1 Pro (High)",
         "rung": "workhorse", "attempt": 1, "source": "default", "ts": _ts(0)},
        {"type": "dispatch_end", "slice_id": "T1", "model": "antigravity:Gemini 3.1 Pro (High)",
         "rc": 0, "tokens": {"total": 1000}, "ms": 10, "ts": _ts(1)},
        {"type": "slice_done", "slice_id": "T1", "status": "completed", "ts": _ts(1)},
        {"type": "slice_start", "slice_id": "T2", "ts": _ts(1)},
        {"type": "dispatch_start", "slice_id": "T2", "model": "opencode:opencode/glm-5.2",
         "rung": "workhorse", "attempt": 1, "source": "tag", "ts": _ts(1)},
        {"type": "dispatch_end", "slice_id": "T2", "model": "opencode:opencode/glm-5.2",
         "rc": 0, "tokens": {"total": 5000}, "ms": 10, "ts": _ts(2)},
        {"type": "slice_done", "slice_id": "T2", "status": "completed", "ts": _ts(2)},
    ]


def test_by_model_rollup_groups_slices_tokens_source():
    out = render_status(_events(), now=_BASE + datetime.timedelta(seconds=3))
    low = out.lower()
    assert "by model" in low                                   # the rollup line/section
    assert "antigravity:Gemini 3.1 Pro (High)" in out          # model 1
    assert "opencode:opencode/glm-5.2" in out                  # model 2
    assert "T1" in out and "T2" in out                         # slices attributed
    assert "1000" in out and "5000" in out                     # per-model token sums
    assert "tag" in low and "default" in low                   # source/reason per model
    out.encode("cp1252")                                       # cp1252-safe


def test_by_model_shows_cost_when_present():
    events = _events()
    for e in events:  # T2 ran on a metered model -> a per-dispatch dollar cost
        if e["type"] == "dispatch_end" and e["slice_id"] == "T2":
            e["cost"] = 0.41
    out = render_status(events, now=_BASE + datetime.timedelta(seconds=3))
    assert "$" in out and "0.41" in out  # cost surfaced (per-model + total)
