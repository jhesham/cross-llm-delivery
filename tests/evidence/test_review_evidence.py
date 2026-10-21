"""v0.5 review fixes (EVIDENCE): bundle provenance, dry-run safety, admission options, partial creations."""
import json
import sys
from pathlib import Path

from cld import cli
from cld.executors.base import ExecutorResult
from tests.evidence._fixtures import environment, write_environments
from tests.evidence._lazy import resolve
from tests.evidence.test_ask import FakeEvidenceExecutor, TASK, _repo, ask
from tests.evidence.test_bundle import make_dir
from tests.evidence.test_materialise import FakeMaterialiser, OBJ


def _check(d, *, task_env=("warehouse_sandbox",), task_id="q1", envs=None):
    bundle = resolve("cld.evidence_mode.bundle", "load_bundle")(d)
    check = resolve("cld.evidence_mode.bundle", "check_bundle")
    error = None
    try:
        return check(bundle, kind="query", evidence_dir=d,
                     environments=envs or {"warehouse_sandbox": environment()},
                     task_env=list(task_env), task_id=task_id)
    except TypeError as exc:
        error = str(exc)
    assert error is None, f"check_bundle task binding not supported: {error}"


# Finding 1: only successful runner records with existing results count.
def test_failed_runner_record_does_not_satisfy_sql_run(tmp_path):
    assert _check(make_dir(tmp_path, statuses={1: "failed"}))[0] == "incomplete"


def test_missing_reported_result_file_is_incomplete(tmp_path):
    d = make_dir(tmp_path)
    (d / "results" / "1.out").unlink()
    status, problems, _ = _check(d)
    assert status == "incomplete" and any("result" in p.lower() for p in problems)


def test_successful_record_with_result_still_complete(tmp_path):
    assert _check(make_dir(tmp_path))[0] == "complete"


# Finding 4: the bundle is bound to the submitted task.
def test_bundle_cannot_substitute_an_mcp_environment(tmp_path):
    d = make_dir(tmp_path, runs=("SELECT 1",), runner_records=())
    bundle = json.loads((d / "evidence.json").read_text(encoding="utf-8"))
    bundle["env"] = ["docs_mcp"]
    (d / "evidence.json").write_text(json.dumps(bundle), encoding="utf-8")
    envs = {"warehouse_sandbox": environment(),
            "docs_mcp": environment("docs_mcp", "real", command=(), mcp_only=True)}
    assert _check(d, envs=envs)[0] == "incomplete"


def test_bundle_task_id_must_match(tmp_path):
    assert _check(make_dir(tmp_path), task_id="another-task")[0] == "incomplete"


# Finding 3: --dry-run never executes SQL or records approvals.
def test_dry_run_with_sql_executes_nothing(tmp_path, capsys):
    marker = tmp_path / "ran.txt"
    script = f"import sys,pathlib; sys.stdin.read(); pathlib.Path(r'{marker}').write_text('x'); print('[]')"
    write_environments(tmp_path, [{"name": "warehouse_sandbox", "class": "sandbox", "platform": "bigquery",
                                   "command": [sys.executable, "-c", script], "read_only_expected": False}])
    q = tmp_path / "q.sql"
    q.write_text("SELECT 1", encoding="utf-8")
    code = cli.main(["--sql", str(q), "--env", "warehouse_sandbox", "--dry-run", "--repo", str(tmp_path), "--json"])
    capsys.readouterr()
    assert code == 5 and not marker.exists()


def test_dry_run_with_approve_records_nothing(tmp_path, capsys):
    write_environments(tmp_path, [{"name": "warehouse_prod", "class": "real", "platform": "bigquery",
                                   "command": ["bq", "query"], "read_only_expected": True}])
    code = cli.main(["--approve", "t1", "--env", "warehouse_prod", "--statement", "a" * 64, "--reason", "r",
                     "--dry-run", "--repo", str(tmp_path), "--json"])
    capsys.readouterr()
    assert code == 5 and not (tmp_path / ".cld" / "approvals.jsonl").exists()


# Finding 8: --ask keeps the caller's admission options and the admitted factory.
def test_cli_ask_uses_caller_admission_options_and_factory(tmp_path, capsys, monkeypatch):
    repo = _repo(tmp_path)
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(TASK), encoding="utf-8")
    seen, made = {}, []
    executor = FakeEvidenceExecutor()

    def factory(spec, evidence=False):
        made.append((spec, evidence))
        return executor

    def fake_prepare(args, tasks, ledger):
        seen["policy"], seen["revalidate"] = args.validation_policy, args.revalidate_models
        return (factory,)

    monkeypatch.setattr(cli, "prepare_dispatch", fake_prepare)
    code = cli.main(["--ask", str(task_file), "--executor", "codex:gpt-example@low", "--validation-policy", "allow",
                     "--revalidate-models", "--repo", str(repo), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert seen == {"policy": "allow", "revalidate": True}, seen
    assert made and all(evidence is True for _, evidence in made)
    assert code == 0 and out["status"] == "complete"


# Finding 10: objects created before a failure stay in the clean-up inventory.
class CreatesThenTimesOut(FakeMaterialiser):
    def run_evidence(self, prompt, workdir):
        super().run_evidence(prompt, workdir)
        return ExecutorResult(ok=False, diff="", raw_log="timed out", process={"error": "timeout"})


def test_partial_materialisation_is_listed_for_cleanup(tmp_path):
    repo = _repo(tmp_path)
    out = ask(repo, {**TASK, "id": "m9", "kind": "materialise"}, CreatesThenTimesOut())
    assert out["status"] == "failed"
    created = resolve("cld.evidence_mode.ask", "list_created")(repo)
    assert [c["name"] for c in created] == [OBJ["name"]] and created[0]["task_id"] == "m9"
