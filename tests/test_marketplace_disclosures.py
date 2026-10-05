"""Portable reviewer resources, exercised without a provider or installed skill."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from generator.build_skill import build_one
from generator import build_plugins

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("antigravity", "opencode", "cursor", "codex", "claude")
HOSTS = ("claude-code", "codex")


def local_links(text):
    return [target.split("#", 1)[0] for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
            if not target.startswith(("https://", "http://", "#"))]


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("provider", PROVIDERS)
def test_bundle_has_portable_matching_policy_resources(tmp_path, host, provider):
    bundle = build_one(provider, host=host, out_root=tmp_path, smoke=False)
    readme = bundle / "README.md"
    assert readme.is_file(), "Reviewer instructions must travel with either host bundle"
    targets = local_links(readme.read_text(encoding="utf-8"))
    assert {"PRIVACY.md", "SECURITY.md"} <= set(targets)
    for target in targets:
        assert (bundle / target).is_file(), f"Unportable reviewer link: {target}"
    skill_links = local_links((bundle / "SKILL.md").read_text(encoding="utf-8"))
    assert "README.md" in skill_links, "Host instructions must expose reviewer disclosures"
    for name in ("PRIVACY.md", "SECURITY.md"):
        assert (bundle / name).read_bytes() == (ROOT / name).read_bytes(), name


@pytest.mark.parametrize("host", HOSTS)
def test_packaged_demo_is_offline_and_leaves_target_untouched(tmp_path, host):
    bundle = build_one("claude", host=host, out_root=tmp_path / "build", smoke=False)
    demo = bundle / "examples" / "demo-plan.md"
    assert demo.is_file(), "Both hosts must ship the documented preview input"
    repo = tmp_path / "review repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)
    before = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    env = dict(os.environ, PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, str(bundle / "scripts" / "run_delivery.py"), str(demo),
         "--repo", str(repo), "--host", host, "--dry-run", "--json"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["gate_code"] == 0
    assert payload["layers"] == [["T1", "T3"], ["T2"]]
    assert payload.get("run_id") is None
    assert not payload.get("attempts")
    after = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    assert after == before, "Preview must not create a ledger, worktree, refs or event files"


@pytest.mark.parametrize("host", HOSTS)
def test_plugin_descriptions_disclose_independence_without_changing_names(host):
    descriptions = build_plugins.CODEX_DESCRIPTIONS if host == "codex" else build_plugins.DESCRIPTIONS
    assert set(descriptions) == set(PROVIDERS)
    for provider, description in descriptions.items():
        lower = description.lower()
        assert "independent" in lower and "endors" in lower, provider
        assert "openai" in lower and "anthropic" in lower, provider


def test_public_catalog_discloses_independence_for_all_five_packages():
    catalog = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert {p["name"] for p in catalog["plugins"]} == {f"cross-llm-{p}" for p in PROVIDERS}
    for entry in [catalog, *catalog["plugins"]]:
        lower = entry["description"].lower()
        assert "independent" in lower and "endors" in lower, entry["name"]
        assert "openai" in lower and "anthropic" in lower, entry["name"]
