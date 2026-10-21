"""v0.5 Task 1: the superpowers -> CLD plan-conversion guide ships in every bundle."""
from pathlib import Path

import pytest

from generator.build_skill import build_one

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "skill" / "references" / "superpowers-to-cld.md"
PROVIDERS = ("antigravity", "opencode", "cursor", "codex", "claude")


@pytest.mark.parametrize("host", ["claude-code", "codex"])
@pytest.mark.parametrize("provider", PROVIDERS)
def test_guide_ships_in_every_bundle(tmp_path, provider, host):
    out = build_one(provider, out_root=tmp_path, smoke=False, host=host)
    assert (out / "references" / "superpowers-to-cld.md").is_file()


def test_guide_mapping_table():
    text = GUIDE.read_text(encoding="utf-8") if GUIDE.exists() else ""
    for needle in ("acceptance_test_path", "`files`", "`deps`", "`complexity`", "A task with no test"):
        assert needle in text, needle


@pytest.mark.parametrize("template", ["skill/SKILL.template.md", "skill/hosts/codex/SKILL.template.md"])
def test_skills_link_guide(template):
    assert "superpowers-to-cld.md" in (ROOT / template).read_text(encoding="utf-8")
