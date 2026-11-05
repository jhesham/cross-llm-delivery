"""Unified cross-llm-delivery plugin: one Claude Code plugin with every executor, chosen per build."""
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.evidence._lazy import resolve

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ("antigravity", "claude", "codex", "cursor", "opencode")
PROJECT = "https://github.com/jhesham/cross-llm-delivery"


def _build(tmp_path):
    return Path(resolve("generator.build_skill", "build_unified")(out_root=tmp_path, smoke=True))


def test_unified_bundle_vendors_every_provider_and_loads_them_in_isolation(tmp_path):
    out = _build(tmp_path)
    assert out == tmp_path / "cross-llm-delivery", out
    scripts = out / "scripts"
    for p in PROVIDERS:
        assert (scripts / "cld_providers" / p / "provider.py").is_file(), p
        assert (out / "references" / "providers" / f"{p}.md").is_file(), p
        assert (out / "references" / "providers" / f"{p}-setup.md").is_file(), p
    shims = {f.name for f in (ROOT / "engine/cld/executors").glob("*.py")}
    assert shims <= {f.name for f in (scripts / "cld" / "executors").glob("*.py")}, "no executor shim trimmed"
    probe = ("from cld.providers_api import load_providers, all_providers; load_providers(); "
             "print(sorted(p.name for p in all_providers()))")
    result = subprocess.run([sys.executable, "-c", probe], cwd=scripts, capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": str(scripts)}, timeout=60)
    assert result.stdout.strip() == str(sorted(PROVIDERS)), result.stdout + result.stderr


def test_unified_skill_names_itself_and_requires_an_explicit_executor(tmp_path):
    out = _build(tmp_path)
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: cross-llm-delivery\n"), skill[:80]
    assert "{{" not in skill, "unfilled template placeholder"
    assert "--executor" in skill and all(p in skill for p in PROVIDERS)
    for ref in ("references/delivery-core.md", "references/providers/"):
        assert ref in skill, ref
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "{{" not in readme and "cross-llm-delivery" in readme
    for name in ("PRIVACY.md", "SECURITY.md", "LICENSE", "examples/demo-plan.md"):
        assert (out / name).is_file(), name


def test_committed_unified_plugin_and_marketplace_entry():
    plugin = ROOT / "plugins" / "cross-llm-delivery"
    data = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert data["name"] == "cross-llm-delivery"
    assert data["version"] == (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert data.get("displayName") == "Cross-LLM Delivery"
    assert data.get("documentationUrl") == f"{PROJECT}#readme"
    assert data.get("privacyPolicyUrl") == f"{PROJECT}/blob/main/PRIVACY.md"
    assert data.get("homepage") == PROJECT and data.get("license") == "MIT"
    assert "Independent project" in data["description"]
    keywords = data.get("keywords") or []
    assert "acceptance-tests" in keywords and len(keywords) == len(set(keywords)) <= 8, keywords
    assert (plugin / "skills" / "cross-llm-delivery" / "SKILL.md").is_file()
    icon = (plugin / ".claude-plugin" / "icon.png").read_bytes()
    assert icon[:8] == b"\x89PNG\r\n\x1a\n" and 512 <= int.from_bytes(icon[16:20], "big") <= 2048
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entries = {p["name"]: p for p in market["plugins"]}
    assert entries.get("cross-llm-delivery", {}).get("source") == "./plugins/cross-llm-delivery", sorted(entries)
    assert {f"cross-llm-{p}" for p in PROVIDERS} <= set(entries), "per-provider plugins stay listed"
