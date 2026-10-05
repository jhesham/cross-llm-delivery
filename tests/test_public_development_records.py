"""Keep published development records useful without exposing local identities."""

import hashlib
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RECORDS = (
    ("docs/plans/claude-executor/PLAN.md", "# Claude Code Executor Implementation Plan"),
    ("docs/plans/codex-support/DEFECTS.md", "# Review defect register"),
    ("docs/plans/codex-support/HANDOFF.md", "# Current handoff"),
    ("docs/plans/codex-support/T05-MIGRATION.md", "# T05"),
    ("docs/plans/codex-support/T06-INTEGRATION.md", "# T06"),
    ("docs/plans/codex-support/T07-CONTRACT.md", "# T07"),
    ("docs/plans/codex-support/T18-PREVIEW.md", "# T18"),
    ("docs/plans/codex-support/T20A-EVIDENCE.md", "# T20A"),
    ("docs/plans/codex-support/T20B-CANDIDATE.md", "# T20B"),
    ("docs/plans/v0.3.1-fixes/PLAN.md", "# v0.3.1 Review Fixes Implementation Plan"),
    ("docs/plans/v0.4.0-review-fixes/FULL-REVIEW-2026-10-03.md", "# Full build review"),
    ("docs/plans/v0.4.0-review-fixes/PLAN.md", "# v0.4.0 Review Fixes"),
)
WINDOWS_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Existing unrelated project/machine labels, stored as fingerprints so the
# regression guard does not republish the identities it protects.
PRIVATE_LABEL_HASHES = frozenset({
    "f7a30510f97bde4b751295d5836fe8f00fb1d791094338dbc08a6597d1cff9fe",
    "70db5bd0f87d653d5995e1e2a081b589e2cd1aa01c1ee63a1c013dcabf3f7e3f",
    "09e002bb523552d1252481feef3381b29ff3b01be8a0138273a8b01edc591172",
})


@pytest.mark.parametrize("relative,title", RECORDS)
def test_development_record_is_retained_and_deidentified(relative, title):
    text = (ROOT / relative).read_text(encoding="utf-8")
    assert text.startswith(title), "Retain the development record and its title"
    assert len(text.splitlines()) >= 40, "Do not replace a record with a stub"
    # Report only locations/categories; assertion diagnostics must not echo PII.
    problems = []
    for number, line in enumerate(text.splitlines(), 1):
        if WINDOWS_PATH.search(line):
            problems.append((number, "absolute Windows path"))
        if EMAIL.search(line):
            problems.append((number, "email address"))
        tokens = re.findall(r"[A-Za-z0-9_.-]+", line.lower())
        if any(hashlib.sha256(token.encode()).hexdigest() in PRIVATE_LABEL_HASHES
               for token in tokens):
            problems.append((number, "private project or machine label"))
    assert not problems, f"Use meaningful placeholders in {relative}: {problems}"


def test_development_records_have_current_guidance_and_historical_context():
    index = ROOT / "docs" / "plans" / "README.md"
    assert index.is_file(), "Explain the purpose and limits of development records"
    text = index.read_text(encoding="utf-8")
    assert re.search(r"development records|historical records", text, re.I)
    assert re.search(r"historical|stale|outdated", text, re.I)
    assert re.search(r"commit|SHA|history", text, re.I)
    for target in ("../../README.md", "../../INSTALL.md", "../../KNOWN-ISSUES.md"):
        assert target in text, f"Link current product guidance: {target}"
        assert (index.parent / target).resolve().is_file()
    assert not WINDOWS_PATH.search(text)
    assert not EMAIL.search(text)
