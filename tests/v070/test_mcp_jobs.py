"""v0.7.0 MCPJOBS: durable job runner, reservation, containment check and fence.

Pinned API and record formats: docs/plans/v0.7.0/DESIGN.md "Jobs". ``argv`` passed
to ``start_job`` is the complete driver command line (argv[0] is an executable).
Contract details these tests pin beyond DESIGN.md:
- a malformed job id raises ``ValueError`` and an unknown well-formed id raises
  ``LookupError``, both before any job file is touched;
- ``resolve_job`` returns a dict with ``"resolved": bool`` (False when it refuses).
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.evidence._lazy import resolve
from tests.v070 import _stubs
from tests.v070._stubs import TERMINAL, WINDOWS, read_json, wait_for

ROOT = Path(__file__).resolve().parents[2]
STATUS_KEYS = {"job_id", "state", "returncode", "result", "reason", "containment",
               "identities_incomplete"}
EXIT_KEYS = {"schema", "state", "returncode", "ended_at", "result", "reason", "containment"}
FENCE_KEYS = {"job_id", "state", "alive", "live_groups", "identities_incomplete"}


def api(name):
    return resolve("cld.mcp_jobs", name)


@pytest.fixture
def stub(tmp_path):
    return _stubs.write_wrapper(tmp_path / "driver.py", "driver_main")


def _dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def start(repo, root, shim, stub, *extra, kind="step"):
    return api("start_job")(kind, str(repo), [sys.executable, str(stub), *extra],
                            entry_script=str(shim), jobs_root=str(root))


def status(job_id, root, wait=0):
    return api("job_status")(job_id, jobs_root=str(root), wait_seconds=wait)


def wait_terminal(job_id, root, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = status(job_id, root, wait=2)
        if st["state"] in TERMINAL:
            return st
    raise AssertionError(f"job {job_id} not terminal: {status(job_id, root)}")


def runner_record(root, job_id, *, driver=True, timeout=20):
    path = Path(root) / job_id / "runner.json"
    rec = wait_for(lambda: (r := read_json(path)) and (not driver or r.get("driver")) and r,
                   timeout)
    assert rec, f"runner.json never recorded the driver: {read_json(path)}"
    return rec


def fence(repo, root):
    return api("check_fence")(str(repo), jobs_root=str(root))


def finished_job(repo, root, shim, stub):
    job = start(repo, root, shim, stub)
    st = wait_terminal(job["job_id"], root)
    assert st["state"] == "finished", st
    # The runner writes exit.json, then releases its reservation and exits; tests that
    # damage the records must not race that last step.
    runner = (read_json(Path(root) / job["job_id"] / "runner.json") or {}).get("runner")
    assert wait_for(lambda: not _stubs.alive(runner), 20), "runner did not exit after finishing"
    return job["job_id"], Path(root) / job["job_id"]


def test_driver_is_recorded_before_it_runs(tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    marker = tmp_path / "marker.json"
    monkeypatch.setenv("CLD_STUB_MARKER", str(marker))
    repo = _dir(tmp_path / "repo")
    job = start(repo, jobs_root, entry_shim, stub, "--json", "x y")
    assert job.get("state") == "running" and job.get("kind") == "step", job
    assert re.fullmatch(r"[0-9a-f]{32}", job.get("job_id", "")), job
    st = wait_terminal(job["job_id"], jobs_root)
    assert STATUS_KEYS <= set(st), st
    assert st["state"] == "finished" and st["containment"] == "clean", st
    assert st["returncode"] == 0 and st["identities_incomplete"] is False, st
    assert _stubs.driver_json(st)["argv"] == ["--json", "x y"]
    exit_record = read_json(jobs_root / job["job_id"] / "exit.json")
    assert exit_record and EXIT_KEYS <= set(exit_record) and exit_record["schema"] == 1
    seen = read_json(marker)
    assert seen, "driver never ran"
    rec = seen["runner_json"]
    assert rec and rec.get("schema") == 1 and isinstance(rec.get("driver"), dict), rec
    assert isinstance(rec.get("runner"), dict) and "reservation" in rec, rec
    driver = rec["driver"]
    assert set(driver) == {"pid", "pgid", "start_time"}, driver
    if WINDOWS:
        assert driver["pid"] == seen["ppid"], "Windows records the gated bootstrap"
        assert driver["pgid"] is None and seen["in_job"] is True
    else:
        assert driver["pid"] == seen["pid"], "POSIX launcher execs in place"


def test_record_failure_kills_gated_driver(tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    marker = tmp_path / "marker.json"
    monkeypatch.setenv("CLD_STUB_MARKER", str(marker))
    monkeypatch.setenv("CLD_MCP_FAULT", "record_fails")
    job = start(_dir(tmp_path / "repo"), jobs_root, entry_shim, stub)
    st = wait_terminal(job["job_id"], jobs_root)
    assert st["state"] == "died" and st["reason"] == "record_failed", st
    time.sleep(0.5)
    assert not marker.exists(), "the gated driver ran although recording failed"


def test_surviving_child_is_terminated_before_clean_finish(tmp_path, jobs_root, entry_shim, stub,
                                                           monkeypatch):
    child = tmp_path / "child.pid"
    monkeypatch.setenv("CLD_STUB_MODE", "spawn")
    monkeypatch.setenv("CLD_STUB_CHILD", str(child))
    job = start(_dir(tmp_path / "repo"), jobs_root, entry_shim, stub)
    st = wait_terminal(job["job_id"], jobs_root)
    assert st["state"] == "finished" and st["containment"] == "clean", st
    assert child.is_file()
    assert not _stubs.pid_alive(int(child.read_text())), "finished while the child still runs"
    spawns = [r for r in _stubs.registry_lines(jobs_root / job["job_id"] / "processes.jsonl")
              if r and r.get("event") == "spawn"]
    assert spawns, "the stub's child was not in the registry"


def test_unconfirmed_containment_fences_until_child_is_gone(tmp_path, jobs_root, entry_shim, stub,
                                                            monkeypatch):
    child = tmp_path / "child.pid"
    repo = _dir(tmp_path / "repo")
    monkeypatch.setenv("CLD_STUB_MODE", "spawn")
    monkeypatch.setenv("CLD_STUB_CHILD", str(child))
    monkeypatch.setenv("CLD_MCP_FAULT", "kill_fails")
    job = start(repo, jobs_root, entry_shim, stub)
    st = wait_terminal(job["job_id"], jobs_root)
    assert st["state"] == "exit_unconfirmed" and st["containment"] == "unconfirmed", st
    pid = int(child.read_text())
    assert _stubs.pid_alive(pid), "kill_fails must leave the child running"
    items = fence(repo, jobs_root)
    assert [i["job_id"] for i in items] == [job["job_id"]], items
    assert FENCE_KEYS <= set(items[0]) and items[0]["alive"], items
    JobFenced = api("JobFenced")
    assert issubclass(JobFenced, RuntimeError)
    monkeypatch.delenv("CLD_MCP_FAULT")
    monkeypatch.setenv("CLD_STUB_MODE", "echo")
    with pytest.raises(JobFenced) as refused:
        start(repo, jobs_root, entry_shim, stub)
    assert job["job_id"] in str(refused.value)
    _stubs.kill_tree(pid)
    assert wait_for(lambda: fence(repo, jobs_root) == [], 10), fence(repo, jobs_root)
    resolution = read_json(jobs_root / job["job_id"] / "resolution.json")
    assert resolution and resolution.get("reason") == "processes_gone", resolution
    nxt = start(repo, jobs_root, entry_shim, stub)
    assert wait_terminal(nxt["job_id"], jobs_root)["state"] == "finished"


def _lost_with_live_driver(tmp_path, jobs_root, entry_shim, stub, monkeypatch, fault):
    repo = _dir(tmp_path / "repo")
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "120")
    if fault:
        monkeypatch.setenv("CLD_MCP_FAULT", fault)
    job = start(repo, jobs_root, entry_shim, stub)
    rec = runner_record(jobs_root, job["job_id"])
    _stubs.kill_one(rec["runner"]["pid"])
    st = wait_for(lambda: (s := status(job["job_id"], jobs_root))["state"] == "lost" and s, 15)
    assert st, status(job["job_id"], jobs_root)
    for name in ("CLD_MCP_FAULT", "CLD_STUB_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CLD_STUB_MODE", "echo")
    return repo, job["job_id"], rec["driver"]


@pytest.mark.parametrize("fault", [None, "kill_fails"])
def test_killed_runner_is_lost_and_fence_follows_the_driver(tmp_path, jobs_root, entry_shim, stub,
                                                            monkeypatch, fault):
    repo, job_id, driver = _lost_with_live_driver(tmp_path, jobs_root, entry_shim, stub,
                                                  monkeypatch, fault)
    if WINDOWS and fault is None:
        # The runner's kill-on-close Job Object took the driver with it.
        assert wait_for(lambda: fence(repo, jobs_root) == [], 10), fence(repo, jobs_root)
    else:
        assert _stubs.alive(driver), "driver should outlive the runner here"
        with pytest.raises(api("JobFenced")) as refused:
            start(repo, jobs_root, entry_shim, stub)
        assert job_id in str(refused.value) and str(driver["pid"]) in str(refused.value)
        items = fence(repo, jobs_root)
        assert items and items[0]["state"] == "lost"
        assert driver["pid"] in [i["pid"] for i in items[0]["alive"]], items
        _stubs.kill_tree(driver["pid"])
        assert wait_for(lambda: fence(repo, jobs_root) == [], 10), fence(repo, jobs_root)
    assert (jobs_root / job_id / "resolution.json").is_file()
    nxt = start(repo, jobs_root, entry_shim, stub)
    assert wait_terminal(nxt["job_id"], jobs_root)["state"] == "finished"


def test_manual_resolve_never_overrides_a_live_driver(tmp_path, jobs_root, entry_shim, stub,
                                                      monkeypatch):
    fault = "kill_fails" if WINDOWS else None
    _repo, job_id, driver = _lost_with_live_driver(tmp_path, jobs_root, entry_shim, stub,
                                                   monkeypatch, fault)
    resolve_job = api("resolve_job")
    result = resolve_job(job_id, jobs_root=str(jobs_root), confirm=True)
    assert result.get("resolved") is False, result
    assert not (jobs_root / job_id / "resolution.json").exists()
    assert _stubs.alive(driver), "resolve_job must not signal a live CLD process"
    _stubs.kill_tree(driver["pid"])
    assert wait_for(lambda: not _stubs.alive(driver), 10)
    result = resolve_job(job_id, jobs_root=str(jobs_root), confirm=True)
    assert result.get("resolved") is True, result
    assert (read_json(jobs_root / job_id / "resolution.json") or {}).get("reason") == "manual"


@pytest.mark.parametrize("damage", ["torn_registry", "missing_runner"])
def test_incomplete_records_block_until_manual_resolution(tmp_path, jobs_root, entry_shim, stub,
                                                          damage):
    repo = _dir(tmp_path / "repo")
    job_id, job_dir = finished_job(repo, jobs_root, entry_shim, stub)
    (job_dir / "exit.json").unlink()
    if damage == "torn_registry":
        with open(job_dir / "processes.jsonl", "a", encoding="utf-8") as stream:
            stream.write('{"event": "spawn", "pid": 12\n')
    else:
        (job_dir / "runner.json").unlink()
    st = status(job_id, jobs_root)
    assert st["state"] == "lost" and st["identities_incomplete"] is True, st
    items = fence(repo, jobs_root)
    assert len(items) == 1 and items[0]["identities_incomplete"] is True, items
    with pytest.raises(api("JobFenced")):
        start(repo, jobs_root, entry_shim, stub)
    resolve_job = api("resolve_job")
    assert resolve_job(job_id, jobs_root=str(jobs_root), confirm=False).get("resolved") is False
    assert not (job_dir / "resolution.json").exists()
    assert resolve_job(job_id, jobs_root=str(jobs_root), confirm=True).get("resolved") is True
    assert (read_json(job_dir / "resolution.json") or {}).get("reason") == "manual"
    assert (job_dir / "processes.jsonl").exists() or damage == "missing_runner"
    assert (job_dir / "request.json").exists(), "evidence must stay in place"
    nxt = start(repo, jobs_root, entry_shim, stub)
    assert wait_terminal(nxt["job_id"], jobs_root)["state"] == "finished"


def test_corrupt_exit_record_with_runner_gone_is_lost(tmp_path, jobs_root, entry_shim, stub):
    job_id, job_dir = finished_job(_dir(tmp_path / "repo"), jobs_root, entry_shim, stub)
    (job_dir / "exit.json").write_text("{not json", encoding="utf-8")
    assert status(job_id, jobs_root)["state"] == "lost"


def test_long_poll_waits_within_bounds(tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "60")
    slow = start(_dir(tmp_path / "slow"), jobs_root, entry_shim, stub)
    runner_record(jobs_root, slow["job_id"])
    t0 = time.monotonic()
    assert status(slow["job_id"], jobs_root, wait=0)["state"] == "running"
    assert time.monotonic() - t0 < 1.0
    t0 = time.monotonic()
    assert status(slow["job_id"], jobs_root, wait=2)["state"] == "running"
    assert 1.0 <= time.monotonic() - t0 <= 3.5
    monkeypatch.setenv("CLD_STUB_SECONDS", "2")
    quick = start(_dir(tmp_path / "quick"), jobs_root, entry_shim, stub)
    t0 = time.monotonic()
    st = status(quick["job_id"], jobs_root, wait=1000)
    assert st["state"] == "finished", st
    assert time.monotonic() - t0 < 20, "a long poll must return at the terminal state"


def test_mismatched_start_time_is_treated_as_gone(tmp_path, jobs_root, entry_shim, stub):
    repo = _dir(tmp_path / "repo")
    job_id, job_dir = finished_job(repo, jobs_root, entry_shim, stub)
    me = _stubs.identity(os.getpid())
    fake = dict(me, start_time=1 if isinstance(me["start_time"], int) else "not a start time")
    rec = read_json(job_dir / "runner.json")
    rec.update(runner=fake, driver=fake)
    (job_dir / "runner.json").write_text(json.dumps(rec), encoding="utf-8")
    (job_dir / "exit.json").unlink()
    assert status(job_id, jobs_root)["state"] == "lost"
    assert fence(repo, jobs_root) == []
    assert (read_json(job_dir / "resolution.json") or {}).get("reason") == "processes_gone"


_RACER = """import json, sys, time
from pathlib import Path
sys.path.insert(0, {engine!r})
try:
    import cld.mcp_jobs as jobs
