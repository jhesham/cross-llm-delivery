"""v0.5 third review (SQLCLASS3): escaped identifier and string spellings."""
import pytest

from tests.evidence._lazy import resolve

@pytest.mark.parametrize("sql", [
    "SELECT U&\"n\\0065xtval\"('s')",
    "SELECT U&\"!006Extval\" UESCAPE '!' ('s')",
    "SELECT E'\\'' || nextval('s') || E'\\''",
    "SELECT 'a\\', nextval('s')",
])
def test_escaped_spellings_of_denylisted_calls_are_writes(sql):
    assert resolve("cld.evidence_mode.sqlclass", "classify_sql")(sql) == "write"


@pytest.mark.parametrize("sql", [
    "SELECT E'it\\'s nextval(1)' AS label",
    "SELECT 'it''s nextval(1)' AS label",
])
def test_calls_inside_escaped_strings_stay_reads(sql):
    assert resolve("cld.evidence_mode.sqlclass", "classify_sql")(sql) == "read"
