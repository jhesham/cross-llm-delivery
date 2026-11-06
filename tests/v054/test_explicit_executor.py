"""v0.5.4 EXPLICITEXEC: with several executors installed, --step never guesses one."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "skill" / "scripts" / "run_delivery.py"
REFUSAL = "No executor chosen"


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _target(tmp_path):
    repo = tmp_path / "target"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "base")
    plan = tmp_path / "plan.md"
    plan.write_text("## SLICE: T1\nbrief: Make test_x pass.\nfiles: src/x.py\n"
                    "acceptance_test_path: tests/test_x.py\ndeps:\n", encoding="utf-8")
    return repo, plan


def _step(tmp_path, *extra):
    repo, plan = _target(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "engine"),
           "AGY_CMD": str(tmp_path / "no-such-agy.exe")}   # never launch a real executor
    env.pop("CLD_EXECUTOR_DEPTH", None)
    return subprocess.run([sys.executable, str(DRIVER), str(plan), "--repo", str(repo), "--step",
                           "--json", "--budget-attempts", "1", *extra],
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300)


def test_step_without_executor_is_refused_when_several_executors_are_installed(tmp_path):
    result = _step(tmp_path)
    out = result.stdout + result.stderr
    assert REFUSAL in out, out[-2000:]
    assert "--executor" in out
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload.get("gate_code") == 5, payload


def test_an_explicit_executor_is_not_refused(tmp_path):
    result = _step(tmp_path, "--executor", "antigravity:Gemini 4 Argon (High)")
    assert REFUSAL not in result.stdout + result.stderr
