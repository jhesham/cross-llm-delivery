"""Network-backed citation verification for indexed reference modules."""

import re
import subprocess
from pathlib import Path

import pytest

from cld.evidence_mode.citations import verify_citations


pytestmark = pytest.mark.network
ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"


def _freshness_entries():
    entries = {}
    table = (KNOWLEDGE / "freshness.md").read_text(encoding="utf-8")
    for line in table.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 4 or cells[0] == "Repo" or set(cells[0]) <= {"-", ":", " "}:
            continue
        repo, _branch, commit, _verified_on = cells
        if repo and commit and "<" not in repo and "<" not in commit:
            entries[repo] = commit
    return entries


def _gh_runner(argv, cwd):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout or result.stderr


def test_all_reference_modules_have_valid_citations():
    freshness = _freshness_entries()
    references = KNOWLEDGE / "references"
    modules = [path for path in references.glob("*.md") if path.name != "README.md"]
    for module in modules:
        problems = verify_citations(module.read_text(encoding="utf-8"), freshness, runner=_gh_runner)
        assert not problems, f"{module.name}: {'; '.join(problems)}"
