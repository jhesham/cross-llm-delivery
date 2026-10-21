"""v0.5 Task 6: evidence bundle completeness (CLD checks completeness, never correctness)."""
import json

import pytest

from tests.evidence._fixtures import environment
from tests.evidence._lazy import resolve

M = "cld.evidence_mode.bundle"
SQL = "SELECT n FROM orders"


def _hash(sql):
    return resolve("cld.evidence_mode.sqlclass", "statement_hash")(sql)


def make_dir(tmp_path, *, kind="query", runs=(SQL,), runner_records=(SQL,), statuses=None,
             extra=None, notes=True, write_bundle=True):
    d = tmp_path / "ev"
    for sub in ("runs", "sql", "results"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    for i, sql in enumerate(runner_records, 1):
        (d / "sql" / f"{i}.sql").write_text(sql, encoding="utf-8")
        (d / "results" / f"{i}.out").write_text("[]", encoding="utf-8")
        status = (statuses or {}).get(i, "ok")
        (d / "runs" / f"{i}.json").write_text(json.dumps({"sql": sql, "sql_hash": _hash(sql), "status": status,
                                                          "result_path": str(d / "results" / f"{i}.out"),
                                                          "env": "warehouse_sandbox"}), encoding="utf-8")
    sql_runs = []
    for i, sql in enumerate(runs, 1):
        p = d / "sql" / f"reported-{i}.sql"
        p.write_text(sql, encoding="utf-8")
        sql_runs.append({"sql_path": str(p), "result_path": str(d / "results" / "1.out")})
    bundle = {"task_id": "q1", "kind": kind, "env": ["warehouse_sandbox"], "sql_runs": sql_runs, "errors": []}
    if notes:
        bundle["notes"] = ""
    bundle.update(extra or {})
    if write_bundle:
        (d / "evidence.json").write_text(json.dumps(bundle), encoding="utf-8")
    return d


def check(d, kind="query", envs=None):
    bundle = resolve(M, "load_bundle")(d)
    return resolve(M, "check_bundle")(bundle, kind=kind, evidence_dir=d,
                                      environments=envs or {"warehouse_sandbox": environment()},
                                      task_env=["warehouse_sandbox"], task_id="q1")


def test_complete_query_bundle(tmp_path):
    assert check(make_dir(tmp_path)) == ("complete", [], True)


def test_missing_bundle_is_incomplete(tmp_path):
    status, problems, _ = check(make_dir(tmp_path, write_bundle=False))
    assert status == "incomplete" and problems


def test_invalid_json_bundle_is_incomplete(tmp_path):
    d = make_dir(tmp_path)
    (d / "evidence.json").write_text("{not json", encoding="utf-8")
    assert check(d)[0] == "incomplete"


def test_query_without_runs_is_incomplete(tmp_path):
    assert check(make_dir(tmp_path, runs=()))[0] == "incomplete"


def test_missing_notes_key_is_a_problem(tmp_path):
    status, problems, _ = check(make_dir(tmp_path, notes=False))
    assert status == "incomplete" and any("notes" in p for p in problems)


def test_materialise_requires_created_objects(tmp_path):
    assert check(make_dir(tmp_path, kind="materialise"), kind="materialise")[0] == "incomplete"
    ok = make_dir(tmp_path, kind="materialise",
                  extra={"created_objects": [{"name": "sandbox.t", "rows": 3, "schema": [{"name": "n", "type": "INT64"}]}]})
    assert check(ok, kind="materialise")[0] == "complete"


def test_investigate_requires_existing_findings(tmp_path):
    d = make_dir(tmp_path, kind="investigate", runs=(), runner_records=(),
                 extra={"findings_path": str(tmp_path / "missing.md")})
    assert check(d, kind="investigate")[0] == "incomplete"
    findings = tmp_path / "findings.md"
    findings.write_text("# Findings\n", encoding="utf-8")
    d = make_dir(tmp_path, kind="investigate", runs=(), runner_records=(), extra={"findings_path": str(findings)})
    assert check(d, kind="investigate")[0] == "complete"


def test_sql_not_in_runner_records_is_flagged(tmp_path):
    status, problems, runner_used = check(make_dir(tmp_path, runs=("SELECT secret_other FROM t",)))
    assert status == "incomplete" and runner_used is False and problems


def test_mcp_only_env_does_not_require_runner(tmp_path):
    d = make_dir(tmp_path, runs=("SELECT 1",), runner_records=())
    envs = {"warehouse_sandbox": environment("warehouse_sandbox", "real", command=(), mcp_only=True)}
    status, problems, runner_used = check(d, envs=envs)
    assert status == "complete" and runner_used is False


def test_needs_approval_propagates(tmp_path):
    assert check(make_dir(tmp_path, statuses={1: "needs_approval"}))[0] == "needs_approval"
