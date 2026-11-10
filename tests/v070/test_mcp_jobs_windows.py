"""v0.7.0 follow-up: job records survive a concurrent reader on Windows.

A reader (job_status polling runner.json) briefly denies replacement on Windows;
the runner must retry the same flushed temporary file instead of failing the
job with record_failed.
"""
import json
import threading

import pytest

from tests.v070._stubs import WINDOWS


@pytest.mark.skipif(not WINDOWS, reason="Windows sharing violations")
def test_atomic_record_retries_while_a_reader_holds_the_file(tmp_path):
    from cld.mcp_jobs import _atomic
    target = tmp_path / "runner.json"
    target.write_text('{"old": true}\n', encoding="utf-8")
    reader = open(target, encoding="utf-8")  # no delete sharing: replace is denied
    timer = threading.Timer(0.15, reader.close)
    timer.start()
    try:
        _atomic(target, {"new": True})
    finally:
        timer.cancel()
        reader.close()
    assert json.loads(target.read_text(encoding="utf-8")) == {"new": True}
    assert [p.name for p in tmp_path.iterdir()] == ["runner.json"], "temporary file left behind"
