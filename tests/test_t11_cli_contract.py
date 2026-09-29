"""Lead-owned acceptance for T11. No live models; both real CLI entrypoints."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from cld.executors.base import SliceTask
from cld.ledger import Ledger
from tests.integration.harness import init_repo, real_git_runner

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=["script", "module"])
def invoke(request):
    def call(*args):
        entry = [str(ROOT / "skill/scripts/run_delivery.py")] if request.param == "script" else ["-m", "cld"]
        env = {**os.environ, "PYTHONPATH": str(ROOT / "engine"), "PYTHONDONTWRITEBYTECODE": "1"}
        env.pop("ANTHROPIC_API_KEY", None)
        proc = subprocess.run([sys.executable, *entry, *map(str, args)], cwd=ROOT,
            env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", timeout=30)
        try:
            response = json.loads(proc.stdout)
        except ValueError:
            assert False, f"Expected one JSON object; rc={proc.returncode}; stderr={proc.stderr[:200]!r}"
        assert response["schema_version"] == 1
        for field in ("command", "gate", "gate_code", "next_action", "run_id", "repository", "ledger", "artifacts", "usage", "budget", "accepted_refs", "errors"):
            assert field in response, field
        assert response["gate_code"] == proc.returncode
        assert isinstance(response["errors"], list)
        assert isinstance(response["next_action"], str) and response["next_action"]
        return proc, response
    return call


@pytest.fixture
def project(tmp_path):
    repo = Path(init_repo(tmp_path / "project with spaces"))
    plan = tmp_path / "plan.md"
    plan.write_text("## SLICE: A\nbrief: implement\nfiles: implementation.py\nacceptance_test_path: test_acceptance.py\ndeps:\n", encoding="utf-8")
    return repo, plan


def test_preview_is_structured_and_read_only(invoke, project):
    repo, plan = project
    proc, data = invoke(plan, "--repo", repo, "--dry-run", "--json", "--host", "codex")
    assert proc.returncode == 0 and data["command"] == "preview"
    assert data["repository"] == str(repo.resolve())
    assert data["ledger"] == str(repo / ".cld-ledger.json")
    assert data["layers"] == [["A"]]
    assert not (repo / ".cld-ledger.json").exists()


@pytest.mark.parametrize("args", [("--unknown-argument",), ("--step",), ("--watch",), ("--status", "--usage")])
def test_invalid_requests_are_structured_not_argparse_prose(invoke, project, args):
    repo, _ = project
    proc, data = invoke(*args, "--repo", repo, "--json")
    assert proc.returncode == 5 and data["gate"] == "blocked" and data["errors"]


def test_corrupt_ledger_is_structured(invoke, project):
    repo, _ = project
    (repo / ".cld-ledger.json").write_text("{broken")
    proc, data = invoke("--status", "--repo", repo, "--json")
    assert proc.returncode == 5 and data["errors"]


@pytest.mark.parametrize("status,code,gate,action", [
    ("pending", 0, "pending", "resume"), ("failed", 2, "failed", "resume"),
    ("needs_repair", 4, "needs_repair", "repair"), ("done", 6, "integration_required", "integrate"),
    ("integrated", 3, "passed", "complete")])
def test_status_gate_never_claims_false_success(invoke, project, status, code, gate, action):
    repo, plan = project
    ledger = Ledger(str(repo / ".cld-ledger.json"))
    with ledger.writer():
        ledger.bind(str(repo), [SliceTask("A", "implement", ["implementation.py"], "test_acceptance.py")], real_git_runner)
        commit = real_git_runner(["git", "rev-parse", "HEAD"], str(repo))[1].strip()
        ledger.set("A", status=status, commit=commit if status in ("done", "integrated") else None,
            collection={"ref": "refs/cld/accepted/A", "commit": commit} if status in ("done", "integrated") else {})
        if status == "integrated":
            ledger.build["integration_proof"] = {"commit": commit}
        ledger.save()
    proc, data = invoke("--status", "--repo", repo, "--json", "--host", "claude-code")
    assert proc.returncode == code and data["gate"] == gate and data["next_action"] == action
    assert data["run_id"] == ledger.build["run_id"]
    if status in ("done", "integrated"):
        assert any(ref["commit"] == commit and ref["ref"] == "refs/cld/accepted/A" for ref in data["accepted_refs"])


def test_usage_is_local_and_unknown_is_null(invoke, project):
    repo, _ = project
    ledger = Ledger(str(repo / ".cld-ledger.json"))
    with ledger.writer():
        ledger.bind(str(repo), [SliceTask("A", "implement", ["implementation.py"], "test_acceptance.py")], real_git_runner)
        ledger.set("A", model="antigravity:unavailable", token_usage={}, cost=None)
        ledger.save()
    proc, data = invoke("--usage", "--repo", repo, "--json")
    assert proc.returncode == 0 and data["command"] == "usage"
    assert data["usage"]["cost"] is None and data["usage"]["total"] is None


def test_state_action_failure_is_structured(invoke, project):
    repo, plan = project
    for flags in (("--integrate",), ("--mark-repaired", "missing")):
        proc, data = invoke(plan, "--repo", repo, *flags, "--json")
        assert proc.returncode in (4, 5) and data["errors"]


def test_slice_detail_and_attempt_containment(invoke, project):
    repo, _ = project
    ledger = Ledger(str(repo / ".cld-ledger.json"))
    with ledger.writer():
        ledger.bind(str(repo), [SliceTask("A", "implement", ["implementation.py"], "test_acceptance.py")], real_git_runner)
        ledger.save()
    _, data = invoke("--status", "--repo", repo, "--json", "--slice", "A")
    assert data["details"]["slice_id"] == "A"
    proc, data = invoke("--status", "--repo", repo, "--json", "--slice", "A", "--attempt", "../outside")
    assert proc.returncode == 5 and data["errors"]


def test_default_response_is_bounded(invoke, project):
    repo, _ = project
    ledger = Ledger(str(repo / ".cld-ledger.json"))
    with ledger.writer():
        ledger.bind(str(repo), [SliceTask("A", "implement", ["implementation.py"], "test_acceptance.py")], real_git_runner)
        ledger.get("A").history = [{"raw_log": "x" * 1000000}]
        ledger.save()
    proc, _ = invoke("--status", "--repo", repo, "--json")
    assert len(proc.stdout.encode("utf-8")) < 32768


def test_engine_owns_cli_and_host_is_telemetry_only(monkeypatch):
    import importlib.util
    assert importlib.util.find_spec("cld.cli") is not None, "Reusable command handling must live in engine"
    from cld import cli, telemetry
    assert callable(cli.main)
    assert len((ROOT / "skill/scripts/run_delivery.py").read_text(encoding="utf-8").splitlines()) < 150
    assert hasattr(telemetry, "set_host")
    events = []
    class Sink:
        def emit(self, event): events.append(event)
    telemetry.set_sink(Sink())
    try:
        telemetry.set_host("codex"); telemetry.emit("test")
        assert events[-1]["host"] == "codex"
    finally:
        telemetry.set_host(None); telemetry.set_sink(None)
