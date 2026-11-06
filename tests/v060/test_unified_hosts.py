"""v0.6.0 UNIFIEDHOSTS: the all-executors bundle builds for the Codex and Antigravity hosts."""
import inspect
import json
import re
from pathlib import Path

import pytest

from tests.evidence._lazy import resolve
from tests.v060._golden import assert_unchanged

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ("antigravity", "claude", "codex", "cursor", "opencode")
SHARED_REFS = ("delivery-core.md", "authoring-plans.md", "architecture.md",
               "observability.md", "superpowers-to-cld.md")
MD_LINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")
HOST_NAMES = {"codex": "Codex", "antigravity": "Antigravity"}
# Codex and Antigravity both read <repo>/.agents/skills, so the Antigravity skill has its own name.
SKILL_NAMES = {"claude-code": "cross-llm-delivery", "codex": "cross-llm-delivery",
               "antigravity": "cross-llm-delivery-agy"}


def _unified(tmp_path, host, smoke=False):
    build_unified = resolve("generator.build_skill", "build_unified")
    assert "host" in inspect.signature(build_unified).parameters, "build_unified(host=...) missing"
    return Path(build_unified(out_root=tmp_path, smoke=smoke, host=host))


def _banner_free(text):
    return re.sub(r"<!-- GENERATED from cross-llm-delivery[^\n]*-->", "{{BANNER}}", text)


@pytest.mark.parametrize("host", ("codex", "antigravity"))
def test_unified_bundle_lands_under_the_host_root(tmp_path, host):
    out = _unified(tmp_path, host)
    assert out == tmp_path / host / SKILL_NAMES[host]
    assert not (tmp_path / "cross-llm-delivery").exists(), "must not write the Claude bundle"


@pytest.mark.parametrize("host", ("codex", "antigravity"))
def test_skill_is_the_host_unified_template(tmp_path, host):
    out = _unified(tmp_path, host)
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    template = (ROOT / "skill/hosts" / host / "SKILL.unified.template.md").read_text(encoding="utf-8")
    assert skill.startswith(f"---\nname: {SKILL_NAMES[host]}\n")
    assert "{{" not in skill
    assert _banner_free(skill) == template


@pytest.mark.parametrize("host", ("codex", "antigravity"))
def test_references_hold_every_executor_and_the_host_workflow(tmp_path, host):
    out = _unified(tmp_path, host)
    refs = out / "references"
    workflow = f"{host}-workflow.md"
    assert (refs / workflow).read_bytes() == (ROOT / "skill/hosts" / host / "references" / workflow).read_bytes()
    for name in SHARED_REFS:
        assert (refs / name).read_bytes() == (ROOT / "skill/references" / name).read_bytes(), name
    other = "codex-workflow.md" if host == "antigravity" else "antigravity-workflow.md"
    assert not (refs / other).exists()
    for p in PROVIDERS:
        assert (refs / "providers" / f"{p}-setup.md").read_bytes() == (
            ROOT / "engine/cld_providers" / p / "setup.md").read_bytes(), p
        assert (refs / "providers" / f"{p}.md").read_bytes() == (
            ROOT / "engine/cld_providers" / p / "SKILL.fragment.md").read_bytes(), p
    setup_index = (refs / "provider-setup.md").read_text(encoding="utf-8")
    notes_index = (refs / "provider.md").read_text(encoding="utf-8")
    for p in PROVIDERS:
        assert f"](providers/{p}-setup.md)" in setup_index, p
        assert f"](providers/{p}.md)" in notes_index, p


@pytest.mark.parametrize("host", ("codex", "antigravity"))
def test_every_executor_is_vendored(tmp_path, host):
    out = _unified(tmp_path, host)
    vendored = {p.name for p in (out / "scripts" / "cld_providers").iterdir()
                if p.is_dir() and p.name != "__pycache__"}
    assert vendored == set(PROVIDERS)
    assert (out / "scripts" / "run_delivery.py").is_file()


@pytest.mark.parametrize("host", ("codex", "antigravity"))
def test_scaffold_and_readme_name_the_host_lead(tmp_path, host):
    out = _unified(tmp_path, host)
    for name in ("README.md", "PRIVACY.md", "SECURITY.md", "LICENSE", ".gitignore"):
        assert (out / name).is_file(), name
    assert (out / "examples").is_dir()
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert readme.startswith(f"# {SKILL_NAMES[host]} ({HOST_NAMES[host]} lead)"), readme[:80]
    assert f"--host {host}" in readme
    assert "{{" not in readme


