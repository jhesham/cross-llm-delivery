"""Antigravity skills call the driver by its absolute path in one command.

Each approval then shows one plain driver command instead of
`Set-Location <skill>; python scripts/run_delivery.py ...`. Headless `agy -p` cannot ask
for approval (in agy 1.5.1 only exact-command allow rules matched), so the skill says to
lead from an interactive session.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.v060.test_agy_host_gen import PROVIDERS, _build
from tests.v060.test_unified_hosts import _unified

DRIVER = 'python "<skill-dir>/scripts/run_delivery.py"'


def _pages(bundle: Path):
    return {name: (bundle / name).read_text(encoding="utf-8")
            for name in ("SKILL.md", "references/antigravity-workflow.md")}


def _assert_absolute_driver(bundle: Path):
    for name, text in _pages(bundle).items():
        assert "python scripts/run_delivery.py" not in text, f"{name} still runs the driver relatively"
        assert "python <skill-dir>/" not in text, f"{name} leaves the driver path unquoted"
        assert DRIVER in text, f"{name} does not show the absolute driver path"
    skill = _pages(bundle)["SKILL.md"]
    assert "`Set-Location`" in skill and "`cd`" in skill  # do not change folder first
    assert "interactive Antigravity session" in skill


@pytest.mark.parametrize("provider", PROVIDERS)
def test_single_executor_skills_call_the_driver_by_absolute_path(tmp_path, provider):
    _assert_absolute_driver(_build(provider, tmp_path))


def test_the_all_executors_skill_calls_the_driver_by_absolute_path(tmp_path):
    _assert_absolute_driver(_unified(tmp_path, "antigravity"))


def test_the_documented_preview_runs_from_an_installed_path_with_spaces(tmp_path):
    from tests.v060.test_agy_host_e2e import _repo
    skill = tmp_path / "skills with spaces" / "cross-llm-codex-agy"
    shutil.copytree(_build("codex", tmp_path / "out"), skill)
    repo = _repo(tmp_path / "target repo")
    line = next(l for l in (skill / "SKILL.md").read_text(encoding="utf-8").splitlines()
                if l.startswith("python ") and "--dry-run" in l)
    command = (line.replace("python ", f'"{sys.executable}" ', 1)
               .replace("<skill-dir>", str(skill)).replace("<plan.md>", str(repo / "plan.md"))
               .replace("<dir>", str(repo)))
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(command, shell=True, cwd=tmp_path, env=env, capture_output=True,
                            text=True, stdin=subprocess.DEVNULL, timeout=120)
    payload = json.loads(result.stdout)
    assert payload["gate_code"] == 0 and payload["slice_count"] == 1, result.stdout + result.stderr
