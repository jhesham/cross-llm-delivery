"""v0.5 Task 9: materialise tasks — created objects recorded for clean-up and rebuild, SQL kept."""
import json

from cld.executors.base import ExecutorResult
from tests.evidence._lazy import resolve
from tests.evidence.test_ask import SQL, _repo, ask

OBJ = {"name": "warehouse_sandbox.daily_orders", "rows": 7, "schema": [{"name": "day", "type": "DATE"}]}


class FakeMaterialiser:
    def __init__(self, *, objects=(OBJ,), runner_status="ok"):
        self.objects, self.runner_status, self.prompts = list(objects), runner_status, []

    def run_evidence(self, prompt, workdir):
        self.prompts.append(prompt)
        d = workdir
        for sub in ("runs", "sql", "results"):
            (d / sub).mkdir(exist_ok=True)
        sql = "CREATE TABLE warehouse_sandbox.daily_orders AS " + SQL
        (d / "sql" / "1.sql").write_text(sql, encoding="utf-8")
        (d / "results" / "1.out").write_text("[]", encoding="utf-8")
        h = resolve("cld.evidence_mode.sqlclass", "statement_hash")(sql)
        (d / "runs" / "1.json").write_text(json.dumps({"sql": sql, "sql_hash": h, "status": self.runner_status}),
                                           encoding="utf-8")
        (d / "evidence.json").write_text(json.dumps({
            "task_id": "m", "kind": "materialise", "env": ["warehouse_sandbox"], "notes": "", "errors": [],
            "sql_runs": [{"sql_path": str(d / "sql" / "1.sql"), "result_path": str(d / "results" / "1.out")}],
            "created_objects": self.objects}), encoding="utf-8")
        return ExecutorResult(ok=True, diff="", raw_log="done", process={})


TASK = {"id": "m1", "kind": "materialise", "env": ["warehouse_sandbox"], "form": "question",
        "brief": "Create a daily order count table in the sandbox."}


def _ledger(repo):
    path = repo / ".cld" / "runs" / "ask" / "ledger.jsonl"
    assert path.is_file(), "ask ledger not written"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_sandbox_materialise_complete_and_recorded(tmp_path):
    out = ask(_repo(tmp_path), TASK, FakeMaterialiser())
    assert out["status"] == "complete"
    assert _ledger(tmp_path)[-1].get("created") == [OBJ]


def test_real_materialise_without_approval_needs_approval(tmp_path):
    out = ask(_repo(tmp_path), TASK, FakeMaterialiser(runner_status="needs_approval"))
    assert out["status"] == "needs_approval"
    assert _ledger(tmp_path)[-1].get("created", []) == []


def test_malformed_created_object_is_incomplete(tmp_path):
    out = ask(_repo(tmp_path), TASK, FakeMaterialiser(objects=[{"name": "", "rows": -1}]))
    assert out["status"] == "incomplete" and any("created" in p for p in out["problems"])


def test_list_created_returns_objects_newest_first(tmp_path):
    repo = _repo(tmp_path)
    second = {**OBJ, "name": "warehouse_sandbox.weekly_orders"}
    ask(repo, TASK, FakeMaterialiser())
    ask(repo, {**TASK, "id": "m2"}, FakeMaterialiser(objects=[second]))
    created = resolve("cld.evidence_mode.ask", "list_created")(repo)
    assert [c["name"] for c in created] == ["warehouse_sandbox.weekly_orders", "warehouse_sandbox.daily_orders"]
    assert created[0]["task_id"] == "m2" and "evidence_dir" in created[0]


def test_materialise_sql_files_kept(tmp_path):
    out = ask(_repo(tmp_path), TASK, FakeMaterialiser())
    from pathlib import Path
    assert (Path(out["evidence_dir"]) / "sql" / "1.sql").is_file()
