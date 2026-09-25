"""Artifact-level regression for the T17A installed-provider defect."""

from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from shutil import copy2, copytree


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("antigravity", "cursor", "opencode", "codex")


def _source_copy(tmp_path: Path) -> Path:
    source = tmp_path / "source tree with spaces"
    source.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        copy2(ROOT / name, source / name)
    copytree(ROOT / "engine", source / "engine", ignore=lambda _path, names: {
        name for name in names if name == "__pycache__" or name.endswith(".egg-info")
    })
    return source


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    assert result.returncode == 0, result.stdout[-1200:] + result.stderr[-1200:]
    return result


def _resource_paths() -> set[str]:
    return {f"cld_providers/{provider}/{name}"
            for provider in PROVIDERS
            for name in ("SKILL.fragment.md", "setup.md")}


def test_wheel_contains_provider_resources_and_runs_without_checkout_or_optional_deps(tmp_path):
    source = _source_copy(tmp_path)
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    _run([sys.executable, "-m", "pip", "wheel", ".", "--no-deps",
          "--no-build-isolation", "-w", str(wheel_dir)], source)
    wheels = list(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        present = set(archive.namelist())
    missing = _resource_paths() - present
    assert not missing, f"wheel lacks provider resources: {sorted(missing)}"

    site = tmp_path / "isolated site"
    site.mkdir()
    _run([sys.executable, "-m", "pip", "install", "--no-deps", "--target",
          str(site), str(wheels[0])], tmp_path)
    sandbox = tmp_path / "outside checkout"
    sandbox.mkdir()
    probe = (
        "import sys,runpy; "
        f"sys.path.insert(0,{str(site)!r}); "
        "from cld.providers_api import load_providers,all_providers; "
        "load_providers(); "
        "assert {p.name for p in all_providers()} == "
        "{'antigravity','cursor','opencode','codex'}; "
        "import cld.behavioral as behavioral; "
        "assert behavioral.GEval is None; "
        "sys.argv=['cld','--help']; runpy.run_module('cld',run_name='__main__')"
    )
    output = _run([sys.executable, "-I", "-S", "-c", probe], sandbox)
    assert "usage:" in output.stdout.lower()


def test_sdist_contains_provider_resources(tmp_path):
    source = _source_copy(tmp_path)
    output_dir = tmp_path / "sdist"
    output_dir.mkdir()
    _run([sys.executable, "-c", "import setuptools.build_meta as b; "
          f"b.build_sdist({str(output_dir)!r})"], source)
    archives = list(output_dir.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as archive:
        present = {"/".join(member.name.split("/")[1:])
                   for member in archive.getmembers()}
    missing = {"engine/" + resource for resource in _resource_paths()} - present
    assert not missing, f"sdist lacks provider resources: {sorted(missing)}"
