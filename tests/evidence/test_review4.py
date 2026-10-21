"""v0.5 fourth review: continued escape strings, and authorization/bearer/apiKey redaction."""
import sys

import pytest

from tests.evidence._fixtures import FakeResult, FakeRunner, environment
from tests.evidence._lazy import resolve


def test_continued_escape_string_cannot_hide_a_call():
    sql = "SELECT E'prefix'\n'\\'' || nextval('s') || E'\\''"
    assert resolve("cld.evidence_mode.sqlclass", "classify_sql")(sql) == "write"


def test_continued_ordinary_strings_stay_reads():
    assert resolve("cld.evidence_mode.sqlclass", "classify_sql")("SELECT 'a'\n'b' || 'nextval(1)'") == "read"


def _stored(tmp_path):
    return "".join(p.read_text(encoding="utf-8", errors="replace") for p in tmp_path.rglob("*") if p.is_file())


@pytest.mark.parametrize("stderr,secret", [
    ("Authorization: SYNTHETIC_SECRET_7 status=403", "SYNTHETIC_SECRET_7"),
    ("Authorization: Basic SYNTHETIC_SECRET_8", "SYNTHETIC_SECRET_8"),
    ("request failed: Bearer SYNTHETIC_SECRET_9", "SYNTHETIC_SECRET_9"),
    ("apiKey=SYNTHETIC_SECRET_10", "SYNTHETIC_SECRET_10"),
    ("x-api-key: SYNTHETIC_SECRET_11", "SYNTHETIC_SECRET_11"),
])
def test_remaining_credential_forms_redacted(tmp_path, stderr, secret):
    rec = resolve("cld.evidence_mode.sqlrun", "run_sql")(
        tmp_path, environment(), "SELECT 1", out_dir=tmp_path / "out",
        runner=FakeRunner(FakeResult(returncode=1, stderr=stderr, stdout=stderr, error="nonzero_exit")))
    assert secret not in rec["stderr_tail"] and secret not in _stored(tmp_path)


def test_locked_raw_output_scrub_covers_unschemed_authorization(tmp_path, monkeypatch):
    module = __import__("cld.evidence_mode.sqlrun", fromlist=["_remove_raw_output"])
    monkeypatch.setattr(module, "_remove_raw_output", lambda path: None)
    env = environment(command=(sys.executable, "-c",
                               "import sys; sys.stdin.read(); "
                               "sys.stderr.write('Authorization: SYNTHETIC_SECRET_12 status=403'); print('[]')"))
    rec = module.run_sql(tmp_path, env, "SELECT 1", out_dir=tmp_path / "out")
    assert rec["status"] == "failed" and "SYNTHETIC_SECRET_12" not in _stored(tmp_path)
