"""T14: fresh-process, real-Git, two-layer host-neutral CLI acceptance."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cld.ledger import Ledger
from tests.integration.harness import init_repo
from generator.build_skill import build_one


ROOT = Path(__file__).resolve().parents[2]
FAKE_CLI = ROOT / "tests/integration/t14_fake_cli.py"

pytestmark = pytest.mark.integration


def test_claude_bundle_frontmatter_precedes_provenance(tmp_path):
    bundle = build_one("opencode", out_root=tmp_path, host="claude-code")
    skill = (bundle / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: cross-llm-opencode\n")
    assert "\n---\n<!-- GENERATED from cross-llm-delivery@" in skill


@pytest.mark.parametrize("host", ("claude-code", "codex"))
@pytest.mark.parametrize("provider", ("antigravity", "cursor", "opencode"))
def test_each_generated_host_loads_only_its_provider_contract(tmp_path, host, provider):
    bundle = build_one(provider, out_root=tmp_path / "bundles with spaces", host=host)
    probe = (
        "from cld.providers_api import load_providers, all_providers\n"
        "from cld.executors import get_executor\n"
        "from cld.executors.base import Executor\n"
        "load_providers()\n"
        f"assert [p.name for p in all_providers()] == [{provider!r}]\n"
        f"executor = get_executor({provider!r}, runner=lambda args, cwd: (0, ''))\n"
        "assert isinstance(executor, Executor)\n"
    )
    env = {**os.environ, "PYTHONPATH": str(bundle / "scripts"), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, env=env,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_worktree_root_that_contains_repo_is_blocked_without_dispatch(tmp_path):
    repo = Path(init_repo(tmp_path / "sandbox repo"))
    plan = repo / "plan.md"
    plan.write_text("## SLICE: A\nbrief: test\nfiles: a.py\nacceptance_test_path: test_a.py\ndeps:\n",
                    encoding="utf-8")
    denied = invoke(repo, tmp_path, str(plan), "--step", "--worktree-root", "..",
                    "--executor", "opencode:opencode/kimi-k3")
    assert denied["gate"] == "blocked"
    assert denied["next_action"] == "correct_input"
    assert Ledger.load(str(repo / ".cld-ledger.json")).get("A").attempts == 0

    unavailable = invoke(repo, tmp_path, str(plan), "--step", "--worktree-root", "plan.md",
                         "--executor", "opencode:opencode/kimi-k3")
    assert unavailable["gate"] == "blocked"
    assert unavailable["errors"]
    assert Ledger.load(str(repo / ".cld-ledger.json")).get("A").attempts == 0


def invoke(repo, cwd, *args, fake=False):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(ROOT / "engine"), str(ROOT))),
           "PYTHONDONTWRITEBYTECODE": "1"}
    command = [sys.executable, str(FAKE_CLI)] if fake else [sys.executable, "-m", "cld"]
    result = subprocess.run(command + [*args, "--repo", str(repo), "--json", "--host", "codex"],
        cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    response = json.loads(result.stdout)
    assert result.returncode == response["gate_code"], result.stdout + result.stderr
    assert response["repository"] == str(repo.resolve())
    return response


def test_two_layer_stop_resume_from_different_cwd_and_fresh_process(tmp_path):
    repo = Path(init_repo(tmp_path / "delivery repo with spaces"))
    outside = tmp_path / "other working directory"
    outside.mkdir()
    (repo / "test_a.py").write_text(
        "from pathlib import Path\n"
        "def test_a():\n"
        "    p = Path(__file__).with_name('a.py')\n"
        "    assert p.exists()\n"
        "    assert p.read_text() == 'VALUE = 2\\n'\n", encoding="utf-8")
    (repo / "test_b.py").write_text(
        "from pathlib import Path\n"
        "def test_b():\n"
        "    p = Path(__file__).with_name('b.py')\n"
        "    assert p.exists()\n"
        "    assert 'RESULT = VALUE + 3' in p.read_text()\n", encoding="utf-8")
    (repo / "test_integration.py").write_text(
        "from pathlib import Path\n"
        "def test_combined():\n"
        "    root = Path(__file__).parent\n"
        "    assert (root / 'a.py').exists()\n"
        "    assert (root / 'a.py').read_text() == 'VALUE = 2\\n'\n"
        "    if (root / 'b.py').exists():\n"
        "        assert (root / 'b.py').read_text() == 'from a import VALUE\\nRESULT = VALUE + 3\\n'\n",
        encoding="utf-8")
    plan = repo / "plan.md"
    plan.write_text("## SLICE: A\nbrief: create a\nfiles: a.py\nacceptance_test_path: test_a.py\ndeps:\n\n"
                    "## SLICE: B\nbrief: consume a\nfiles: b.py\nacceptance_test_path: test_b.py\ndeps: A\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "committed acceptance"], cwd=repo, check=True, capture_output=True)

    common = (str(plan), "--worktree-root", ".cld/t14-worktrees", "--executor", "opencode:opencode/kimi-k3")
    preview = invoke(repo, outside, *common, "--dry-run")
    assert preview["gate"] == "pending" and len(preview["layers"]) == 2
    first = invoke(repo, repo, *common, "--step", fake=True)
    assert first["gate"] == "integration_required"
    run_id = first["run_id"]
    ledger = Path(first["ledger"])
    assert ledger.exists()

    # The next invocation knows only committed plan + ledger; it cannot dispatch B yet.
    stopped = invoke(repo, outside, "--status")
    assert stopped["run_id"] == run_id and stopped["gate"] == "integration_required"
    again = invoke(repo, outside, *common, "--step", fake=True)
    assert again["gate"] == "failed"
    assert Ledger.load(str(ledger)).get("B").attempts == 0

    merged_a = invoke(repo, outside, *common, "--integrate", "--integration-tests", "test_integration.py")
    assert merged_a["gate"] == "pending"
    second = invoke(repo, outside, *common, "--step", fake=True)
    assert second["gate"] == "integration_required" and second["run_id"] == run_id
    merged_b = invoke(repo, outside, *common, "--integrate", "--integration-tests", "test_integration.py")
    assert merged_b["gate"] == "passed"
    final = invoke(repo, outside, "--status")
    assert final["gate"] == "passed" and final["next_action"] == "complete"
    assert {key: entry.attempts for key, entry in Ledger.load(str(ledger)).entries.items()} == {"A": 1, "B": 1}
    assert (repo / ".cld/t14-worktrees").is_dir()
