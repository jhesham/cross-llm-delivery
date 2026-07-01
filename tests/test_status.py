"""Acceptance test for cld.status.render_status — the --status digest the lead agent reads.

Pure function: a telemetry event stream (list of dicts) in -> a compact ASCII digest out.
Deterministic `now` so elapsed is exact. cp1252-safe (the console-crash discipline).
"""
import datetime

from cld.status import render_status

_BASE = datetime.datetime(2026, 6, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _ts(offset_s):
    return (_BASE + datetime.timedelta(seconds=offset_s)).isoformat()


_NOW = _BASE + datetime.timedelta(seconds=60)


def _events():
    return [
        {"type": "run_start", "run_id": "a1b2", "plan": "p.md", "ts": _ts(0)},
        {"type": "layer_start", "layer": 0, "slice_ids": ["T1", "T2", "T3", "T4"],
         "total": 3, "run_id": "a1b2", "ts": _ts(0)},
        # T1 done (completed)
        {"type": "slice_start", "slice_id": "T1", "run_id": "a1b2", "ts": _ts(1)},
        {"type": "dispatch_start", "slice_id": "T1", "model": "antigravity:Gemini 3.1 Pro (High)",
         "rung": "workhorse", "attempt": 1, "source": "default", "run_id": "a1b2", "ts": _ts(1)},
        {"type": "dispatch_end", "slice_id": "T1", "model": "antigravity:Gemini 3.1 Pro (High)",
         "rc": 0, "tokens": {"total": 1000}, "ms": 1200, "run_id": "a1b2", "ts": _ts(3)},
        {"type": "judge_verdict", "slice_id": "T1", "passed": True, "attempt": 1,
         "run_id": "a1b2", "ts": _ts(3)},
        {"type": "slice_done", "slice_id": "T1", "status": "completed", "run_id": "a1b2", "ts": _ts(3)},
        # T2 done (completed)
        {"type": "slice_start", "slice_id": "T2", "run_id": "a1b2", "ts": _ts(3)},
        {"type": "dispatch_start", "slice_id": "T2", "model": "antigravity:Gemini 3.1 Pro (High)",
         "rung": "workhorse", "attempt": 1, "source": "default", "run_id": "a1b2", "ts": _ts(3)},
        {"type": "dispatch_end", "slice_id": "T2", "model": "antigravity:Gemini 3.1 Pro (High)",
         "rc": 0, "tokens": {"total": 2000}, "ms": 900, "run_id": "a1b2", "ts": _ts(5)},
        {"type": "slice_done", "slice_id": "T2", "status": "completed", "run_id": "a1b2", "ts": _ts(5)},
        # T3 RUNNING: dispatch_start at +13s, _NOW is +60s -> elapsed 47s. No slice_done.
        {"type": "slice_start", "slice_id": "T3", "run_id": "a1b2", "ts": _ts(13)},
        {"type": "dispatch_start", "slice_id": "T3", "model": "opencode:opencode/glm-5.2",
         "rung": "workhorse", "attempt": 1, "source": "tag", "run_id": "a1b2", "ts": _ts(13)},
        # T4 PENDING: in slice_ids, never started.
    ]


def test_render_status_reconstructs_build_state():
    out = render_status(_events(), now=_NOW)
    assert "a1b2" in out                         # run id
    assert "1/3" in out                          # layer position (index 0 of 3)
    assert "T3" in out                           # the in-flight slice
    assert "opencode:opencode/glm-5.2" in out    # its model
    assert "47s" in out                          # its elapsed (now - dispatch_start)
    assert "2" in out                            # 2 slices done
    assert ("3000" in out) or ("3k" in out)      # cumulative tokens (1000 + 2000)
    assert "gate" in out.lower()                 # gate shown
    out.encode("cp1252")                         # cp1252-safe: must not raise


def test_render_status_pending_slice_counted():
    out = render_status(_events(), now=_NOW)
    # T4 is in the layer but never started -> surfaced as pending (1 pending)
    assert "pending" in out.lower()


def test_render_status_gate_from_run_done():
    events = _events() + [{"type": "run_done", "gate": "passed", "run_id": "a1b2", "ts": _ts(70)}]
    out = render_status(events, now=_NOW)
    assert "passed" in out.lower()


def test_render_status_defaults_now_for_real_elapsed():
    # The CLI calls render_status(events) with NO `now`; elapsed must reflect wall-clock,
    # not collapse to 0. Regression: a live --status showed `elapsed: 0s` while the slice
    # had really been running 212s, because now=None flowed into the elapsed calc as 0.
    import re
    start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60)
    events = [
        {"type": "layer_start", "layer": 0, "slice_ids": ["T1"], "total": 1, "ts": start.isoformat()},
        {"type": "slice_start", "slice_id": "T1", "ts": start.isoformat()},
        {"type": "dispatch_start", "slice_id": "T1", "model": "m", "rung": "workhorse",
         "source": "default", "ts": start.isoformat()},
    ]
    out = render_status(events)  # no now= -> must default to wall clock
    m = re.search(r"elapsed:\s*(\d+)s", out)
    assert m, out
    assert int(m.group(1)) >= 55  # ~60s; crucially NOT 0


def test_render_status_empty_is_graceful():
    out = render_status([])
    assert out and "no events" in out.lower()  # degrades, never crashes


def test_status_flag_reads_events_file(tmp_path, capsys):
    """run_delivery --status reads <repo>/.cld/events.jsonl and prints the digest (no plan)."""
    import json
    import skill.scripts.run_delivery as rd
    cld = tmp_path / ".cld"
    cld.mkdir()
    evs = [
        {"type": "run_start", "run_id": "zz9", "ts": _ts(0)},
        {"type": "layer_start", "layer": 0, "slice_ids": ["A"], "total": 1, "ts": _ts(0)},
        {"type": "slice_start", "slice_id": "A", "ts": _ts(0)},
        {"type": "dispatch_end", "slice_id": "A", "tokens": {"total": 42}, "ts": _ts(1)},
        {"type": "slice_done", "slice_id": "A", "status": "completed", "ts": _ts(1)},
        {"type": "run_done", "gate": "passed", "ts": _ts(2)},
    ]
    (cld / "events.jsonl").write_text("\n".join(json.dumps(e) for e in evs), encoding="utf-8")
    rc = rd.main(["--status", "--repo", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0 and "zz9" in out and "42" in out and "passed" in out.lower()


def test_status_flag_missing_file_is_graceful(tmp_path, capsys):
    import skill.scripts.run_delivery as rd
    rc = rd.main(["--status", "--repo", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0 and "no events" in out.lower()


def test_watch_repaints_then_stops_on_interrupt(tmp_path, monkeypatch, capsys):
    """--watch repaints the digest then exits cleanly on Ctrl-C (one iteration here)."""
    import skill.scripts.run_delivery as rd
    cld = tmp_path / ".cld"
    cld.mkdir()
    (cld / "events.jsonl").write_text(
        '{"type":"run_start","run_id":"w1","ts":"2026-06-30T12:00:00+00:00"}', encoding="utf-8")

    def fake_sleep(_):
        raise KeyboardInterrupt  # stop after the first repaint

    monkeypatch.setattr("time.sleep", fake_sleep)
    rc = rd.main(["--watch", "--repo", str(tmp_path), "--interval", "1"])
    out = capsys.readouterr().out
    assert rc == 0 and "w1" in out
