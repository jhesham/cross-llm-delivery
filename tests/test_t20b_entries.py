"""Candidate packaging boundaries: discoverable catalogs and bounded entry context."""
from pathlib import Path
import json
import re

import pytest
import yaml

from generator.build_skill import build_one
from generator.release import CommandError, _validate_manifests

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("antigravity", "cursor", "opencode", "codex", "claude")


def test_claude_marketplace_resolves_all_four_committed_plugins():
    catalog = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    entries = catalog["plugins"]
    assert {entry["name"] for entry in entries} == {"cross-llm-" + p for p in PROVIDERS}
    assert len(entries) == len(PROVIDERS)
    for entry in entries:
        source = (ROOT / entry["source"]).resolve()
        assert source.is_relative_to(ROOT)
        manifest = json.loads((source / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == entry["name"]
        # Claude packages intentionally follow Git commits without a fixed
        # version field; an explicitly versioned manifest must still agree.
        assert manifest.get("version", (ROOT / "VERSION").read_text().strip()) == (
            ROOT / "VERSION").read_text().strip()
        assert (source / "skills" / entry["name"] / "SKILL.md").is_file()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("host", ("claude-code", "codex"))
def test_entry_context_budget_and_linked_references(tmp_path, host, provider):
    bundle = build_one(provider, out_root=tmp_path, host=host)
    text = (bundle / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    meta = yaml.safe_load(text.split("---", 2)[1])
    assert meta["name"] == "cross-llm-" + provider
    assert len(text) <= 8000  # <=2k characters/4 planning estimate; not billing.
    refs = set(re.findall(r"references/[A-Za-z0-9_.-]+\.md", text))
    assert refs
    for ref in refs:
        assert (bundle / ref).is_file(), ref
    for original, name in (("SKILL.fragment.md", "provider.md"), ("setup.md", "provider-setup.md")):
        assert (bundle / "references" / name).read_bytes() == (
            ROOT / "engine/cld_providers" / provider / original).read_bytes()


@pytest.mark.parametrize("mode", ("current", "stale", "missing", "null-version"))
def test_native_release_gate_checks_git_versioned_claude_bundles(tmp_path, mode):
    version = (ROOT / "VERSION").read_text().strip()
    (tmp_path / "VERSION").write_text(version + "\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="' + version + '"\n')
    claude = tmp_path / "plugins/cross-llm-codex/.claude-plugin"
    codex = tmp_path / "dist/release-plugins/codex/cross-llm-codex"
    claude.mkdir(parents=True)
    codex.mkdir(parents=True)
    manifest = json.loads((ROOT / "plugins/cross-llm-codex/.claude-plugin/plugin.json").read_text())
    if mode == "null-version":
        manifest["version"] = None
    (claude / "plugin.json").write_text(json.dumps(manifest))
    (codex / "plugin.json").write_text(json.dumps({"name": "cross-llm-codex", "version": version}))
    if mode != "missing":
        skill = claude.parent / "skills/cross-llm-codex/SKILL.md"
        skill.parent.mkdir(parents=True)
        text = (ROOT / "plugins/cross-llm-codex/skills/cross-llm-codex/SKILL.md").read_text(encoding="utf-8")
        if mode == "stale":
            text = text.replace("v" + version, "v0.0.0")
        skill.write_text(text, encoding="utf-8")
    if mode == "current":
        _validate_manifests(tmp_path)
    else:
        with pytest.raises(CommandError):
            _validate_manifests(tmp_path)
