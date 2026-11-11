"""v0.7.0 review fixes: reservation keyed by worktree root; a missing registry is incomplete."""
import sys

import pytest

from tests.evidence._lazy import resolve
from tests.v070 import _stubs


def _jobs(name):
    return resolve("cld.mcp_jobs", name)


def _start(repo, root, shim, stub):
    return _jobs("start_job")("step", str(repo), [sys.executable, str(stub)],
                              entry_script=str(shim), jobs_root=str(root))


def _runner_gone(job_dir):
    """The runner writes exit.json and then exits; do not race that last step."""
    import json
    runner = json.loads((job_dir / "runner.json").read_text(encoding="utf-8")).get("runner")
    assert _stubs.wait_for(lambda: not _stubs.alive(runner), 20), "runner did not exit"


@pytest.fixture
def stub(tmp_path):
    return _stubs.write_wrapper(tmp_path / "driver.py", "driver_main")


def test_subdirectory_of_a_worktree_shares_its_reservation(tmp_path, jobs_root, entry_shim, stub,
                                                           monkeypatch):
    repo, _plan = _stubs.git_repo(tmp_path / "repo")
    (repo / "sub").mkdir()
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "30")
    first = _start(repo, jobs_root, entry_shim, stub)
    conflict = _jobs("JobConflict")
    try:
        second = _start(repo / "sub", jobs_root, entry_shim, stub)
    except conflict as exc:
        second = exc
    assert isinstance(second, conflict), f"a subdirectory started its own job: {second}"
    assert first["job_id"] in str(second)


def test_missing_registry_after_a_recorded_driver_is_incomplete(tmp_path, jobs_root, entry_shim,
                                                                stub):
    repo = tmp_path / "repo"
    repo.mkdir()
    job = _start(repo, jobs_root, entry_shim, stub)
    status = _jobs("job_status")(job["job_id"], jobs_root=str(jobs_root), wait_seconds=30)
    assert status["state"] == "finished", status
    job_dir = jobs_root / job["job_id"]
    assert (job_dir / "processes.jsonl").is_file(), "the runner must create the registry up front"
    _runner_gone(job_dir)
    (job_dir / "exit.json").unlink()
    (job_dir / "processes.jsonl").unlink()
    assert _jobs("job_status")(job["job_id"], jobs_root=str(jobs_root))["identities_incomplete"]
    items = _jobs("check_fence")(str(repo), jobs_root=str(jobs_root))
    assert len(items) == 1 and items[0]["identities_incomplete"] is True, items
    assert not (job_dir / "resolution.json").exists()


def test_orphan_started_from_a_removed_subdirectory_still_fences_the_worktree(
        tmp_path, jobs_root, entry_shim, stub):
    import json
    import os
    import shutil
    repo, _plan = _stubs.git_repo(tmp_path / "repo")
    (repo / "sub").mkdir()
    job = _start(repo / "sub", jobs_root, entry_shim, stub)
    status = _jobs("job_status")(job["job_id"], jobs_root=str(jobs_root), wait_seconds=30)
    assert status["state"] == "finished", status
    job_dir = jobs_root / job["job_id"]
    _runner_gone(job_dir)
    # Simulate an orphan: the runner is gone, a recorded driver is still alive.
    record = json.loads((job_dir / "runner.json").read_text(encoding="utf-8"))
    original = json.dumps(record)
    record["driver"] = _stubs.identity(os.getpid())
    (job_dir / "runner.json").write_text(json.dumps(record), encoding="utf-8")
    (job_dir / "exit.json").unlink()
    shutil.rmtree(repo / "sub")
    try:
        items = _jobs("check_fence")(str(repo), jobs_root=str(jobs_root))
        assert [i["job_id"] for i in items] == [job["job_id"]], items
    finally:
        # Never leave this test process recorded: the fixture reaps live identities.
        (job_dir / "runner.json").write_text(original, encoding="utf-8")


def test_worktree_lookup_never_inherits_the_server_stdin(tmp_path, monkeypatch):
    # The MCP server reads requests from stdin; on Windows a child that inherits that
    # synchronous pipe can stall while the server's reader thread holds it.
    import subprocess
    jobs = _jobs("start_job") and resolve("cld.mcp_jobs")
    seen = []
    real = subprocess.run

    def spy(*args, **kwargs):
        seen.append(kwargs.get("stdin"))
        return real(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    jobs._repo_root(str(tmp_path))
    assert seen and all(value is subprocess.DEVNULL for value in seen), seen
