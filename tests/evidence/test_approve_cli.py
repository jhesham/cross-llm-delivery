"""v0.5 Task 10: --approve records an approval; a re-run then executes exactly that statement."""
import json

from cld import cli
from tests.evidence._fixtures import echo_json_command, write_environments
from tests.evidence._lazy import resolve

WRITE = "INSERT INTO orders VALUES (1)"


def _repo(tmp_path):
    write_environments(tmp_path, [{"name": "warehouse_prod", "class": "real", "platform": "bigquery",
                                   "command": echo_json_command(1), "read_only_expected": True}])
    return tmp_path


def _env(repo):
    return resolve("cld.evidence_mode.environments", "load_environments")(repo)["warehouse_prod"]


def _run(repo, sql):
    return resolve("cld.evidence_mode.sqlrun", "run_sql")(repo, _env(repo), sql, out_dir=repo / "ev")


def _approve(repo, capsys, sql_hash, reason="agreed with owner"):
    code = cli.main(["--approve", "t1", "--env", "warehouse_prod", "--statement", sql_hash,
                     "--reason", reason, "--repo", str(repo), "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_approve_then_rerun_executes(tmp_path, capsys):
    repo = _repo(tmp_path)
    first = _run(repo, WRITE)
    assert first["status"] == "needs_approval"
    code, payload = _approve(repo, capsys, first["sql_hash"])
    assert code == 0 and payload.get("command") == "approve"
    assert payload.get("sql_hash") == first["sql_hash"] and payload.get("task_id") == "t1"
    assert _run(repo, WRITE)["status"] == "ok"


def test_changed_statement_needs_new_approval(tmp_path, capsys):
    repo = _repo(tmp_path)
    first = _run(repo, WRITE)
    code, _ = _approve(repo, capsys, first["sql_hash"])
    assert code == 0, "--approve must succeed for a valid request"
    assert _run(repo, "INSERT INTO orders VALUES (2)")["status"] == "needs_approval"


def test_approve_requires_reason(tmp_path, capsys):
    repo = _repo(tmp_path)
    code, payload = _approve(repo, capsys, "a" * 64, reason="  ")
    assert code == 5 and payload.get("command") == "approve"
    assert resolve("cld.evidence_mode.approvals", "is_approved")(repo, env="warehouse_prod", sql_hash="a" * 64) is False


def test_approve_rejects_undeclared_env_and_bad_hash(tmp_path, capsys):
    repo = _repo(tmp_path)
    ok, _ = _approve(repo, capsys, "b" * 64)
    assert ok == 0, "--approve must succeed for a valid request"
    code = cli.main(["--approve", "t1", "--env", "nowhere", "--statement", "a" * 64, "--reason", "r",
                     "--repo", str(repo), "--json"])
    assert code == 5
    capsys.readouterr()
    code, _ = _approve(repo, capsys, "not-a-hash")
    assert code == 5


def test_executor_cannot_approve_its_own_write(tmp_path, capsys, monkeypatch):
    """Approvals come from the user or lead, never from inside a dispatched executor."""
    repo = _repo(tmp_path)
    first = _run(repo, WRITE)
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    code, payload = _approve(repo, capsys, first["sql_hash"])
    assert code == 5 and payload.get("status") == "blocked"
    assert "executor" in payload.get("error", "").lower()
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH")
    assert _run(repo, WRITE)["status"] == "needs_approval"
