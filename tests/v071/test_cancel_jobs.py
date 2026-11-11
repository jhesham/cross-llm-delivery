"""v0.7.1 JOBCANCEL: cancel_job, grace and escalation, states, races and retention.

The stub driver's sleep mode exits like the real CLI (exit 130, no JSON) when
CLD_CANCEL_FILE appears; its late mode prints a gate-6 response, admits a cancel
itself, then exits 6 (a cancel that arrived too late).
"""
import json
import os
import time
from pathlib import Path

import pytest

from tests.evidence._lazy import resolve
from tests.v070 import _stubs
from tests.v070._stubs import WINDOWS, read_json, wait_for
from tests.v070.test_mcp_jobs import _age, _dir, fence, finished_job, runner_record, start, status
from tests.v071.conftest import ACTIVE, TERMINAL

CANCEL_KEYS = {"job_id", "state", "requested", "reason"}


def api(name):
    return resolve("cld.mcp_jobs", name)


@pytest.fixture
def stub(tmp_path):
    return _stubs.write_wrapper(tmp_path / "driver.py", "driver_main")


def cancel(job_id, root):
    return api("cancel_job")(job_id, jobs_root=str(root))


def settle(job_id, root, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = status(job_id, root, wait=2)
        if st["state"] in TERMINAL:
            return st
    raise AssertionError(f"job {job_id} did not settle: {status(job_id, root)}")


def sleeping_job(tmp_path, root, shim, stub, monkeypatch, *, name="repo", seconds="120"):
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", seconds)
    job = start(_dir(tmp_path / name), root, shim, stub)
    runner_record(root, job["job_id"])
    return job["job_id"]


def test_cooperative_cancel_ends_cancelled_and_is_retained_like_finished(
        tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    job_id = sleeping_job(tmp_path, jobs_root, entry_shim, stub, monkeypatch)
    record = read_json(jobs_root / job_id / "runner.json")
    assert record.get("cancel") == 1, f"runner.json must advertise cancel support: {record}"
    reply = cancel(job_id, jobs_root)
    assert CANCEL_KEYS <= set(reply) and reply["requested"] is True, reply
    assert reply["state"] in ACTIVE
    st = settle(job_id, jobs_root)
    assert st["state"] == "cancelled" and st["reason"] == "cancel_requested", st
    assert st["containment"] == "clean"
    assert (jobs_root / job_id / "cancel.request").is_file()
    _age(jobs_root / job_id)
    assert api("purge")(jobs_root=str(jobs_root), max_age_days=7) == 1
    assert not (jobs_root / job_id).exists()


def test_ignored_cancel_is_escalated_after_grace(tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    monkeypatch.setenv("CLD_MCP_FAULT", "ignore_cancel")
    monkeypatch.setenv("CLD_MCP_CANCEL_GRACE", "1")
    job_id = sleeping_job(tmp_path, jobs_root, entry_shim, stub, monkeypatch)
    t0 = time.monotonic()
    assert cancel(job_id, jobs_root)["requested"] is True
    st = settle(job_id, jobs_root)
    assert st["state"] == "cancelled" and st["reason"] == "cancel_escalated", st
    assert time.monotonic() - t0 < 15
    driver = read_json(jobs_root / job_id / "runner.json")["driver"]
    assert not _stubs.alive(driver)


def test_unconfirmed_cancel_fences_the_repository(tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    monkeypatch.setenv("CLD_MCP_FAULT", "ignore_cancel,kill_fails")
    monkeypatch.setenv("CLD_MCP_CANCEL_GRACE", "1")
    job_id = sleeping_job(tmp_path, jobs_root, entry_shim, stub, monkeypatch)
    driver = read_json(jobs_root / job_id / "runner.json")["driver"]
    assert cancel(job_id, jobs_root)["requested"] is True
    st = settle(job_id, jobs_root)
    assert st["state"] == "cancel_unconfirmed", st
    repo = tmp_path / "repo"
    items = fence(repo, jobs_root)
    assert [i["job_id"] for i in items] == [job_id], items
    _stubs.kill_tree(driver["pid"])
    assert wait_for(lambda: fence(repo, jobs_root) == [], 15), fence(repo, jobs_root)


def test_cancelling_state_long_polls_and_keeps_the_first_deadline(
        tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    monkeypatch.setenv("CLD_MCP_FAULT", "ignore_cancel")
    monkeypatch.setenv("CLD_MCP_CANCEL_GRACE", "4")
    job_id = sleeping_job(tmp_path, jobs_root, entry_shim, stub, monkeypatch)
    t0 = time.monotonic()
    assert cancel(job_id, jobs_root)["requested"] is True
    assert wait_for(lambda: status(job_id, jobs_root)["state"] == "cancelling", 5)
    t1 = time.monotonic()
    assert status(job_id, jobs_root, wait=1)["state"] == "cancelling"
    assert time.monotonic() - t1 >= 0.8, "a long poll must wait while cancelling"
    while time.monotonic() - t0 < 3:
        time.sleep(0.1)
    again = cancel(job_id, jobs_root)
    assert again["requested"] is True and again["state"] == "cancelling", again
    st = settle(job_id, jobs_root)
    assert st["state"] == "cancelled", st
    assert time.monotonic() - t0 < 6.5, "a repeated cancel must not reset the grace deadline"


def test_cancelling_job_is_named_in_conflicts(tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    monkeypatch.setenv("CLD_MCP_FAULT", "ignore_cancel")
    monkeypatch.setenv("CLD_MCP_CANCEL_GRACE", "10")
    job_id = sleeping_job(tmp_path, jobs_root, entry_shim, stub, monkeypatch)
    assert cancel(job_id, jobs_root)["requested"] is True
    assert wait_for(lambda: status(job_id, jobs_root)["state"] == "cancelling", 5)
    conflict = api("JobConflict")
    try:
        second = start(tmp_path / "repo", jobs_root, entry_shim, stub)
    except conflict as exc:
        second = exc
    assert isinstance(second, conflict) and job_id in str(second), second


def test_cancel_after_finish_is_not_requested(tmp_path, jobs_root, entry_shim, stub):
    job_id, job_dir = finished_job(_dir(tmp_path / "repo"), jobs_root, entry_shim, stub)
    reply = cancel(job_id, jobs_root)
    assert reply["requested"] is False and reply["state"] == "finished", reply
    assert not (job_dir / "cancel.request").exists()


def test_cancel_arriving_after_completion_reports_finished(tmp_path, jobs_root, entry_shim, stub,
                                                           monkeypatch):
    monkeypatch.setenv("CLD_STUB_MODE", "late")
    job = start(_dir(tmp_path / "repo"), jobs_root, entry_shim, stub)
    st = settle(job["job_id"], jobs_root)
    assert st["state"] == "finished" and st["reason"] == "cancel_too_late", st
    assert st["returncode"] == 6 and st["result"]["gate_code"] == 6, st


def test_legacy_runner_is_refused(tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    job_id = sleeping_job(tmp_path, jobs_root, entry_shim, stub, monkeypatch)
    path = jobs_root / job_id / "runner.json"
    record = read_json(path)
    record.pop("cancel", None)
    path.write_text(json.dumps(record), encoding="utf-8")
    reply = cancel(job_id, jobs_root)
    assert reply["requested"] is False and reply["reason"] == "legacy_runner", reply
    assert not (jobs_root / job_id / "cancel.request").exists()


@pytest.mark.parametrize("bad", ["../x", "A" * 32, "a" * 31])
def test_malformed_cancel_ids_are_refused(tmp_path, bad):
    root = tmp_path / "never"
    with pytest.raises(ValueError):
        api("cancel_job")(bad, jobs_root=str(root))
    assert not root.exists()


def test_unknown_cancel_id_is_a_lookup_error(jobs_root):
    with pytest.raises(LookupError):
        api("cancel_job")("0" * 32, jobs_root=str(jobs_root))
