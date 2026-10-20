"""v0.5 Task 8: ask mode — one evidence task, dispatched, checked for completeness, returned."""
import json
import threading

from cld import cli
from cld.executors.base import ExecutorResult
from tests.evidence._fixtures import echo_json_command, write_environments
from tests.evidence._lazy import resolve

M = "cld.evidence_mode.ask"
SPEC = "codex:gpt-example@low"
SQL = "SELECT n FROM orders"


def _repo(tmp_path):
    write_environments(tmp_path, [{"name": "warehouse_sandbox", "class": "sandbox", "platform": "bigquery",
                                   "command": echo_json_command(1), "read_only_expected": False}])
    return tmp_path


class FakeEvidenceExecutor:
    """Simulates an executor that ran SQL through the runner and wrote evidence.json."""

    def __init__(self, *, rows=2, kind="query", fail=None, findings=False):
        self.rows, self.kind, self.fail, self.findings, self.prompts = rows, kind, fail, findings, []

    def run_evidence(self, prompt, workdir):
        self.prompts.append(prompt)
        if self.fail:
            return ExecutorResult(ok=False, diff="", raw_log="failed", process={"error": self.fail})
        d = workdir
        bundle = {"task_id": "t", "kind": self.kind, "env": ["warehouse_sandbox"], "notes": "", "errors": [],
                  "sql_runs": []}
        if self.kind in ("query", "materialise"):
            for sub in ("runs", "sql", "results"):
                (d / sub).mkdir(exist_ok=True)
            (d / "sql" / "1.sql").write_text(SQL, encoding="utf-8")
            (d / "results" / "1.out").write_text(json.dumps([{"n": i} for i in range(self.rows)]), encoding="utf-8")
            sql_hash = resolve("cld.evidence_mode.sqlclass", "statement_hash")(SQL)
            (d / "runs" / "1.json").write_text(json.dumps({"sql": SQL, "sql_hash": sql_hash, "status": "ok",
                                                           "result_path": str(d / "results" / "1.out")}), encoding="utf-8")
            bundle["sql_runs"] = [{"sql_path": str(d / "sql" / "1.sql"), "result_path": str(d / "results" / "1.out")}]
        if self.findings:
            (d / "findings.md").write_text("# Findings\n", encoding="utf-8")
            bundle["findings_path"] = str(d / "findings.md")
        (d / "evidence.json").write_text(json.dumps(bundle), encoding="utf-8")
        return ExecutorResult(ok=True, diff="", raw_log="done", process={})


def ask(repo, task, executor):
    try:
        return resolve(M, "run_ask")(repo, task, executor_spec=SPEC, make_executor=lambda spec: executor,
                                     admit=lambda spec: None)
    except TypeError as exc:
        message = str(exc)
    assert False, f"run_ask signature mismatch: {message}"


TASK = {"id": "q1", "kind": "query", "env": ["warehouse_sandbox"], "form": "question",
        "brief": "How many orders per day last week?"}


def test_question_query_complete(tmp_path):
    executor = FakeEvidenceExecutor()
    out = ask(_repo(tmp_path), TASK, executor)
    assert out["status"] == "complete" and out["runner_used"] is True and out["problems"] == []
    assert out["preview"]["rows"] == [{"n": 0}, {"n": 1}] and out["preview"]["truncated"] is False
    ev = tmp_path.joinpath(out["evidence_dir"]) if not out["evidence_dir"].startswith(str(tmp_path)) else None
    evidence_dir = ev or __import__("pathlib").Path(out["evidence_dir"])
    assert (evidence_dir / "task.json").is_file() and (evidence_dir / "run_sql.py").is_file()
    assert "run_sql.py" in executor.prompts[0] and "warehouse_sandbox" in executor.prompts[0]


def test_sql_form_requires_sql(tmp_path):
    out = ask(_repo(tmp_path), {**TASK, "form": "sql", "brief": None}, FakeEvidenceExecutor())
    assert out["status"] == "blocked" and "sql" in " ".join(out["problems"]).lower()


def test_undeclared_env_blocked(tmp_path):
    executor = FakeEvidenceExecutor()
    out = ask(_repo(tmp_path), {**TASK, "env": ["nowhere"]}, executor)
    assert out["status"] == "blocked" and executor.prompts == []


