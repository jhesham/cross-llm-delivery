"""v0.5 review fixes (SQLSAFE): side-effecting SELECTs, complete redaction, execution timeout."""
import sys

import pytest

from tests.evidence._fixtures import FakeRunner, environment
from tests.evidence._lazy import resolve


@pytest.mark.parametrize("sql", [
    "SELECT nextval('orders_id_seq')",
    "SELECT setval('orders_id_seq', 10)",
    "SELECT * FROM orders FOR UPDATE",
    "SELECT * FROM orders FOR SHARE",
    "SELECT pg_advisory_lock(1)",
    "SELECT lo_import('/tmp/x')",
    "SELECT dblink_exec('db', 'DELETE FROM t')",
    "SELECT pg_terminate_backend(123)",
])
def test_side_effecting_selects_are_writes(sql):
    assert resolve("cld.evidence_mode.sqlclass", "classify_sql")(sql) == "write"


def test_plain_selects_with_functions_stay_reads():
    classify = resolve("cld.evidence_mode.sqlclass", "classify_sql")
    assert classify("SELECT count(*), max(updated_at) FROM orders") == "read"
    assert classify("SELECT 'nextval' AS label") == "read"


def _run(tmp_path, runner, sql="SELECT 1"):
    return resolve("cld.evidence_mode.sqlrun", "run_sql")(tmp_path, environment(), sql,
                                                           out_dir=tmp_path / "out", runner=runner)


def test_bearer_and_json_tokens_redacted(tmp_path):
    from tests.evidence._fixtures import FakeResult
    stderr = ('Authorization: Bearer sk-bearer-123\n{"access_token": "tok-json-456", "refresh_token":"r-789"}\n'
              'api_key=k-000')
    rec = _run(tmp_path, FakeRunner(FakeResult(returncode=1, stderr=stderr, error="nonzero_exit")))
    stored = "".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in (tmp_path / "out").rglob("*") if p.is_file())
    for secret in ("sk-bearer-123", "tok-json-456", "r-789", "k-000"):
        assert secret not in rec["stderr_tail"] and secret not in stored, secret


def test_no_unredacted_copy_left_by_the_real_runner(tmp_path, monkeypatch):
    """The shared runner keeps raw stdout/stderr files; none may retain a secret, wherever they land."""
    import tempfile
    system_temp = tmp_path / "system-temp"
    system_temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(system_temp))
    env = environment(command=(sys.executable, "-c",
                               "import sys; sys.stdin.read(); sys.stderr.write('password=hunter2-secret'); print('[]')"))
    resolve("cld.evidence_mode.sqlrun", "run_sql")(tmp_path, env, "SELECT 1", out_dir=tmp_path / "out")
    leaked = [p for p in tmp_path.rglob("*") if p.is_file()
              and "hunter2-secret" in p.read_text(encoding="utf-8", errors="replace")]
    assert leaked == [], leaked


def test_sql_uses_the_dispatch_deadline(tmp_path, monkeypatch):
    monkeypatch.setenv("CLD_DISPATCH_TIMEOUT", "1234")
    monkeypatch.setenv("CLD_PROBE_TIMEOUT", "30")
    runner = FakeRunner()
    _run(tmp_path, runner)
    assert runner.calls and runner.calls[0][1].get("timeout") == 1234.0
