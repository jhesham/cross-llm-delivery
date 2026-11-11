"""v0.7.0 GENMCP: entry script in every bundle, Claude plugin .mcp.json, MCP skill text."""
import contextlib
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ("antigravity", "claude", "codex", "cursor", "opencode")
HOSTS = ("claude-code", "codex", "antigravity")
TEMPLATES = ("skill/SKILL.template.md", "skill/SKILL.unified.template.md",
             "skill/hosts/codex/SKILL.template.md", "skill/hosts/codex/SKILL.unified.template.md",
             "skill/hosts/antigravity/SKILL.template.md",
             "skill/hosts/antigravity/SKILL.unified.template.md",
             "skill/hosts/codex/references/codex-workflow.md",
             "skill/hosts/antigravity/references/antigravity-workflow.md")
PLUGIN_ARGS = ["${CLAUDE_PLUGIN_ROOT}/skills/cross-llm-delivery/scripts/cld_mcp.py"]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    from generator import build_plugins
    from generator.build_skill import build_one, build_unified
    out = tmp_path_factory.mktemp("dist")
    bundles = {}
    for host in HOSTS:
        for provider in PROVIDERS:
            bundles[(host, provider)] = Path(build_one(provider, out_root=out, smoke=False, host=host))
        bundles[(host, "unified")] = Path(build_unified(out_root=out, smoke=False, host=host))
    plugins = tmp_path_factory.mktemp("plugins")
    with contextlib.redirect_stdout(io.StringIO()):
        assert build_plugins.main(["--dist-root", str(out), "--out-root", str(plugins)]) == 0
        assert build_plugins.main(["--host", "codex", "--dist-root", str(out),
                                   "--out-root", str(plugins)]) == 0
    return bundles, plugins


def test_every_bundle_vendors_the_entry_script(built):
    source = ROOT / "skill" / "scripts" / "cld_mcp.py"
    assert source.is_file(), "skill/scripts/cld_mcp.py not implemented"
    for key, bundle in built[0].items():
        vendored = bundle / "scripts" / "cld_mcp.py"
        assert vendored.is_file(), key
        assert vendored.read_bytes() == source.read_bytes(), key


def test_only_the_unified_claude_plugin_declares_the_server(built):
    plugins = built[1]
    found = sorted(plugins.rglob(".mcp.json"))
    assert found == [plugins / "cross-llm-delivery" / ".mcp.json"], found
    server = json.loads(found[0].read_text(encoding="utf-8"))["mcpServers"]["cld"]
    assert server["command"] == "python"
    assert server["args"] == PLUGIN_ARGS
    assert server["env"] == {"CLD_HOST": "claude-code"}
    assert (plugins / "cross-llm-delivery" / "skills" / "cross-llm-delivery" / "scripts"
            / "cld_mcp.py").is_file()


def test_skills_prefer_tools_and_keep_cli(built):
    for key, bundle in built[0].items():
        text = (bundle / "SKILL.md").read_text(encoding="utf-8")
        for needle in ("cld_step", "cld_job", "wait_seconds"):
            assert needle in text, (key, needle)
        assert "run_delivery.py" in text, (key, "CLI instructions removed")


def test_host_workflow_references_mention_tools(built):
    for (host, provider), bundle in built[0].items():
        name = {"codex": "codex-workflow.md", "antigravity": "antigravity-workflow.md"}.get(host)
        if name and (provider == "unified" or (bundle / "references" / name).exists()):
            text = (bundle / "references" / name).read_text(encoding="utf-8")
            assert "cld_step" in text and "cld_job" in text, (host, provider)


def test_added_text_is_ascii_and_cp1252(built):
    for rel in TEMPLATES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "cld_job" in text, f"{rel} lacks the MCP tools section"
        for line in text.splitlines():
            if "cld_" in line or "MCP" in line:
                assert line.isascii(), (rel, line)
    for key, bundle in built[0].items():
        (bundle / "SKILL.md").read_text(encoding="utf-8").encode("cp1252")


def test_codex_skill_stays_within_limits(built):
    for (host, provider), bundle in built[0].items():
        if host == "codex":
            text = (bundle / "SKILL.md").read_text(encoding="utf-8")
            assert len(text.splitlines()) <= 130, (provider, len(text.splitlines()))
            assert len(text) <= 9000, (provider, len(text))
