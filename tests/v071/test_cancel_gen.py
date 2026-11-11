"""v0.7.1 GENCANCEL: skills describe cld_cancel and when polling ends."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ("skill/SKILL.template.md", "skill/SKILL.unified.template.md",
             "skill/hosts/codex/SKILL.template.md", "skill/hosts/codex/SKILL.unified.template.md",
             "skill/hosts/antigravity/SKILL.template.md",
             "skill/hosts/antigravity/SKILL.unified.template.md",
             "skill/hosts/codex/references/codex-workflow.md",
             "skill/hosts/antigravity/references/antigravity-workflow.md")


@pytest.mark.parametrize("rel", TEMPLATES)
def test_templates_describe_cancel(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if "cld_cancel" in line]
    assert lines, f"{rel} does not mention cld_cancel"
    joined = " ".join(lines)
    assert "running" in joined and "cancelling" in joined, f"{rel}: say to poll while running or cancelling"
    assert all(line.isascii() for line in lines), rel
    assert "run_delivery.py" in text, f"{rel}: CLI instructions removed"


@pytest.fixture(scope="module")
def codex_bundles(tmp_path_factory):
    from generator.build_skill import build_one, build_unified
    out = tmp_path_factory.mktemp("dist")
    bundles = [Path(build_one(p, out_root=out, smoke=False, host="codex"))
               for p in ("antigravity", "claude", "codex", "cursor", "opencode")]
    bundles.append(Path(build_unified(out_root=out, smoke=False, host="codex")))
    return bundles


def test_codex_skill_limits_hold(codex_bundles):
    for bundle in codex_bundles:
        text = (bundle / "SKILL.md").read_text(encoding="utf-8")
        assert "cld_cancel" in text, bundle.name
        assert len(text.splitlines()) <= 130 and len(text) <= 9000, (bundle.name, len(text))
        text.encode("cp1252")
