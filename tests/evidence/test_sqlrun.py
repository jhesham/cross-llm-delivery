"""v0.5 Task 5: the CLD SQL runner (layer 2 of real-environment enforcement)."""
import json
import sys

from cld import cli
from tests.evidence._fixtures import FakeResult, FakeRunner, echo_json_command, environment, write_environments
from tests.evidence._lazy import resolve

M = "cld.evidence_mode.sqlrun"


def run(tmp_path, env, sql, runner):
    return resolve(M, "run_sql")(tmp_path, env, sql, out_dir=tmp_path / "out", runner=runner)


def test_read_on_real_runs_and_records(tmp_path):
    runner = FakeRunner()
    rec = run(tmp_path, environment("warehouse_prod", "real"), "SELECT n FROM orders", runner)
    assert rec["status"] == "ok" and rec["classification"] == "read" and rec["rows"] == 2
    assert runner.calls and runner.calls[0][1].get("stdin") == "SELECT n FROM orders"
    for key in ("sql", "sql_hash", "env", "duration_s", "exit_code", "job_id", "result_path", "sql_path", "stderr_tail"):
        assert key in rec, key
    saved = json.loads(next((tmp_path / "out" / "runs").glob("*.json")).read_text(encoding="utf-8"))
    assert saved["sql_hash"] == rec["sql_hash"]
    assert (tmp_path / "out" / "sql").is_dir() and (tmp_path / "out" / "results").is_dir()


def test_write_on_real_needs_approval_and_does_not_execute(tmp_path):
    runner = FakeRunner()
    rec = run(tmp_path, environment("warehouse_prod", "real"), "DELETE FROM orders", runner)
    assert rec["status"] == "needs_approval" and runner.calls == []


def test_write_on_real_with_approval_runs(tmp_path):
    sql = "INSERT INTO orders VALUES (1)"
    h = resolve("cld.evidence_mode.sqlclass", "statement_hash")(sql)
    resolve("cld.evidence_mode.approvals", "record_approval")(
        tmp_path, env="warehouse_prod", sql_hash=h, approved_by="lead", reason="agreed backfill")
    runner = FakeRunner()
    assert run(tmp_path, environment("warehouse_prod", "real"), sql, runner)["status"] == "ok"
    assert runner.calls


def test_write_on_sandbox_runs(tmp_path):
    runner = FakeRunner()
    assert run(tmp_path, environment(), "CREATE TABLE t AS SELECT 1", runner)["status"] == "ok"


def test_missing_command_fails_clearly(tmp_path):
    rec = run(tmp_path, environment(command=("bq", "query")), "SELECT 1", FakeRunner(raises=FileNotFoundError("bq")))
    assert rec["status"] == "failed" and "bq" in rec.get("error", "")
    assert rec["rows"] is None


def test_nonzero_exit_is_failed(tmp_path):
    runner = FakeRunner(FakeResult(returncode=2, stderr="Syntax error at [1:1]", error="nonzero_exit"))
    rec = run(tmp_path, environment(), "SELECT broken", runner)
    assert rec["status"] == "failed" and "Syntax error" in rec["stderr_tail"]


def test_stderr_secrets_redacted(tmp_path):
    runner = FakeRunner(FakeResult(returncode=1, stderr="jdbc:pg://u:p4ss@h password=abc token: xyz", error="nonzero_exit"))
    rec = run(tmp_path, environment(), "SELECT 1", runner)
    stored = (tmp_path / "out" / "runs").glob("*.json").__next__().read_text(encoding="utf-8")
    for secret in ("p4ss", "abc", "xyz"):
        assert secret not in rec["stderr_tail"] and secret not in stored


def test_job_id_extracted(tmp_path):
    env = environment(job_id_pattern=r"Waiting on (\S+)")
    rec = run(tmp_path, env, "SELECT 1", FakeRunner(FakeResult(stdout="[]", stderr="Waiting on job_42 ... (0s)")))
    assert rec["job_id"] == "job_42"


def test_mcp_only_env_refused(tmp_path):
    runner = FakeRunner()
    rec = run(tmp_path, environment("docs_mcp", "real", command=(), mcp_only=True), "SELECT 1", runner)
    assert rec["status"] == "refused" and runner.calls == []


def _cli(argv, capsys):
    code = cli.main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_cli_sql_json_and_exit_codes(tmp_path, capsys):
    write_environments(tmp_path, [
        {"name": "warehouse_sandbox", "class": "sandbox", "platform": "bigquery",
         "command": echo_json_command(3), "read_only_expected": False},
        {"name": "warehouse_prod", "class": "real", "platform": "bigquery",
         "command": echo_json_command(1), "read_only_expected": True}])
    read = tmp_path / "read.sql"
    read.write_text("SELECT n FROM orders", encoding="utf-8")
    write = tmp_path / "write.sql"
    write.write_text("DROP TABLE orders", encoding="utf-8")
    code, payload = _cli(["--sql", str(read), "--env", "warehouse_sandbox", "--repo", str(tmp_path),
                          "--out", str(tmp_path / "ev")], capsys)
    assert code == 0 and payload["status"] == "ok" and payload["rows"] == 3
    code, payload = _cli(["--sql", str(write), "--env", "warehouse_prod", "--repo", str(tmp_path),
                          "--out", str(tmp_path / "ev")], capsys)
    assert code == 5 and payload["status"] == "needs_approval"


def test_cli_sql_allowed_inside_an_executor(tmp_path, capsys, monkeypatch):
    """The runner never dispatches, so the recursion guard must not block it."""
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    write_environments(tmp_path, [{"name": "warehouse_sandbox", "class": "sandbox", "platform": "bigquery",
                                   "command": echo_json_command(1), "read_only_expected": False}])
    q = tmp_path / "q.sql"
    q.write_text("SELECT 1", encoding="utf-8")
    code, payload = _cli(["--sql", str(q), "--env", "warehouse_sandbox", "--repo", str(tmp_path),
                          "--out", str(tmp_path / "ev")], capsys)
    assert code == 0 and payload["status"] == "ok"
