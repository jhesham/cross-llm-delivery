"""Findings from the live PostgreSQL test: CSV runner output gets a row count and a preview."""
import json

from tests.evidence._fixtures import FakeResult, FakeRunner, environment
from tests.evidence._lazy import resolve
from tests.evidence.test_ask import TASK, _repo, ask

CSV = "order_day,order_count,total_amount\n2026-01-01,3,420.00\n2026-01-02,4,388.00\n"


def test_csv_output_counts_rows(tmp_path):
    rec = resolve("cld.evidence_mode.sqlrun", "run_sql")(
        tmp_path, environment(), "SELECT 1", out_dir=tmp_path / "out",
        runner=FakeRunner(FakeResult(returncode=0, stdout=CSV)))
    assert rec["rows"] == 2, rec["rows"]


def test_json_output_still_counts_rows(tmp_path):
    rec = resolve("cld.evidence_mode.sqlrun", "run_sql")(
        tmp_path, environment(), "SELECT 1", out_dir=tmp_path / "out",
        runner=FakeRunner(FakeResult(returncode=0, stdout=json.dumps([{"n": 1}, {"n": 2}, {"n": 3}]))))
    assert rec["rows"] == 3


class CsvExecutor:
    def run_evidence(self, prompt, workdir):
        from cld.executors.base import ExecutorResult
        from tests.evidence._fixtures import prompt_task_id
        d = workdir
        for sub in ("runs", "sql", "results"):
            (d / sub).mkdir(exist_ok=True)
        sql = "SELECT order_day, count(*) AS order_count, sum(amount) AS total_amount FROM orders GROUP BY 1"
        (d / "sql" / "1.sql").write_text(sql, encoding="utf-8")
        (d / "results" / "1.out").write_text(CSV, encoding="utf-8")
        h = resolve("cld.evidence_mode.sqlclass", "statement_hash")(sql)
        (d / "runs" / "1.json").write_text(json.dumps({
            "sql": sql, "sql_hash": h, "status": "ok", "env": "warehouse_sandbox",
            "sql_path": str(d / "sql" / "1.sql"), "result_path": str(d / "results" / "1.out")}), encoding="utf-8")
        (d / "evidence.json").write_text(json.dumps({
            "task_id": prompt_task_id(prompt), "kind": "query", "env": ["warehouse_sandbox"], "notes": "",
            "errors": [], "sql_runs": [{"sql_path": str(d / "sql" / "1.sql"),
                                        "result_path": str(d / "results" / "1.out")}]}), encoding="utf-8")
        return ExecutorResult(ok=True, diff="", raw_log="done", process={})


def test_csv_result_is_previewed(tmp_path):
    out = ask(_repo(tmp_path), TASK, CsvExecutor())
    assert out["status"] == "complete", out
    assert out["preview"]["rows"] == [
        {"order_day": "2026-01-01", "order_count": "3", "total_amount": "420.00"},
        {"order_day": "2026-01-02", "order_count": "4", "total_amount": "388.00"},
    ], out["preview"]
