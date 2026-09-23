"""T13B red acceptance for a portable Codex marketplace and repo guidance."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("antigravity", "cursor", "opencode")


def _isolated_generator(tmp_path):
    isolated = tmp_path / "isolated generator repo"
    (isolated / "generator").mkdir(parents=True)
    shutil.copy2(ROOT / "generator" / "build_plugins.py", isolated / "generator" / "build_plugins.py")
    shutil.copy2(ROOT / "VERSION", isolated / "VERSION")
    dist = isolated / "dist"
    for provider in PROVIDERS:
        source = dist / "codex" / f"cross-llm-{provider}"
        (source / "scripts" / "cld").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            f"---\nname: cross-llm-{provider}\ndescription: delivery\n---\n", encoding="utf-8")
        (source / "scripts" / "run_delivery.py").write_text("print('ok')\n", encoding="utf-8")
        (source / "scripts" / "cld" / "__init__.py").write_text("", encoding="utf-8")
    return isolated, dist


def _run(isolated, dist, out):
    return subprocess.run([sys.executable, str(isolated / "generator" / "build_plugins.py"),
        "--host", "codex", "--dist-root", str(dist), "--out-root", str(out)],
        cwd=isolated, stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=45)


def _snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_catalog_has_three_contained_local_plugin_sources(tmp_path):
    isolated, dist = _isolated_generator(tmp_path)
    out = tmp_path / "marketplace root with spaces"
    legacy = out / "cross-llm-opencode" / "KEEP"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("claude", encoding="utf-8")
    result = _run(isolated, dist, out)
    assert result.returncode == 0, result.stderr + result.stdout
    catalog_path = out / ".agents" / "plugins" / "marketplace.json"
    assert catalog_path.is_file(), "Codex marketplace catalog was not generated"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert catalog["name"] == "cross-llm-delivery-codex"
    assert catalog["interface"]["displayName"]
    assert {p["name"] for p in catalog["plugins"]} == {
        f"cross-llm-{provider}" for provider in PROVIDERS}
    assert len(catalog["plugins"]) == 3
    for entry in catalog["plugins"]:
        name = entry["name"]
        assert entry["source"] == {"source": "local", "path": f"./codex/{name}"}
        assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
        assert entry["category"] == "Productivity"
        plugin = (out / entry["source"]["path"]).resolve()
        assert plugin.is_relative_to(out.resolve())
        assert json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))["name"] == name
        assert (plugin / "skills" / name / "SKILL.md").is_file()
    assert legacy.read_text(encoding="utf-8") == "claude"
    before = _snapshot(out)
    again = _run(isolated, dist, out)
    assert again.returncode == 0, again.stderr + again.stdout
    assert _snapshot(out) == before


def test_missing_input_fails_before_catalog_or_packages_change(tmp_path):
    isolated, dist = _isolated_generator(tmp_path)
    out = tmp_path / "marketplace"
    assert _run(isolated, dist, out).returncode == 0
    before = _snapshot(out)
    (dist / "codex" / "cross-llm-antigravity" / "SKILL.md").write_text(
        "---\nname: cross-llm-antigravity\ndescription: changed\n---\n", encoding="utf-8")
    shutil.rmtree(dist / "codex" / "cross-llm-cursor")
    result = _run(isolated, dist, out)
    assert result.returncode != 0
    assert _snapshot(out) == before


def test_default_codex_output_includes_catalog(tmp_path):
    isolated, _ = _isolated_generator(tmp_path)
    result = subprocess.run([sys.executable, str(isolated / "generator" / "build_plugins.py"),
        "--host", "codex"], cwd=isolated, stdin=subprocess.DEVNULL,
        text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stderr + result.stdout
    assert (isolated / "dist" / "plugins" / ".agents" / "plugins" / "marketplace.json").is_file()
    assert not (isolated / "plugins").exists()


def test_repository_maintainer_guidance_is_concise_and_local():
    guidance = ROOT / "AGENTS.md"
    assert guidance.is_file(), "repository AGENTS.md guidance is missing"
    body = guidance.read_text(encoding="utf-8")
    assert len(body.splitlines()) <= 80
    for pointer in ("IMPLEMENTATION_PLAN.md", "HANDOFF.md", "generator/build_skill.py",
                    "generator/build_plugins.py", "tests/test_t13b_marketplace.py"):
        assert pointer in body
    assert "token" in body.lower()
    assert "dist/" in body


def test_install_docs_and_ci_cover_catalog_without_ide_plugin_claim():
    guide = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    assert "codex plugin marketplace add" in guide
    assert "codex plugin list" in guide
    assert "generator/build_plugins.py --host codex" in guide
    assert "IDE" in guide and "standalone" in guide
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert ".agents/plugins/marketplace.json" in workflow
    assert "codex plugin marketplace add" not in workflow
