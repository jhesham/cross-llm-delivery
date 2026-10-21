"""v0.5 third review (REDACT3): authorization forms, line-bounded redaction, scrub."""
import sys

import pytest

from tests.evidence._fixtures import FakeResult, FakeRunner, environment
from tests.evidence._lazy import resolve

def _stored(tmp_path):
    return "".join(p.read_text(encoding="utf-8", errors="replace") for p in tmp_path.rglob("*") if p.is_file())


@pytest.mark.parametrize("stderr,secret", [
    ("Authorization=Basic SYNTHETIC_SECRET_1", "SYNTHETIC_SECRET_1"),
    ('{"authorization":"Basic SYNTHETIC_SECRET_2"}', "SYNTHETIC_SECRET_2"),
    ('{"Authorization": "SYNTHETIC_SECRET_3"}', "SYNTHETIC_SECRET_3"),
    ("Authorization: SYNTHETIC_SECRET_4\nrows=5", "SYNTHETIC_SECRET_4"),
])
def test_authorization_forms_redacted(tmp_path, stderr, secret):
    rec = resolve("cld.evidence_mode.sqlrun", "run_sql")(
        tmp_path, environment(), "SELECT 1", out_dir=tmp_path / "out",
        runner=FakeRunner(FakeResult(returncode=1, stderr=stderr, error="nonzero_exit")))
    assert secret not in rec["stderr_tail"] and secret not in _stored(tmp_path)


def test_authorization_redaction_stays_on_its_line(tmp_path):
    rec = resolve("cld.evidence_mode.sqlrun", "run_sql")(
        tmp_path, environment(), "SELECT 1", out_dir=tmp_path / "out",
        runner=FakeRunner(FakeResult(returncode=1, stderr="Authorization: SYNTHETIC_SECRET_5\nrows=5",
                                     error="nonzero_exit")))
    assert "rows=5" in rec["stderr_tail"], rec["stderr_tail"]


def test_locked_raw_output_scrub_covers_json_authorization(tmp_path, monkeypatch):
    module = __import__("cld.evidence_mode.sqlrun", fromlist=["_remove_raw_output"])
    monkeypatch.setattr(module, "_remove_raw_output", lambda path: None)
    env = environment(command=(sys.executable, "-c",
                               "import sys; sys.stdin.read(); "
                               "sys.stderr.write('{\"authorization\":\"Basic SYNTHETIC_SECRET_6\"}'); print('[]')"))
    rec = module.run_sql(tmp_path, env, "SELECT 1", out_dir=tmp_path / "out")
    assert rec["status"] == "failed" and "SYNTHETIC_SECRET_6" not in _stored(tmp_path)
