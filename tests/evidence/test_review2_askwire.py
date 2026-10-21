"""v0.5 second review (ASKWIRE): admitted factory on the API path, provider check first, held creations kept."""
import json

from cld import cli
from cld.executors.base import ExecutorResult
from tests.evidence._fixtures import prompt_task_id
from tests.evidence._lazy import resolve
from tests.evidence.test_ask import SQL, TASK, FakeEvidenceExecutor, _repo, ask
from tests.evidence.test_materialise import OBJ


def test_api_default_admission_uses_the_admitted_factory(tmp_path, monkeypatch):
    repo, executor, made = _repo(tmp_path), FakeEvidenceExecutor(), []

    def factory(spec, evidence=False):
        made.append(evidence)
        return executor

    monkeypatch.setattr(cli, "prepare_dispatch", lambda args, tasks, ledger: (factory,))
    out = resolve("cld.evidence_mode.ask", "run_ask")(repo, TASK, executor_spec="codex:gpt-example@low")
    assert made == [True], made
    assert executor.prompts and out["status"] == "complete", out


def test_cli_ask_rejects_unsupported_provider_before_admission(tmp_path, capsys, monkeypatch):
    repo, calls = _repo(tmp_path), []
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(TASK), encoding="utf-8")
    monkeypatch.setattr(cli, "prepare_dispatch", lambda *a: calls.append(a) or (lambda s, evidence=False: None,))
    code = cli.main(["--ask", str(task_file), "--executor", "opencode:zai/glm-4.6", "--repo", str(repo), "--json"])
    capsys.readouterr()
    assert code == 5 and calls == []


class CreatesThenHeld:
    """One CREATE ran in the sandbox; a second CREATE was held for approval."""

    def run_evidence(self, prompt, workdir):
        d = workdir
        for sub in ("runs", "sql", "results"):
            (d / sub).mkdir(exist_ok=True)
        h = resolve("cld.evidence_mode.sqlclass", "statement_hash")
        runs = []
        for i, (sql, status) in enumerate(((f"CREATE TABLE {OBJ['name']} AS {SQL}", "ok"),
                                           ("CREATE TABLE warehouse_sandbox.held AS " + SQL, "needs_approval")), 1):
            (d / "sql" / f"{i}.sql").write_text(sql, encoding="utf-8")
            (d / "results" / f"{i}.out").write_text("[]" if status == "ok" else "", encoding="utf-8")
            (d / "runs" / f"{i}.json").write_text(json.dumps({
                "sql": sql, "sql_hash": h(sql), "status": status, "env": "warehouse_sandbox",
                "sql_path": str(d / "sql" / f"{i}.sql"), "result_path": str(d / "results" / f"{i}.out")}),
                encoding="utf-8")
            runs.append({"sql_path": str(d / "sql" / f"{i}.sql"), "result_path": str(d / "results" / f"{i}.out")})
        (d / "evidence.json").write_text(json.dumps({
            "task_id": prompt_task_id(prompt), "kind": "materialise", "env": ["warehouse_sandbox"], "notes": "",
            "errors": [], "sql_runs": runs, "created_objects": [OBJ]}), encoding="utf-8")
        return ExecutorResult(ok=True, diff="", raw_log="held", process={})


def test_held_task_keeps_earlier_creations(tmp_path):
    repo = _repo(tmp_path)
    out = ask(repo, {**TASK, "id": "m7", "kind": "materialise"}, CreatesThenHeld())
    assert out["status"] == "needs_approval", out
    created = resolve("cld.evidence_mode.ask", "list_created")(repo)
    assert [c["name"] for c in created] == [OBJ["name"]]
