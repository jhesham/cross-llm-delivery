"""Lead-owned T12B contract for metadata, two-host parity and Codex packaging."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

from generator.build_skill import build_one


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("antigravity", "cursor", "opencode")
HOSTS = ("claude-code", "codex")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_codex_skill_has_verified_agent_metadata(tmp_path, provider):
    bundle = build_one(provider, out_root=tmp_path, host="codex")
    meta_path = bundle / "agents" / "openai.yaml"
    assert meta_path.is_file()
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    assert isinstance(meta, dict)
    assert set(meta) == {"interface", "policy"}
    interface = meta["interface"]
    assert set(interface) == {"display_name", "short_description", "default_prompt"}
    assert provider.lower() in interface["display_name"].lower()
    assert "Codex" in interface["short_description"]
    assert provider.lower() in interface["default_prompt"].lower()
    assert meta["policy"] == {"products": ["CODEX"], "allow_implicit_invocation": False}
    assert "{{" not in meta_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("provider", PROVIDERS)
def test_host_bundle_shares_core_reference_and_uses_its_vendored_driver(tmp_path, host, provider):
    bundle = build_one(provider, out_root=tmp_path / "output with spaces", host=host)
    skill = (bundle / "SKILL.md").read_text(encoding="utf-8")
    core = bundle / "references" / "delivery-core.md"
    assert core.is_file()
    assert core.read_bytes() == (ROOT / "skill" / "references" / "delivery-core.md").read_bytes()
    assert "references/delivery-core.md" in skill
    assert "python scripts/run_delivery.py" in skill
    assert "python skill/scripts/run_delivery.py" not in skill
    assert "pip install -e ." not in skill
    assert "{{" not in skill

    plan = tmp_path / f"{host}-{provider}.md"
    plan.write_text("## SLICE: A\nbrief: work\nfiles: a.py\nacceptance_test_path: test_a.py\ndeps:\n",
                    encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, str(bundle / "scripts" / "run_delivery.py"),
                           str(plan), "--repo", str(tmp_path), "--dry-run", "--json"],
                          cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["layers"] == [["A"]]


def _snapshot(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def _build_codex_plugins(tmp_path):
    isolated = tmp_path / "isolated generator repo"
    (isolated / "generator").mkdir(parents=True)
    shutil.copy2(ROOT / "generator" / "build_plugins.py", isolated / "generator" / "build_plugins.py")
    shutil.copy2(ROOT / "VERSION", isolated / "VERSION")
    dist = tmp_path / "source bundles"
    for provider in PROVIDERS:
        build_one(provider, out_root=dist, host="codex")
    output = tmp_path / "plugin output"
    legacy = output / "cross-llm-cursor"
    legacy.mkdir(parents=True)
    (legacy / "KEEP").write_text("untouched", encoding="utf-8")
    cmd = [sys.executable, str(isolated / "generator" / "build_plugins.py"), "--host", "codex",
           "--dist-root", str(dist), "--out-root", str(output)]
    proc = subprocess.run(cmd, cwd=tmp_path, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert (legacy / "KEEP").read_text(encoding="utf-8") == "untouched"
    return output, cmd


def test_codex_plugin_layout_metadata_and_idempotence(tmp_path):
    output, cmd = _build_codex_plugins(tmp_path)
    plugins = output / "codex"
    assert plugins.is_dir()
    assert {p.name for p in plugins.iterdir() if p.is_dir()} == {
        f"cross-llm-{provider}" for provider in PROVIDERS}
    for provider in PROVIDERS:
        plugin = plugins / f"cross-llm-{provider}"
        manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
        assert manifest["name"] == f"cross-llm-{provider}"
        assert manifest["version"] == (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        assert manifest["description"] and manifest["author"]["name"]
        assert not (plugin / ".claude-plugin").exists()
        skill = plugin / "skills" / f"cross-llm-{provider}"
        assert (skill / "SKILL.md").read_text(encoding="utf-8").startswith("---\n")
        assert (skill / "agents" / "openai.yaml").is_file()
        assert (skill / "scripts" / "run_delivery.py").is_file()
    before = _snapshot(plugins)
    again = subprocess.run(cmd, cwd=tmp_path, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert again.returncode == 0, again.stderr + again.stdout
    assert _snapshot(plugins) == before


def test_ci_smokes_codex_generation_and_plugin_packaging():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python generator/build_skill.py --all --host codex" in workflow
    assert "python generator/build_plugins.py --host codex" in workflow