def test_unsupported_provider_blocked_before_dispatch(tmp_path):
    executor = FakeEvidenceExecutor()
    run_ask = resolve(M, "run_ask")
    out = run_ask(_repo(tmp_path), TASK, executor_spec="opencode:example/model",
                  make_executor=lambda spec: executor, admit=lambda spec: None)
    assert out["status"] == "blocked" and executor.prompts == []


def test_large_result_preview_is_capped(tmp_path):
    out = ask(_repo(tmp_path), TASK, FakeEvidenceExecutor(rows=100_000))
    assert len(out["preview"]["rows"]) <= 50 and out["preview"]["truncated"] is True
    assert len(json.dumps(out["preview"])) <= 16 * 1024 + 512


def test_ledger_line_has_no_row_data(tmp_path):
    ask(_repo(tmp_path), TASK, FakeEvidenceExecutor(rows=500))
    lines = _ledger_lines(tmp_path)
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["task_id"] == "q1" and entry["status"] == "complete" and "preview" not in entry
    assert '"n": 499' not in lines[0]


def test_final_error_reported_as_failed(tmp_path):
    out = ask(_repo(tmp_path), TASK, FakeEvidenceExecutor(fail="authentication"))
    assert out["status"] == "failed" and out.get("error") == "authentication"


def test_investigate_ask_returns_findings(tmp_path):
    task = {"id": "i1", "kind": "investigate", "env": ["warehouse_sandbox"], "form": "question",
            "brief": "Map the interfaces of example-org/service-a."}
    out = ask(_repo(tmp_path), task, FakeEvidenceExecutor(kind="investigate", findings=True))
    assert out["status"] == "complete"


def test_network_disabled_lead_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_SANDBOX_NETWORK_DISABLED", "1")
    executor = FakeEvidenceExecutor()
    out = ask(_repo(tmp_path), TASK, executor)
    assert out["status"] == "blocked" and executor.prompts == []


def test_executor_depth_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    executor = FakeEvidenceExecutor()
    out = ask(_repo(tmp_path), TASK, executor)
    assert out["status"] == "blocked" and executor.prompts == []


def _ledger_lines(repo):
    path = repo / ".cld" / "runs" / "ask" / "ledger.jsonl"
    assert path.is_file(), "ask ledger not written"
    return path.read_text(encoding="utf-8").splitlines()


def test_concurrent_ask_runs_keep_ledger_intact(tmp_path):
    resolve(M, "run_ask")
    repo = _repo(tmp_path)
    threads = [threading.Thread(target=ask, args=(repo, {**TASK, "id": f"q{i}"}, FakeEvidenceExecutor()))
               for i in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    lines = _ledger_lines(repo)
    assert sorted(json.loads(line)["task_id"] for line in lines) == ["q0", "q1"]


def test_cli_ask_requires_executor(tmp_path, capsys):
    task = tmp_path / "task.json"
    task.write_text(json.dumps(TASK), encoding="utf-8")
    code = cli.main(["--ask", str(task), "--repo", str(_repo(tmp_path)), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 5 and "executor" in json.dumps(payload).lower() and payload.get("command") == "ask"


def test_prompt_describes_bundle_format_per_kind(tmp_path):
    """A real executor must be told the evidence.json format, not left to guess it."""
    for kind, needle in (("query", "sql_runs"), ("materialise", "created_objects"), ("investigate", "findings_path")):
        executor = FakeEvidenceExecutor(kind=kind, findings=(kind == "investigate"))
        (tmp_path / kind).mkdir()
        ask(_repo(tmp_path / kind), {**TASK, "id": kind, "kind": kind}, executor)
        prompt = executor.prompts[0]
        for key in ("evidence.json", "task_id", "notes", "errors", "sql_path", "result_path", needle):
            assert key in prompt, (kind, key)


def test_runner_command_is_portable_across_shells(tmp_path):
    """Double-quoted paths and a plain `python` work in PowerShell, cmd and POSIX shells."""
    executor = FakeEvidenceExecutor()
    ask(_repo(tmp_path), TASK, executor)
    lines = [line for line in executor.prompts[0].splitlines() if "run_sql.py" in line and "--env" in line]
    assert lines, "no runner command in prompt"
    for line in lines:
        assert line.startswith('python "') and "'" not in line, line
