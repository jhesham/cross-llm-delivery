"""Offline checks for the knowledge-base starter contract."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
CORE_SECTIONS = (
    "## 1. System Map",
    "## 2. Contracts",
    "## 3. Dependency Map",
    "## 4. Impact Chains",
    "## 5. Risks",
    "## 6. Key Tables and Paths",
    "## 7. Defects and Gaps",
    "## 8. Owners",
    "## 9. Module Index",
)
STAMP = re.compile(
    r"^> Verified: (?:\d{4}-\d{2}-\d{2}|YYYY-MM-DD) against "
    r"(?:<repo>@<branch>|[^\s@]+@[^\s]+)$",
    re.MULTILINE,
)


def test_core_sections_are_numbered_and_ordered():
    core = (KNOWLEDGE / "core.md").read_text(encoding="utf-8")
    positions = [core.index(section) for section in CORE_SECTIONS]
    assert positions == sorted(positions)


def test_core_has_verification_stamp_and_size_limit():
    path = KNOWLEDGE / "core.md"
    core = path.read_text(encoding="utf-8")
    assert STAMP.search(core)
    assert len(path.read_bytes()) <= 35_000


def test_freshness_file_has_required_table():
    freshness = (KNOWLEDGE / "freshness.md").read_text(encoding="utf-8")
    assert "| Repo | Branch | Verified commit | Verified on |" in freshness


def test_reference_modules_are_stamped_and_indexed():
    references = KNOWLEDGE / "references"
    index = (references / "README.md").read_text(encoding="utf-8")
    modules = [path for path in references.glob("*.md") if path.name != "README.md"]
    for module in modules:
        text = module.read_text(encoding="utf-8")
        assert STAMP.search(text), f"{module.name} is missing its verification stamp"
        assert module.name in index, f"{module.name} is missing from the module index"


def test_queries_are_commented_and_indexed():
    queries = KNOWLEDGE / "references" / "queries"
    index = (queries / "README.md").read_text(encoding="utf-8")
    for query in queries.glob("*.sql"):
        contents = query.read_text(encoding="utf-8")
        first_line = contents.splitlines()[0] if contents.splitlines() else ""
        assert first_line.startswith("--"), f"{query.name} must start with a SQL comment"
        assert query.name in index, f"{query.name} is missing from the query index"
