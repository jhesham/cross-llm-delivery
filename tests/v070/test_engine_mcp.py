"""v0.7.0 ENGINEMCP: --new-build reports the ledger backup; gated process registry."""
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.v070 import _stubs
from tests.v070._stubs import WINDOWS, json_lines, read_json

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "skill" / "scripts" / "run_delivery.py"


def _new_build(repo, plan, *extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLD_")}
    proc = subprocess.run([sys.executable, str(DRIVER), str(plan), "--repo", str(repo),
                           "--new-build", *extra], capture_output=True, text=True, env=env,
                          timeout=120)
    return proc


def test_new_build_json_reports_ledger_backup(repo):
    path, plan = repo
    first = _new_build(path, plan, "--json")
    objects = json_lines(first.stdout)
    assert first.returncode == 0 and len(objects) == 1, (first.stdout, first.stderr)
    assert objects[0]["command"] == "new-build" and objects[0]["gate_code"] == 0
    assert objects[0]["artifacts"].get("ledger_backup") is None
    second = _new_build(path, plan, "--json")
    objects = json_lines(second.stdout)
    assert second.returncode == 0 and len(objects) == 1, (second.stdout, second.stderr)
    response = objects[0]
    assert response["command"] == "new-build" and response["gate_code"] == 0
    assert isinstance(response.get("run_id"), str)
    backup = response["artifacts"].get("ledger_backup")
    assert backup, f"artifacts lacks ledger_backup: {response['artifacts']}"
    assert Path(backup).is_absolute() and Path(backup).is_file()


def test_new_build_text_output_unchanged(repo):
    path, plan = repo
    _new_build(path, plan)
    proc = _new_build(path, plan)
    assert proc.returncode == 0, proc.stderr
    assert "state prepared: run=" in proc.stdout and "; backup=" in proc.stdout
    assert not json_lines(proc.stdout)


_PROBE = """import json, os, sys
sys.path.insert(0, {here!r})
import _stubs
registry = os.environ.get("CLD_PROCESS_REGISTRY")
data = {{"pid": os.getpid(), "ppid": os.getppid(), "in_job": _stubs.in_job(),
        "registry": _stubs.registry_lines(registry) if registry else [],
        "stdin": sys.stdin.read()}}
open(sys.argv[1], "w").write(json.dumps(data))
"""


def _probe(tmp_path):
    script = tmp_path / "probe.py"
    script.write_text(_PROBE.format(here=str(_stubs.HERE)), encoding="utf-8")
    return script


def test_registry_records_child_before_it_runs(tmp_path, monkeypatch):
    from cld.process import run_process
    registry = tmp_path / "processes.jsonl"
    marker = tmp_path / "marker.json"
    monkeypatch.setenv("CLD_PROCESS_REGISTRY", str(registry))
    result = run_process([sys.executable, str(_probe(tmp_path)), str(marker)], str(tmp_path),
                         stdin="hello stdin", timeout=60)
    assert result.error is None and result.returncode == 0, result
    seen = read_json(marker)
    assert seen, "child never ran"
    spawns = [r for r in seen["registry"] if r and r.get("event") == "spawn"]
    assert len(spawns) == 1, f"spawn line not present when the child started: {seen['registry']}"
    spawn = spawns[0]
    assert set(spawn) == {"event", "pid", "pgid", "start_time"}, spawn
    if WINDOWS:
        assert spawn["pid"] == seen["ppid"], "Windows records the gated bootstrap"
        assert spawn["pgid"] is None and seen["in_job"] is True
    else:
        assert spawn["pid"] == seen["pid"], "POSIX launcher execs in place"
        assert spawn["pgid"] == spawn["pid"]
    assert seen["stdin"] == "hello stdin"
    lines = _stubs.registry_lines(registry)
    reaps = [r for r in lines if r and r.get("event") == "reap"]
    assert reaps == [{"event": "reap", "pid": spawn["pid"], "start_time": spawn["start_time"]}]
    assert lines.index(reaps[0]) > lines.index(spawn)


def test_registry_write_failure_kills_child_unrun(tmp_path, monkeypatch):
    from cld.process import run_process
    unwritable = tmp_path / "registry-is-a-directory"
    unwritable.mkdir()
    marker = tmp_path / "marker.json"
    monkeypatch.setenv("CLD_PROCESS_REGISTRY", str(unwritable))
    result = run_process([sys.executable, str(_probe(tmp_path)), str(marker)], str(tmp_path),
                         timeout=60)
    assert not marker.exists(), "the child ran although its record could not be written"
    assert result.error is not None, result


def test_registry_unset_writes_nothing(tmp_path, monkeypatch):
    from cld.process import run_process
    monkeypatch.delenv("CLD_PROCESS_REGISTRY", raising=False)
    marker = tmp_path / "marker.json"
    probe = _probe(tmp_path)
    before = set(tmp_path.rglob("*"))
    result = run_process([sys.executable, str(probe), str(marker)], str(tmp_path),
                         stdin="x", timeout=60)
    assert result.error is None and read_json(marker)["registry"] == []
    created = {p.name for p in set(tmp_path.rglob("*")) - before}
    assert created == {"marker.json"}, created
    assert json.loads(marker.read_text())["stdin"] == "x"
