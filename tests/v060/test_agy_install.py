"""v0.6.0 AGYINSTALL: safe installer for Antigravity-host skill bundles."""
import json
from pathlib import Path

import pytest

from tests.evidence._lazy import resolve

MARKER = "cross-llm-delivery/install_antigravity.py"


def _bundle(root: Path, name: str, *, antigravity: bool = True) -> Path:
    b = root / name
    (b / "scripts" / "cld").mkdir(parents=True)
    (b / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n# t\n", encoding="utf-8")
    (b / "scripts" / "run_delivery.py").write_text("print('ok')\n", encoding="utf-8")
    (b / "scripts" / "cld" / "__init__.py").write_text("", encoding="utf-8")
    (b / "references").mkdir()
    workflow = "antigravity-workflow.md" if antigravity else "codex-workflow.md"
    (b / "references" / workflow).write_text("# workflow\n", encoding="utf-8")
    return b


def _run(capsys, *argv):
    main = resolve("generator.install_antigravity", "main")
    rc = main(list(argv))
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "installer printed nothing"
    return rc, json.loads(out[-1])


@pytest.fixture
def src(tmp_path):
    root = tmp_path / "bundles with spaces"
    root.mkdir()
    return root


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "target repo"
    path.mkdir()
    return path


def test_workspace_install_goes_to_dot_agents_skills(src, repo, capsys):
    bundle = _bundle(src, "cross-llm-opencode-agy")
    rc, payload = _run(capsys, "--install", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    target = repo / ".agents" / "skills" / "cross-llm-opencode-agy"
    assert rc == 0, payload
    assert payload["outcome"] != "error" and payload["target"] == str(target)
    assert payload["scope"] == "workspace"
    assert (target / "SKILL.md").is_file()
    manifest = json.loads((target / ".cld-install.json").read_text(encoding="utf-8"))
    assert manifest.get("installer") == MARKER


def test_user_install_goes_to_gemini_config_skills(tmp_path, src, capsys):
    bundle = _bundle(src, "cross-llm-delivery-agy")
    home = tmp_path / "home"
    home.mkdir()
    rc, payload = _run(capsys, "--install", "--scope", "user", "--scope-root", str(home),
                       "--bundle", str(bundle))
    target = home / ".gemini" / "config" / "skills" / "cross-llm-delivery-agy"
    assert rc == 0, payload
    assert payload["target"] == str(target) and payload["scope"] == "user"
    assert (target / "scripts" / "run_delivery.py").is_file()


def test_preview_writes_nothing(src, repo, capsys):
    bundle = _bundle(src, "cross-llm-codex-agy")
    rc, payload = _run(capsys, "--preview", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc == 0, payload
    assert payload["action"] == "preview" and payload["scope"] == "workspace"
    assert not (repo / ".agents").exists()


def test_update_after_runtime_cache_and_refusal_after_local_edit(src, repo, capsys):
    bundle = _bundle(src, "cross-llm-cursor-agy")
    common = ("--scope", "workspace", "--scope-root", str(repo), "--bundle", str(bundle))
    assert _run(capsys, "--install", *common)[0] == 0
    target = repo / ".agents" / "skills" / "cross-llm-cursor-agy"
    cache = target / "scripts" / "cld" / "__pycache__"
    cache.mkdir()
    (cache / "x.cpython-311.pyc").write_bytes(b"\0")
    rc, payload = _run(capsys, "--install", *common)
    assert rc == 0, payload
    (target / "SKILL.md").write_text("edited\n", encoding="utf-8")
    rc, payload = _run(capsys, "--install", *common)
    assert rc != 0 and payload["outcome"] == "error"
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "edited\n"


def test_unowned_folder_is_a_collision(src, repo, capsys):
    bundle = _bundle(src, "cross-llm-claude-agy")
    existing = repo / ".agents" / "skills" / "cross-llm-claude-agy"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("mine\n", encoding="utf-8")
    rc, payload = _run(capsys, "--install", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc != 0 and payload.get("collision") == "unowned", payload
    assert (existing / "SKILL.md").read_text(encoding="utf-8") == "mine\n"


@pytest.mark.parametrize("name", ("cross-llm-opencode", "cross-llm-delivery", "something-else"))
def test_only_antigravity_skill_names_are_installed(src, repo, capsys, name):
    bundle = _bundle(src, name)
    rc, payload = _run(capsys, "--preview", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc != 0 and payload["outcome"] == "error", payload


def test_non_antigravity_bundle_is_refused(src, repo, capsys):
    bundle = _bundle(src, "cross-llm-codex-agy", antigravity=False)
    rc, payload = _run(capsys, "--preview", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc != 0 and payload["outcome"] == "error"
    assert "antigravity-workflow.md" in payload["error"]


def test_codex_and_antigravity_copies_sit_side_by_side(src, repo, capsys):
    codex_main = resolve("generator.install_codex", "main")
    codex_bundle = _bundle(src / "codex", "cross-llm-opencode", antigravity=False)
    assert codex_main(["--install", "--scope-root", str(repo), "--bundle", str(codex_bundle)]) == 0
    capsys.readouterr()
    codex_target = repo / ".agents" / "skills" / "cross-llm-opencode"
    codex_manifest = (codex_target / ".cld-install.json").read_bytes()

    agy_bundle = _bundle(src / "agy", "cross-llm-opencode-agy")
    rc, payload = _run(capsys, "--install", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(agy_bundle))
    assert rc == 0, payload
    # Antigravity also sees the Codex skill; the installer says which one to ask for.
    warning = payload.get("sibling_warning", "")
    assert str(codex_target) in warning and "cross-llm-opencode-agy" in warning, payload
    assert (repo / ".agents/skills/cross-llm-opencode-agy/SKILL.md").is_file()

    rc, payload = _run(capsys, "--uninstall", "--scope", "workspace", "--scope-root", str(repo),
                       "--name", "cross-llm-opencode-agy")
    assert rc == 0, payload
    assert (codex_target / ".cld-install.json").read_bytes() == codex_manifest


def test_no_sibling_warning_without_a_codex_copy(src, repo, capsys):
    bundle = _bundle(src, "cross-llm-opencode-agy")
    rc, payload = _run(capsys, "--preview", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc == 0 and "sibling_warning" not in payload and "shadow_warning" not in payload, payload


def test_unified_sibling_is_the_codex_unified_skill(src, repo, capsys):
    (repo / ".agents" / "skills" / "cross-llm-delivery").mkdir(parents=True)
    bundle = _bundle(src, "cross-llm-delivery-agy")
    rc, payload = _run(capsys, "--preview", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc == 0 and str(repo / ".agents" / "skills" / "cross-llm-delivery") in payload.get(
        "sibling_warning", ""), payload


def test_codex_installer_refuses_antigravity_skill_names(src, repo):
    codex_main = resolve("generator.install_codex", "main")
    bundle = _bundle(src, "cross-llm-opencode-agy")
    assert codex_main(["--install", "--scope-root", str(repo), "--bundle", str(bundle)]) != 0
    assert not (repo / ".agents/skills/cross-llm-opencode-agy").exists()


def test_deprecated_dot_agent_copy_is_reported_as_a_shadow(src, repo, capsys):
    bundle = _bundle(src, "cross-llm-opencode-agy")
    old = repo / ".agent" / "skills" / "cross-llm-opencode-agy"
    old.mkdir(parents=True)
    rc, payload = _run(capsys, "--preview", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc == 0, payload
    assert str(old) in payload.get("shadow_warning", ""), payload
    rc, payload = _run(capsys, "--install", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc == 0 and str(old) in payload.get("shadow_warning", ""), payload
    assert old.is_dir(), "the old copy is reported, never removed"


def test_uninstall_removes_only_an_owned_clean_install(tmp_path, src, capsys):
    bundle = _bundle(src, "cross-llm-antigravity-agy")
    home = tmp_path / "home"
    home.mkdir()
    assert _run(capsys, "--install", "--scope", "user", "--scope-root", str(home),
                "--bundle", str(bundle))[0] == 0
    target = home / ".gemini" / "config" / "skills" / "cross-llm-antigravity-agy"
    rc, payload = _run(capsys, "--uninstall", "--scope", "user", "--scope-root", str(home),
                       "--name", "cross-llm-antigravity-agy")
    assert rc == 0, payload
    assert not target.exists()


def test_scope_is_required(tmp_path, src):
    main = resolve("generator.install_antigravity", "main")
    bundle = _bundle(src, "cross-llm-opencode-agy")
    with pytest.raises(SystemExit):
        main(["--preview", "--scope-root", str(tmp_path), "--bundle", str(bundle)])


def test_codex_installer_accepts_the_codex_unified_bundle(src, repo):
    codex_main = resolve("generator.install_codex", "main")
    bundle = _bundle(src, "cross-llm-delivery", antigravity=False)
    assert codex_main(["--install", "--scope-root", str(repo), "--bundle", str(bundle)]) == 0
    assert (repo / ".agents/skills/cross-llm-delivery/SKILL.md").is_file()
