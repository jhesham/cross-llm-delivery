"""v0.6.0 integration: generate, install and drive an Antigravity-host bundle offline."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.evidence._lazy import resolve


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.invalid")
    _git(path, "config", "user.name", "T")
    (path / "test_a.py").write_text("def test_a():\n    assert False\n", encoding="utf-8")
    (path / "plan.md").write_text(
        "## SLICE: A\nbrief: create a\nfiles: a.py\nacceptance_test_path: test_a.py\ndeps:\n",
        encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "base")
    return path


def _drive(driver: Path, cwd: Path, *args) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, str(driver), *args, "--json", "--host", "antigravity"],
                            cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=120)
    payload = json.loads(result.stdout)
    assert result.returncode == payload["gate_code"], result.stdout + result.stderr
    return payload


@pytest.mark.parametrize("bundle_name", ("cross-llm-opencode-agy", "cross-llm-delivery-agy"))
def test_installed_antigravity_bundle_previews_and_reports_status(tmp_path, capsys, bundle_name):
    build_one = resolve("generator.build_skill", "build_one")
    build_unified = resolve("generator.build_skill", "build_unified")
    install = resolve("generator.install_antigravity", "main")
    dist = tmp_path / "dist with spaces"
    if bundle_name == "cross-llm-delivery-agy":
        bundle = Path(build_unified(out_root=dist, smoke=False, host="antigravity"))
    else:
        bundle = Path(build_one("opencode", out_root=dist, smoke=False, host="antigravity"))
    repo = _repo(tmp_path / "target repo")
    assert install(["--install", "--scope", "workspace", "--scope-root", str(repo),
                    "--bundle", str(bundle)]) == 0
    capsys.readouterr()
    installed = repo / ".agents" / "skills" / bundle_name
    shutil.rmtree(dist)  # the installed copy must stand alone
    nested = repo / "nested dir"
    nested.mkdir()
    driver = installed / "scripts" / "run_delivery.py"
    preview = _drive(driver, nested, str(repo / "plan.md"), "--repo", str(repo), "--dry-run")
    assert preview["gate"] == "pending" and len(preview["layers"]) == 1
    status = _drive(driver, nested, "--status", "--repo", str(repo))
    assert status["repository"] == str(repo.resolve())


def test_codex_and_antigravity_installs_coexist_in_one_repository(tmp_path, capsys):
    build_one = resolve("generator.build_skill", "build_one")
    install_agy = resolve("generator.install_antigravity", "main")
    install_codex = resolve("generator.install_codex", "main")
    dist = tmp_path / "dist"
    codex_bundle = Path(build_one("opencode", out_root=dist, smoke=False, host="codex"))
    agy_bundle = Path(build_one("opencode", out_root=dist, smoke=False, host="antigravity"))
    repo = _repo(tmp_path / "shared repo")
    assert install_codex(["--install", "--scope-root", str(repo), "--bundle", str(codex_bundle)]) == 0
    assert install_agy(["--install", "--scope", "workspace", "--scope-root", str(repo),
                        "--bundle", str(agy_bundle)]) == 0
    capsys.readouterr()
    skills = repo / ".agents" / "skills"
    codex_skill = (skills / "cross-llm-opencode" / "SKILL.md").read_text(encoding="utf-8")
    agy_skill = (skills / "cross-llm-opencode-agy" / "SKILL.md").read_text(encoding="utf-8")
    assert codex_skill.startswith("---\nname: cross-llm-opencode\n") and "Codex is the lead" in codex_skill
    assert agy_skill.startswith("---\nname: cross-llm-opencode-agy\n") and "Antigravity is the lead" in agy_skill
    assert (codex_bundle / "SKILL.md").read_text(encoding="utf-8") == codex_skill
    for name in ("cross-llm-opencode", "cross-llm-opencode-agy"):
        preview = _drive(skills / name / "scripts" / "run_delivery.py", repo,
                         str(repo / "plan.md"), "--repo", str(repo), "--dry-run")
        assert preview["gate"] == "pending", name
