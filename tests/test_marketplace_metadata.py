"""Generated listing metadata and portable assets; no CLI/model/account needed."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("antigravity", "opencode", "cursor", "codex", "claude")
PROJECT = "https://github.com/jhesham/cross-llm-delivery"


@pytest.fixture
def generated(tmp_path):
    # A copied packager proves metadata/assets do not depend on a live checkout
    # or an installed profile. Deliberately use a different VERSION.
    source = tmp_path / "isolated source"
    (source / "generator").mkdir(parents=True)
    shutil.copy2(ROOT / "generator/build_plugins.py", source / "generator/build_plugins.py")
    (source / "VERSION").write_text("9.8.7\n", encoding="utf-8")
    for host in ("claude-code", "codex"):
        for provider in PROVIDERS:
            bundle = source / "dist" / ("codex" if host == "codex" else "") / f"cross-llm-{provider}"
            bundle.mkdir(parents=True)
            (bundle / "SKILL.md").write_text(
                f"---\nname: cross-llm-{provider}\ndescription: Test-gated slice delivery\n---\n", encoding="utf-8")
    output = tmp_path / "portable output"
    for host in ("claude-code", "codex"):
        result = subprocess.run(
            [sys.executable, str(source / "generator/build_plugins.py"), "--host", host,
             "--out-root", str(output)], cwd=source, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
    return source, output


def manifest(output, host, provider):
    plugin = output / ("codex" if host == "codex" else "") / f"cross-llm-{provider}"
    file = plugin / ("plugin.json" if host == "codex" else ".claude-plugin/plugin.json")
    return plugin, json.loads(file.read_text(encoding="utf-8"))


@pytest.mark.parametrize("host", ("claude-code", "codex"))
@pytest.mark.parametrize("provider", PROVIDERS)
def test_common_metadata_uses_current_version_and_public_contact(generated, host, provider):
    _, output = generated
    plugin, data = manifest(output, host, provider)
    assert data["name"] == f"cross-llm-{provider}"
    assert data.get("version") == "9.8.7", "No fixed or omitted version"
    assert data.get("homepage") == PROJECT
    assert data.get("repository") == PROJECT
    assert data.get("license") == "MIT"
    assert data["author"]["name"]
    assert data["author"].get("url") == "https://github.com/jhesham"
    assert "email" not in data["author"], "Do not add private contact information"
    assert (plugin / "skills" / data["name"] / "SKILL.md").is_file()
    assert not (plugin / (".codex-plugin" if host == "codex" else "plugin.json")).exists()
    for forbidden in ("hooks", "mcpServers", "apps", "agents", "settings", "dependencies"):
        assert forbidden not in data, "Listing changes must not grant runtime capabilities"


def test_codex_directory_fields_and_icons_are_portable(generated):
    _, output = generated
    for provider in PROVIDERS:
        plugin, data = manifest(output, "codex", provider)
        assert "interface" not in data, "Portable format keeps OpenAI fields namespaced"
        extension = data.get("extensions", {}).get("com.openai", {})
        interface = extension.get("interface", {})
        for field in ("displayName", "shortDescription"):
            assert isinstance(interface.get(field), str) and 0 < len(interface[field]) <= 30
            assert "\n" not in interface[field]
        assert 0 < len(interface.get("longDescription", "")) <= 4000
        assert provider.lower() in interface["longDescription"].lower()
        assert 0 < len(interface.get("developerName", "")) <= 80
        assert interface.get("category") == "Developer Tools"
        capabilities = interface.get("capabilities", [])
        assert isinstance(capabilities, list) and len(capabilities) <= 20
        assert all(isinstance(c, str) and 0 < len(c) <= 120 for c in capabilities)
        assert interface.get("websiteURL") == PROJECT
        assert interface.get("supportURL") == PROJECT + "/issues"
        assert interface.get("privacyPolicyURL") == PROJECT + "/blob/main/PRIVACY.md"
        assert "termsOfServiceURL" not in interface, "An MIT license is not a service-terms policy"
        for field in ("logo", "composerIcon"):
            path = interface.get(field, "")
            assert path.startswith("./assets/")
            asset = (plugin / path).resolve()
            assert asset.is_relative_to(plugin.resolve()) and asset.is_file()
            assert asset.stat().st_size <= 5 * 1024 * 1024
            svg = ET.parse(asset).getroot()
            assert svg.tag == "{http://www.w3.org/2000/svg}svg"
            box = [float(x) for x in svg.attrib["viewBox"].split()]
            assert box[2] == box[3] and box[2] >= 48
            for node in svg.iter():
                assert node.tag.split("}")[-1] not in ("script", "foreignObject", "image", "use")
                assert all(not key.lower().startswith("on") for key in node.attrib)
                assert all(not value.startswith(("http:", "https:", "data:")) for value in node.attrib.values())
        assert not (set(extension) - {"interface"}), "Do not add onboarding/review/runtime behavior in this slice"


def test_regeneration_remains_byte_idempotent(generated):
    source, output = generated
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    for host in ("claude-code", "codex"):
        result = subprocess.run([sys.executable, str(source / "generator/build_plugins.py"),
            "--host", host, "--out-root", str(output)], cwd=source, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stderr
    after = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    assert before == after


def test_catalog_jobs_and_provider_paths_are_retained():
    catalog = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    assert len(catalog["plugins"]) == 5
    for entry in catalog["plugins"]:
        provider = entry["name"].removeprefix("cross-llm-")
        assert provider in PROVIDERS and entry["source"] == f"./plugins/{entry['name']}"
        words = entry["description"].lower()
        assert "slice" in words and provider in words
        assert "independent" in words and "not affiliated" in words
