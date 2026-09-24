"""Stable external plan, CLI result, and legacy-state fixtures for T17C."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cld.ledger import Ledger, StateError, resolve_ledger
from cld.plan.slice import load_slices
from tests.integration.harness import init_repo, real_git_runner


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/compatibility"
PLAN = FIXTURES / "plan-v1.md"
LEGACY = FIXTURES / "legacy-ledger-v0.json"


def test_versioned_plan_fixture_previews_as_stable_json_without_state(tmp_path):
    repo = Path(init_repo(tmp_path / "fixture repo with spaces"))
    tasks = load_slices(PLAN.read_text(encoding="utf-8"))
    assert [(task.id, task.deps) for task in tasks] == [("A", []), ("B", ["A"])]
    env = {**os.environ, "PYTHONPATH": str(ROOT / "engine"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-m", "cld", str(PLAN), "--repo", str(repo),
        "--dry-run", "--json", "--host", "codex"], cwd=tmp_path, env=env,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    response = json.loads(result.stdout)
    assert response["schema_version"] == 1
    assert (response["command"], response["gate"], response["gate_code"],
            response["next_action"]) == ("preview", "pending", 0, "resume")
    assert response["layers"] == [["A"], ["B"]]
    assert response["repository"] == str(repo.resolve())
    assert response["ledger"] == str(repo / ".cld-ledger.json")
    assert not Path(response["ledger"]).exists()


def test_legacy_state_fixture_requires_migration_and_round_trips_schema_two(tmp_path):
    repo = Path(init_repo(tmp_path / "legacy repo with spaces"))
    path = Path(resolve_ledger(repo))
    original = LEGACY.read_bytes()
    path.write_bytes(original)
    tasks = load_slices(PLAN.read_text(encoding="utf-8"))
    with Ledger.load(str(path)).writer(refresh=True) as ledger:
        with pytest.raises(StateError, match="migrate-ledger"):
            ledger.bind(str(repo), tasks, real_git_runner)
    assert path.read_bytes() == original
    with Ledger.load(str(path)).writer(refresh=True) as ledger:
        ledger.bind(str(repo), tasks, real_git_runner, migrate=True)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 2
    assert saved["build"]["repo"] == str(repo.resolve())
    assert saved["build"]["integrated_sha"] is None
    assert saved["entries"]["A"]["attempts"] == 2
    assert saved["entries"]["A"]["status"] == "failed"
    assert saved["entries"]["B"]["status"] == "pending"
    assert Path(saved["build"]["backup"]).read_bytes() == original
    reloaded = Ledger.load(str(path))
    assert reloaded.build["run_id"] == saved["build"]["run_id"]
