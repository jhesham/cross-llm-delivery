"""v0.6.0 review fix: installers refuse Windows junctions in the bundle and the destination."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.evidence._lazy import resolve
from tests.v060.test_agy_install import _bundle, _run, repo, src  # noqa: F401 (fixtures)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-only")


@pytest.fixture
def junction():
    made = []

    def make(link: Path, target: Path) -> Path:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                       check=True, capture_output=True)
        made.append(link)
        return link
    yield make
    for link in made:
        os.rmdir(link)  # removes the junction only, never its target


def _codex(capsys, *argv):
    import json
    rc = resolve("generator.install_codex", "main")(list(argv))
    return rc, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_a_junction_inside_the_bundle_is_refused(src, repo, tmp_path, capsys, junction):
    bundle = _bundle(src, "cross-llm-codex-agy")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("not part of the bundle", encoding="utf-8")
    junction(bundle / "references" / "linked", outside)
    rc, payload = _run(capsys, "--install", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc == 1 and payload["outcome"] == "error", payload
    assert not (repo / ".agents" / "skills" / "cross-llm-codex-agy").exists()


def test_a_junctioned_agents_folder_is_refused(src, repo, capsys, junction):
    bundle = _bundle(src, "cross-llm-codex-agy")
    (repo / ".agent").mkdir()
    junction(repo / ".agents", repo / ".agent")
    rc, payload = _run(capsys, "--install", "--scope", "workspace", "--scope-root", str(repo),
                       "--bundle", str(bundle))
    assert rc == 1 and payload["outcome"] == "error", payload
    assert list((repo / ".agent").iterdir()) == []


def test_uninstall_through_a_junction_is_refused(src, repo, tmp_path, capsys, junction):
    bundle = _bundle(src, "cross-llm-codex-agy")
    elsewhere = tmp_path / "elsewhere"
    rc, _ = _run(capsys, "--install", "--scope", "workspace", "--scope-root", str(elsewhere),
                 "--bundle", str(bundle))
    assert rc == 0
    junction(repo / ".agents", elsewhere / ".agents")
    rc, payload = _run(capsys, "--uninstall", "--scope", "workspace", "--scope-root", str(repo),
                       "--name", "cross-llm-codex-agy")
    assert rc == 1 and payload["outcome"] == "error", payload
    assert (elsewhere / ".agents" / "skills" / "cross-llm-codex-agy" / "SKILL.md").is_file()


def test_the_codex_installer_refuses_a_junction_inside_the_bundle(src, repo, tmp_path, capsys,
                                                                  junction):
    bundle = _bundle(src, "cross-llm-codex", antigravity=False)
    outside = tmp_path / "outside"
    outside.mkdir()
    junction(bundle / "references" / "linked", outside)
    rc, payload = _codex(capsys, "--install", "--scope-root", str(repo), "--bundle", str(bundle))
    assert rc == 1 and payload["outcome"] == "error", payload
    assert not (repo / ".agents" / "skills" / "cross-llm-codex").exists()