except Exception as exc:
    print(json.dumps({{"error": repr(exc)}})); sys.exit(0)
go = Path(sys.argv[1])
while not go.exists():
    time.sleep(0.005)
try:
    r = jobs.start_job("step", sys.argv[2], [sys.executable, sys.argv[3]],
                       entry_script=sys.argv[4], jobs_root=sys.argv[5])
    print(json.dumps({{"ok": r}}))
except jobs.JobConflict as exc:
    print(json.dumps({{"conflict": str(exc)}}))
except Exception as exc:
    print(json.dumps({{"error": repr(exc)}}))
"""


def test_reservation_across_separate_processes(tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "30")
    repo = _dir(tmp_path / "repo")
    _dir(repo / "sub")
    racer = tmp_path / "racer.py"
    racer.write_text(_RACER.format(engine=str(ROOT / "engine")), encoding="utf-8")
    go = tmp_path / "go"
    spellings = [str(repo), str(repo / "sub" / "..")]
    procs = [subprocess.Popen([sys.executable, str(racer), str(go), spelling, str(stub),
                               str(entry_shim), str(jobs_root)],
                              stdout=subprocess.PIPE, text=True) for spelling in spellings]
    time.sleep(1.0)
    go.write_text("go")
    results = [json.loads(p.communicate(timeout=60)[0].strip().splitlines()[-1]) for p in procs]
    winners = [r["ok"] for r in results if "ok" in r]
    losers = [r["conflict"] for r in results if "conflict" in r]
    assert len(winners) == 1 and len(losers) == 1, results
    assert winners[0]["job_id"] in losers[0], "the conflict must name the running job"
    other = start(_dir(tmp_path / "other"), jobs_root, entry_shim, stub)
    assert other["state"] == "running"


def _short_path(path):
    if not WINDOWS:
        return None
    import ctypes
    buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, 1024) and buf.value != str(path):
        return buf.value
    return None


def test_unresolved_jobs_root_spelling_works(tmp_path, jobs_root, entry_shim, stub):
    _dir(tmp_path / "x")
    roots = [tmp_path / "x" / ".." / "jobs-dotted"]
    short = _short_path(tmp_path)
    if short:
        roots.append(Path(short) / "jobs-short")
    for index, root in enumerate(roots):
        assert root.absolute() != root.resolve()
        job = start(_dir(tmp_path / f"repo{index}"), root, entry_shim, stub)
        assert wait_terminal(job["job_id"], root)["state"] == "finished"


def test_jobs_root_defaults_to_environment(tmp_path, jobs_root, entry_shim, stub):
    job = api("start_job")("step", str(_dir(tmp_path / "repo")), [sys.executable, str(stub)],
                           entry_script=str(entry_shim))
    assert (jobs_root / job["job_id"]).is_dir()
    st = api("job_status")(job["job_id"], wait_seconds=30)
    assert st["state"] == "finished", st


def _age(job_dir, days=10):
    then = time.time() - days * 86400
    record = read_json(job_dir / "exit.json")
    if record:
        record["ended_at"] = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        (job_dir / "exit.json").write_text(json.dumps(record), encoding="utf-8")
    for path in [*job_dir.rglob("*"), job_dir]:
        os.utime(path, (then, then))


def test_retention_deletes_only_old_confirmed_terminal_jobs(tmp_path, jobs_root, entry_shim, stub,
                                                            monkeypatch):
    jobs = {}
    for name in ("old_finished", "recent_finished", "old_lost", "old_resolved", "old_unconfirmed"):
        repo = _dir(tmp_path / name)
        job_id, job_dir = finished_job(repo, jobs_root, entry_shim, stub)
        jobs[name] = job_dir
        if name in ("old_lost", "old_resolved"):
            (job_dir / "exit.json").unlink()
        if name == "old_resolved":
            assert fence(repo, jobs_root) == []
            assert (job_dir / "resolution.json").is_file()
        if name == "old_unconfirmed":
            record = read_json(job_dir / "exit.json")
            record.update(state="exit_unconfirmed", containment="unconfirmed")
            (job_dir / "exit.json").write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "60")
    running = start(_dir(tmp_path / "running"), jobs_root, entry_shim, stub)
    runner_record(jobs_root, running["job_id"])
    jobs["old_running"] = jobs_root / running["job_id"]
    for name, job_dir in jobs.items():
        if name != "recent_finished":
            _age(job_dir)
    assert api("purge")(jobs_root=str(jobs_root), max_age_days=7) == 2
    gone = {name for name, job_dir in jobs.items() if not job_dir.exists()}
    assert gone == {"old_finished", "old_resolved"}, gone


@pytest.mark.parametrize("bad", ["../x", "A" * 32, "a" * 31, "a" * 33, "g" * 32,
                                 "0" * 16 + "/" + "0" * 15])
def test_malformed_job_ids_are_refused_before_filesystem_access(tmp_path, bad):
    root = tmp_path / "never-created"
    job_status, resolve_job = api("job_status"), api("resolve_job")
    with pytest.raises(ValueError):
        job_status(bad, jobs_root=str(root))
    with pytest.raises(ValueError):
        resolve_job(bad, jobs_root=str(root), confirm=True)
    assert not root.exists()


def test_unknown_job_id_is_a_lookup_error(tmp_path, jobs_root):
    with pytest.raises(LookupError):
        api("job_status")("0" * 32, jobs_root=str(jobs_root))


def _find_key(value, key):
    if isinstance(value, dict):
        return any(k == key and v is False for k, v in value.items()) or any(
            _find_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_find_key(v, key) for v in value)
    return False


@pytest.mark.skipif(not WINDOWS, reason="Windows Job Object breakaway")
def test_breakaway_refusal_retries_without_it(tmp_path, jobs_root, entry_shim, stub, monkeypatch):
    jobs = api("start_job") and resolve("cld.mcp_jobs")
    real = subprocess.Popen
    refused = []

    def popen(*args, **kwargs):
        if kwargs.get("creationflags", 0) & subprocess.CREATE_BREAKAWAY_FROM_JOB:
            refused.append(kwargs["creationflags"])
            raise OSError("breakaway not permitted")
        return real(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", popen)
    if hasattr(jobs, "Popen"):
        monkeypatch.setattr(jobs, "Popen", popen)
    job = start(_dir(tmp_path / "repo"), jobs_root, entry_shim, stub)
    monkeypatch.setattr(subprocess, "Popen", real)
    assert refused, "start_job never asked for breakaway"
    assert wait_terminal(job["job_id"], jobs_root)["state"] == "finished"
    records = [read_json(p) for p in (jobs_root / job["job_id"]).glob("*.json")]
    assert any(_find_key(r, "breakaway") for r in records), "breakaway: false not recorded"


@pytest.mark.skipif(WINDOWS, reason="POSIX process groups")
def test_leaderless_group_fences_until_its_worker_is_gone(tmp_path, jobs_root, entry_shim, stub,
                                                          monkeypatch):
    child = tmp_path / "child.pid"
    worker = Path(str(child) + ".worker")
    repo = _dir(tmp_path / "repo")
    monkeypatch.setenv("CLD_STUB_MODE", "leaderless")
    monkeypatch.setenv("CLD_STUB_CHILD", str(child))
    job = start(repo, jobs_root, entry_shim, stub)
    rec = runner_record(jobs_root, job["job_id"])
    registry = jobs_root / job["job_id"] / "processes.jsonl"
    assert wait_for(lambda: worker.is_file() and any(
        r and r.get("event") == "reap" for r in _stubs.registry_lines(registry)), 20)
    spawn = next(r for r in _stubs.registry_lines(registry) if r and r.get("event") == "spawn")
    _stubs.kill_one(rec["runner"]["pid"])
    _stubs.kill_tree(rec["driver"]["pid"])
    assert wait_for(lambda: status(job["job_id"], jobs_root)["state"] == "lost", 15)
    items = fence(repo, jobs_root)
    assert items and spawn["pgid"] in items[0]["live_groups"], items
    monkeypatch.setenv("CLD_STUB_MODE", "echo")
    with pytest.raises(api("JobFenced")):
        start(repo, jobs_root, entry_shim, stub)
    os.kill(int(worker.read_text()), 9)
    assert wait_for(lambda: fence(repo, jobs_root) == [], 10), fence(repo, jobs_root)
