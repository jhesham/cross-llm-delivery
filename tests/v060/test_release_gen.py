"""v0.6.0 RELEASEGEN: release generation and CI also build the Antigravity host."""
import sys
from pathlib import Path

from tests.evidence._lazy import resolve

ROOT = Path(__file__).resolve().parents[2]
AGY_BUILD = ["generator/build_skill.py", "--all", "--host", "antigravity"]


def test_release_generation_builds_the_antigravity_host(monkeypatch, tmp_path):
    release = resolve("generator.release")
    generate = resolve("generator.release", "_generate")
    calls = []

    def runner(argv, cwd):
        calls.append(list(argv))
        return 0, ""

    monkeypatch.setattr(release, "_validate_manifests", lambda root: None)
    generate(tmp_path, runner)
    builds = [argv[1:] for argv in calls if argv and argv[0] == sys.executable]
    assert AGY_BUILD in builds, builds
    # Existing generation is unchanged and still runs first.
    assert builds[:4] == [
        ["generator/build_skill.py", "--all"],
        ["generator/build_skill.py", "--all", "--host", "codex"],
        ["generator/build_plugins.py"],
        ["generator/build_plugins.py", "--host", "codex", "--out-root", "dist/release-plugins"],
    ], builds


def test_ci_smoke_builds_the_antigravity_host():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "python generator/build_skill.py --all --host antigravity" in ci
