"""Lead-owned T12A contract: isolated Codex skill bundles without Claude drift."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from generator.build_skill import build_one


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("antigravity", "cursor", "opencode")


def codex_build(provider, out_root):
    try:
        return build_one(provider, out_root=out_root, host="codex")
    except TypeError as exc:
        assert False, f"Codex host generation is unavailable: {exc}"


def test_explicit_claude_host_preserves_default_bundle_bytes(tmp_path):
    default = build_one("cursor", out_root=tmp_path / "default")
    try:
        explicit = build_one("cursor", out_root=tmp_path / "explicit", host="claude-code")
    except TypeError as exc:
        assert False, f"Explicit Claude host is unavailable: {exc}"
    def snapshot(path):
        return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    assert explicit == tmp_path / "explicit" / "cross-llm-cursor"
    assert snapshot(default) == snapshot(explicit)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_codex_bundle_has_valid_first_line_metadata_and_distinct_root(tmp_path, provider):
    out = codex_build(provider, tmp_path)
    assert out == tmp_path / "codex" / f"cross-llm-{provider}"
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\n")
    _, front, body = skill.split("---", 2)
    meta = yaml.safe_load(front)
    assert meta == {"name": f"cross-llm-{provider}", "description": meta["description"]}
    assert isinstance(meta["description"], str) and 20 <= len(meta["description"]) <= 240
    assert body.strip().startswith("<!-- GENERATED")
    assert "Codex" in body and "--json" in body
    assert "python scripts/run_delivery.py" in body
    assert "skill/scripts/run_delivery.py" not in body
    assert "pip install -e ." not in body
    assert "ANTHROPIC_API_KEY" not in body
    assert "Claude acts as" not in body
    assert len(skill.splitlines()) <= 130
    assert len(skill) <= 9000


@pytest.mark.parametrize("provider", PROVIDERS)
def test_codex_bundle_references_and_isolated_driver_work(tmp_path, provider):
    out = codex_build(provider, tmp_path / "outputs")
    assert (out / "references" / "codex-workflow.md").is_file()
    assert (out / "references" / "provider-setup.md").read_bytes() == (
        ROOT / "engine" / "cld_providers" / provider / "setup.md").read_bytes()
    assert (out / "references" / "provider.md").read_bytes() == (
        ROOT / "engine" / "cld_providers" / provider / "SKILL.fragment.md").read_bytes()
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    assert "references/codex-workflow.md" in skill
    assert "references/provider-setup.md" in skill
    assert "references/provider.md" in skill
    plan = tmp_path / "p.md"
    plan.write_text("## SLICE: A\nbrief: work\nfiles: a.py\nacceptance_test_path: test_a.py\ndeps:\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, str(out / "scripts" / "run_delivery.py"),
        str(plan), "--repo", str(tmp_path), "--dry-run", "--json"], cwd=tmp_path,
        env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        encoding="utf-8", timeout=30)
    response = json.loads(proc.stdout)
    assert proc.returncode == 0 and response["layers"] == [["A"]]
    assert "cld" in str(out / "scripts") and (out / "scripts" / "cld").is_dir()


def test_codex_all_cli_keeps_existing_claude_tree(tmp_path):
    root = tmp_path / "output with spaces"
    legacy = root / "cross-llm-cursor"
    legacy.mkdir(parents=True)
    (legacy / "KEEP").write_text("untouched", encoding="utf-8")
    proc = subprocess.run([sys.executable, str(ROOT / "generator" / "build_skill.py"),
        "--all", "--host", "codex", "--out-root", str(root)], cwd=tmp_path,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert proc.returncode == 0, proc.stderr
    assert (legacy / "KEEP").read_text(encoding="utf-8") == "untouched"
    assert {p.name for p in (root / "codex").iterdir() if p.is_dir()} == {
        f"cross-llm-{provider}" for provider in PROVIDERS}


def test_invalid_host_rejected_before_mutation(tmp_path):
    try:
        build_one("cursor", out_root=tmp_path, host="unsupported")
    except ValueError:
        pass
    except TypeError as exc:
        assert False, f"Host validation is unavailable: {exc}"
    else:
        assert False, "Unsupported host was accepted"
    assert not list(tmp_path.iterdir())
