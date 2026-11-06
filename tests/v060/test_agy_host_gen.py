"""v0.6.0 AGYHOSTGEN: the generator builds Antigravity-host skill bundles."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.evidence._lazy import resolve
from tests.v060._golden import assert_unchanged

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ("antigravity", "claude", "codex", "cursor", "opencode")
SHARED_REFS = ("delivery-core.md", "authoring-plans.md", "architecture.md",
               "observability.md", "superpowers-to-cld.md")
MD_LINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")


def _hosts():
    return resolve("generator.build_skill", "HOSTS")


def _build(provider, tmp_path, host="antigravity", smoke=False):
    assert "antigravity" in _hosts(), "antigravity host not supported"
    build_one = resolve("generator.build_skill", "build_one")
    return Path(build_one(provider, out_root=tmp_path, smoke=smoke, host=host))


@pytest.mark.parametrize("provider", PROVIDERS)
def test_bundle_lands_under_the_antigravity_root(tmp_path, provider):
    out = _build(provider, tmp_path)
    assert out == tmp_path / "antigravity" / f"cross-llm-{provider}-agy"
    assert not (tmp_path / f"cross-llm-{provider}").exists(), "must not write a Claude bundle"
    assert not (tmp_path / "codex").exists(), "must not write a Codex bundle"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_skill_is_yaml_first_and_rendered_from_the_antigravity_template(tmp_path, provider):
    out = _build(provider, tmp_path)
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith(f"---\nname: cross-llm-{provider}-agy\n"), skill[:80]
    assert "\n---\n<!-- GENERATED from cross-llm-delivery" in skill
    assert "{{" not in skill and "}}" not in skill
    assert "**Antigravity is the lead.**" in skill
    assert "--host antigravity" in skill
    assert "Codex is the lead" not in skill


@pytest.mark.parametrize("provider", PROVIDERS)
def test_references_and_codex_guard_metadata(tmp_path, provider):
    out = _build(provider, tmp_path)
    refs = out / "references"
    expected = {"antigravity-workflow.md", "provider-setup.md", "provider.md", *SHARED_REFS}
    assert {p.name for p in refs.iterdir()} == expected
    source = ROOT / "skill/hosts/antigravity/references/antigravity-workflow.md"
    assert (refs / "antigravity-workflow.md").read_bytes() == source.read_bytes()
    assert (refs / "provider-setup.md").read_bytes() == (
        ROOT / "engine/cld_providers" / provider / "setup.md").read_bytes()
    assert (refs / "provider.md").read_bytes() == (
        ROOT / "engine/cld_providers" / provider / "SKILL.fragment.md").read_bytes()
    # Codex also reads .agents/skills: this metadata stops it invoking the Antigravity skill.
    meta = (out / "agents" / "openai.yaml").read_text(encoding="utf-8")
    template = (ROOT / "skill/hosts/antigravity/agents/openai.yaml.template").read_text(encoding="utf-8")
    assert meta == template.replace("{{PROVIDER_NAME}}", provider)
    assert "allow_implicit_invocation: false" in meta


@pytest.mark.parametrize("provider", PROVIDERS)
def test_scaffold_and_readme_name_the_antigravity_lead(tmp_path, provider):
    out = _build(provider, tmp_path)
    for name in ("README.md", "PRIVACY.md", "SECURITY.md", "LICENSE", ".gitignore"):
        assert (out / name).is_file(), name
    assert (out / "examples").is_dir()
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert readme.startswith(f"# cross-llm-{provider}-agy (Antigravity lead)"), readme[:80]
    assert "--host antigravity" in readme
    assert "{{" not in readme


@pytest.mark.parametrize("provider", PROVIDERS)
def test_only_the_selected_provider_is_vendored(tmp_path, provider):
    out = _build(provider, tmp_path)
    vendored = {p.name for p in (out / "scripts" / "cld_providers").iterdir()
                if p.is_dir() and p.name != "__pycache__"}
    assert vendored == {provider}
    assert (out / "scripts" / "run_delivery.py").is_file()
    assert (out / "scripts" / "list_models.py").is_file()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_markdown_link_resolves_from_its_page(tmp_path, provider):
    out = _build(provider, tmp_path)
    broken = set()
    for doc in out.rglob("*.md"):
        for target in MD_LINK.findall(doc.read_text(encoding="utf-8")):
            if "://" not in target and not (doc.parent / target).is_file():
                broken.add((doc.relative_to(out).as_posix(), target))
    assert not broken, sorted(broken)


def test_standalone_smoke_check_passes(tmp_path):
    out = _build("opencode", tmp_path, smoke=True)
    assert (out / "SKILL.md").is_file()


def test_installed_driver_previews_offline_with_the_antigravity_label(tmp_path):
    out = _build("opencode", tmp_path / "bundles with spaces")
    repo = tmp_path / "target repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"],
                 ["config", "user.name", "T"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    (repo / "test_a.py").write_text("def test_a():\n    assert False\n", encoding="utf-8")
    plan = repo / "plan.md"
    plan.write_text("## SLICE: A\nbrief: create a\nfiles: a.py\nacceptance_test_path: test_a.py\ndeps:\n",
                    encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True, capture_output=True)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(out / "scripts" / "run_delivery.py"), str(plan), "--repo", str(repo),
         "--dry-run", "--json", "--host", "antigravity"],
        cwd=tmp_path, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["gate"] == "pending", result.stdout


def test_main_builds_all_antigravity_bundles(tmp_path):
    main = resolve("generator.build_skill", "main")
    assert "antigravity" in _hosts(), "antigravity host not supported"
    assert main(["--all", "--host", "antigravity", "--out-root", str(tmp_path), "--no-smoke"]) == 0
    for provider in PROVIDERS:
        assert (tmp_path / "antigravity" / f"cross-llm-{provider}-agy" / "SKILL.md").is_file(), provider


def test_unknown_host_is_still_refused_before_output(tmp_path):
    build_one = resolve("generator.build_skill", "build_one")
    with pytest.raises(ValueError):
        build_one("codex", out_root=tmp_path, smoke=False, host="nope")
    assert not any(tmp_path.iterdir())


def test_claude_and_codex_bundles_carry_no_antigravity_files(tmp_path):
    assert "antigravity" in _hosts(), "antigravity host not supported"
    claude = _build("codex", tmp_path, host="claude-code")
    codex = _build("codex", tmp_path, host="codex")
    for out in (claude, codex):
        assert not (out / "references" / "antigravity-workflow.md").exists()
        assert "**Antigravity is the lead.**" not in (out / "SKILL.md").read_text(encoding="utf-8")
    # Codex bundles stay exactly as they are: same names, same metadata.
    assert claude.name == codex.name == "cross-llm-codex"
    assert (codex / "agents" / "openai.yaml").read_text(encoding="utf-8") == (
        ROOT / "skill/hosts/codex/agents/openai.yaml.template").read_text(
        encoding="utf-8").replace("{{PROVIDER_NAME}}", "codex")


@pytest.mark.parametrize("host", ("claude-code", "codex"))
@pytest.mark.parametrize("provider", PROVIDERS)
def test_claude_and_codex_bundles_match_the_v054_snapshot(tmp_path, host, provider):
    # Every file name and byte, apart from the banner, as v0.5.4 generated it.
    build_one = resolve("generator.build_skill", "build_one")
    assert_unchanged(f"{host}/{provider}", build_one(provider, out_root=tmp_path, smoke=False, host=host))
