"""v0.5 third review (PROVENANCE3): runner attempts reconciled by identity."""
import json

from tests.evidence._fixtures import environment
from tests.evidence._lazy import resolve

SQL_A = "SELECT order_day, count(*) FROM orders GROUP BY 1"
SQL_B = "SELECT count(*) FROM refunds"


def _build(tmp_path, records, reported, *, bundle_env=("warehouse_sandbox",), kind="query"):
    """records: (sql, status, env) per runner attempt; reported: 1-based attempts listed in sql_runs."""
    d = tmp_path / "ev"
    for sub in ("runs", "sql", "results"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    h = resolve("cld.evidence_mode.sqlclass", "statement_hash")
    for i, (sql, status, env) in enumerate(records, 1):
        (d / "sql" / f"{i}.sql").write_text(sql, encoding="utf-8")
        (d / "results" / f"{i}.out").write_text("[]" if status == "ok" else "", encoding="utf-8")
        (d / "runs" / f"{i}.json").write_text(json.dumps({
            "sql": sql, "sql_hash": h(sql), "status": status, "env": env,
            "sql_path": str(d / "sql" / f"{i}.sql"), "result_path": str(d / "results" / f"{i}.out")}),
            encoding="utf-8")
    runs = [{"sql_path": str(d / "sql" / f"{i}.sql"), "result_path": str(d / "results" / f"{i}.out")}
            for i in reported]
    (d / "evidence.json").write_text(json.dumps({"task_id": "q1", "kind": kind, "env": list(bundle_env),
                                                 "notes": "", "errors": [], "sql_runs": runs}), encoding="utf-8")
    return d


def _check(d, task_env=("warehouse_sandbox",), kind="query"):
    envs = {"warehouse_sandbox": environment(), "warehouse_prod": environment("warehouse_prod", "real")}
    bundle = resolve("cld.evidence_mode.bundle", "load_bundle")(d)
    return resolve("cld.evidence_mode.bundle", "check_bundle")(
        bundle, kind=kind, evidence_dir=d, environments=envs, task_env=list(task_env), task_id="q1")


def test_omitted_held_attempt_is_not_complete(tmp_path):
    d = _build(tmp_path, [(SQL_A, "ok", "warehouse_sandbox"), (SQL_B, "needs_approval", "warehouse_sandbox")], [1])
    assert _check(d)[0] == "incomplete"


def test_omitted_successful_attempt_is_not_complete(tmp_path):
    d = _build(tmp_path, [(SQL_A, "ok", "warehouse_sandbox"), (SQL_B, "ok", "warehouse_sandbox")], [1])
    assert _check(d)[0] == "incomplete"


def test_failed_attempts_need_not_be_reported(tmp_path):
    d = _build(tmp_path, [(SQL_B, "failed", "warehouse_sandbox"), (SQL_A, "ok", "warehouse_sandbox")], [2])
    assert _check(d) == ("complete", [], True)


def test_held_attempt_superseded_by_approved_run_matches_by_identity(tmp_path):
    d = _build(tmp_path, [(SQL_A, "needs_approval", "warehouse_sandbox"), (SQL_A, "ok", "warehouse_sandbox")], [2])
    assert _check(d) == ("complete", [], True)


def test_reported_run_resolves_to_its_own_record(tmp_path):
    d = _build(tmp_path, [(SQL_A, "needs_approval", "warehouse_sandbox"), (SQL_A, "ok", "warehouse_sandbox")], [1])
    status, problems, _ = _check(d)
    assert status == "needs_approval", problems


def test_matched_run_environment_must_be_reported(tmp_path):
    d = _build(tmp_path, [(SQL_A, "ok", "warehouse_prod")], [1], bundle_env=("warehouse_sandbox",))
    assert _check(d, task_env=("warehouse_sandbox", "warehouse_prod"))[0] == "incomplete"
