"""T17B acceptance: six isolated bundles and committed Claude package freshness."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("antigravity", "cursor", "opencode")
ALL_PROVIDERS = (*PROVIDERS, "codex")


def _run(*args, cwd=ROOT):
    result = subprocess.run([sys.executable, *map(str, args)], cwd=cwd,
                            stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_six_fresh_bundles_and_codex_package_metadata(tmp_path):
    dist = tmp_path / "fresh bundles with spaces"
    for host in ("claude-code", "codex"):
        _run(ROOT / "generator/build_skill.py", "--all", "--host", host,
             "--out-root", dist)
        for provider in ALL_PROVIDERS:
            name = f"cross-llm-{provider}"
            bundle = dist / ("codex" if host == "codex" else "") / name
            skill = (bundle / "SKILL.md").read_text(encoding="utf-8")
            assert name in skill
            assert (bundle / "scripts/run_delivery.py").is_file()
            _run(bundle / "scripts/run_delivery.py", "--help", cwd=tmp_path)
            if host == "codex":
                assert (bundle / "agents/openai.yaml").is_file()
                assert (bundle / "references/codex-workflow.md").is_file()
            else:
                assert not (bundle / "agents/openai.yaml").exists()
                assert (bundle / "README.md").is_file()

    packages = tmp_path / "codex packages"
    _run(ROOT / "generator/build_plugins.py", "--host", "codex",
         "--dist-root", dist, "--out-root", packages)
    catalog = json.loads((packages / ".agents/plugins/marketplace.json").read_text(
        encoding="utf-8"))
    assert {p["name"] for p in catalog["plugins"]} == {
        f"cross-llm-{p}" for p in ALL_PROVIDERS}
    for entry in catalog["plugins"]:
        plugin = (packages / entry["source"]["path"]).resolve()
        assert plugin.is_relative_to(packages.resolve())
        manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == entry["name"]
        assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
        assert (plugin / "skills" / entry["name"] / "SKILL.md").is_file()


def test_freshness_check_detects_content_and_file_set_drift_without_mutation(tmp_path):
    dist = tmp_path / "dist"
    for provider in PROVIDERS:
        source = dist / f"cross-llm-{provider}"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            f"<!-- GENERATED from cross-llm-delivery@abcdef0 (provider: {provider}, v0.2.0) -->\n",
            encoding="utf-8")
    tracked = tmp_path / "plugins"
    _run(ROOT / "generator/build_plugins.py", "--dist-root", dist,
         "--out-root", tracked)
    check = ROOT / "generator/check_plugins_fresh.py"
    _run(check, "--dist-root", dist, "--plugins-root", tracked)
    source_file = tracked / "cross-llm-opencode/skills/cross-llm-opencode/SKILL.md"
    before = source_file.read_bytes()
    source_file.write_bytes(before + b"stale\n")
    result = subprocess.run([sys.executable, str(check), "--dist-root", str(dist),
        "--plugins-root", str(tracked)], cwd=ROOT, capture_output=True, text=True,
        timeout=45)
    assert result.returncode == 1
    assert "changed: 1" in result.stdout
    assert source_file.read_bytes() == before + b"stale\n"
    source_file.write_bytes(before)
    source_file.unlink()
    extra = tracked / "cross-llm-opencode/extra.txt"
    extra.write_text("extra", encoding="utf-8")
    result = subprocess.run([sys.executable, str(check), "--dist-root", str(dist),
        "--plugins-root", str(tracked)], cwd=ROOT, capture_output=True, text=True,
        timeout=45)
    assert result.returncode == 1
    assert "missing: 1" in result.stdout and "extra: 1" in result.stdout
    assert extra.read_text(encoding="utf-8") == "extra"


def test_committed_claude_plugins_match_fresh_generation(tmp_path):
    dist = tmp_path / "dist"
    _run(ROOT / "generator/build_skill.py", "--all", "--out-root", dist)
    result = subprocess.run([sys.executable, str(ROOT / "generator/check_plugins_fresh.py"),
        "--dist-root", str(dist)], cwd=ROOT, capture_output=True, text=True,
        timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
