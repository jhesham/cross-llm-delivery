"""v0.4.0 fifth-provider wiring for both hosts."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("host", ["claude-code", "codex"])
def test_claude_bundle_has_no_guessed_default(tmp_path, host):
    from generator.build_skill import build_one
    skill = (build_one("claude", out_root=tmp_path / "out", host=host) / "SKILL.md").read_text(encoding="utf-8")
    assert "claude:<model-id>@<effort>" in skill and "no default" in skill.lower()
    assert "+fast" not in skill


def test_codex_policy_keeps_fast_guidance(tmp_path):
    from generator.build_skill import build_one
    skill = (build_one("codex", out_root=tmp_path / "out", host="claude-code") / "SKILL.md").read_text(encoding="utf-8")
    assert "codex:gpt-6-luna@max+fast" in skill


def test_plugins_and_marketplace_list_claude(tmp_path):
    from generator import build_plugins
    (tmp_path / "cross-llm-claude").mkdir()
    assert "claude" in build_plugins._package_providers(tmp_path, host="claude-code")
    assert "claude" in build_plugins.DESCRIPTIONS and "claude" in build_plugins.CODEX_DESCRIPTIONS
    names = [p["name"] for p in json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())["plugins"]]
    assert "cross-llm-claude" in names


def test_codex_installer_accepts_claude():
    from generator.install_codex import SUPPORTED_NAMES
    assert "cross-llm-claude" in SUPPORTED_NAMES


def test_install_hint_names_login():
    from cld.cli import _install_hint
    assert "claude auth login" in _install_hint("claude")
