"""v0.5.4 UNIFIEDREF: every reference link inside the unified bundle resolves."""
import re
from pathlib import Path

from tests.evidence._lazy import resolve

PROVIDERS = ("antigravity", "claude", "codex", "cursor", "opencode")
# A bundle link starts at "references/"; a longer path such as an example
# "knowledge/references/x.md" in a target repository is not a bundle link.
LINK = re.compile(r"(?<![A-Za-z0-9_./-])references/[A-Za-z0-9_./-]+\.md")


def _bundle(tmp_path):
    return Path(resolve("generator.build_skill", "build_unified")(out_root=tmp_path, smoke=False))


def test_unified_bundle_has_a_provider_setup_index(tmp_path):
    out = _bundle(tmp_path)
    index = out / "references" / "provider-setup.md"
    assert index.is_file(), "references/provider-setup.md missing from the unified bundle"
    text = index.read_text(encoding="utf-8")
    for p in PROVIDERS:
        assert f"providers/{p}-setup.md" in text, p


def test_every_reference_link_in_the_unified_bundle_resolves(tmp_path):
    out = _bundle(tmp_path)
    missing = set()
    for doc in out.rglob("*.md"):
        for link in LINK.findall(doc.read_text(encoding="utf-8")):
            if not (out / link).is_file():
                missing.add((doc.relative_to(out).as_posix(), link))
    assert not missing, sorted(missing)


MD_LINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")


def test_markdown_hyperlinks_resolve_relative_to_their_page(tmp_path):
    # Codex review P2: a Markdown link resolves from the page that holds it, not the bundle root.
    out = _bundle(tmp_path)
    broken = set()
    for doc in out.rglob("*.md"):
        for target in MD_LINK.findall(doc.read_text(encoding="utf-8")):
            if "://" in target:
                continue
            if not (doc.parent / target).is_file():
                broken.add((doc.relative_to(out).as_posix(), target))
    assert not broken, sorted(broken)