@pytest.mark.parametrize("host", ("codex", "antigravity"))
def test_unified_bundle_carries_its_agent_metadata(tmp_path, host):
    # Codex reads it; for the Antigravity skill it stops Codex invoking it on its own.
    out = _unified(tmp_path, host)
    meta = (out / "agents" / "openai.yaml").read_bytes()
    assert meta == (ROOT / "skill/hosts" / host / "agents/openai.unified.yaml").read_bytes()
    assert b"allow_implicit_invocation: false" in meta


@pytest.mark.parametrize("host", ("codex", "antigravity"))
def test_every_markdown_link_resolves_from_its_page(tmp_path, host):
    out = _unified(tmp_path, host)
    broken = set()
    for doc in out.rglob("*.md"):
        for target in MD_LINK.findall(doc.read_text(encoding="utf-8")):
            if "://" not in target and not (doc.parent / target).is_file():
                broken.add((doc.relative_to(out).as_posix(), target))
    assert not broken, sorted(broken)


@pytest.mark.parametrize("host", ("codex", "antigravity"))
def test_smoke_check_loads_every_provider(tmp_path, host):
    out = _unified(tmp_path, host, smoke=True)
    assert (out / "SKILL.md").is_file()


def test_claude_unified_bundle_is_unchanged_by_default(tmp_path):
    build_unified = resolve("generator.build_skill", "build_unified")
    out = Path(build_unified(out_root=tmp_path, smoke=False))
    assert out == tmp_path / "cross-llm-delivery"
    # Every file name and byte, apart from the banner, as v0.5.4 generated it.
    assert_unchanged("claude-code/unified", out)


@pytest.mark.parametrize("host", ("claude-code", "codex"))
def test_main_all_leaves_the_claude_and_codex_bundles_unchanged(tmp_path, host):
    main = resolve("generator.build_skill", "main")
    assert main(["--all", "--host", host, "--out-root", str(tmp_path), "--no-smoke"]) == 0
    root = tmp_path if host == "claude-code" else tmp_path / host
    for provider in PROVIDERS:
        assert_unchanged(f"{host}/{provider}", root / f"cross-llm-{provider}")
    if host == "claude-code":
        assert_unchanged("claude-code/unified", root / "cross-llm-delivery")


@pytest.mark.parametrize("host", ("claude-code", "codex", "antigravity"))
def test_main_all_builds_the_unified_bundle_for_each_host(tmp_path, host):
    main = resolve("generator.build_skill", "main")
    assert "antigravity" in resolve("generator.build_skill", "HOSTS"), "antigravity host not supported"
    assert main(["--all", "--host", host, "--out-root", str(tmp_path), "--no-smoke"]) == 0
    root = tmp_path if host == "claude-code" else tmp_path / host
    assert (root / SKILL_NAMES[host] / "SKILL.md").is_file()


def test_single_provider_build_does_not_build_the_unified_bundle(tmp_path):
    main = resolve("generator.build_skill", "main")
    assert main(["codex", "--host", "codex", "--out-root", str(tmp_path), "--no-smoke"]) == 0
    assert not (tmp_path / "codex" / "cross-llm-delivery").exists()


def test_codex_plugin_packaging_keeps_exactly_the_five_executor_plugins(tmp_path):
    main = resolve("generator.build_skill", "main")
    assert main(["--all", "--host", "codex", "--out-root", str(tmp_path / "dist"), "--no-smoke"]) == 0
    assert (tmp_path / "dist" / "codex" / "cross-llm-delivery").is_dir()
    packager = resolve("generator.build_plugins", "main")
    assert packager(["--host", "codex", "--dist-root", str(tmp_path / "dist"),
                     "--out-root", str(tmp_path / "out")]) == 0
    catalog = json.loads((tmp_path / "out/.agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    assert {p["name"] for p in catalog["plugins"]} == {f"cross-llm-{p}" for p in PROVIDERS}
    assert not (tmp_path / "out" / "codex" / "cross-llm-delivery").exists()
