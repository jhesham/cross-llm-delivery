"""Test-only abrupt-death driver; never imported by production."""
import json
import os
from pathlib import Path
import sys

from cld import integration, recovery, telemetry
from cld.cli import _install_telemetry
from cld.executors.base import ExecutorResult
from cld.judge import judge
from cld.ledger import Ledger
from cld.orchestrator import run_plan_parallel
from cld.plan.slice import load_slices
from tests.integration.harness import real_git_runner
from tests.integration.test_review_regressions import acceptance, checked_git


def main(repo, action, stop=""):
    repo = Path(repo).resolve()
    root = repo / ".cld"
    root.mkdir(exist_ok=True)
    plan = repo / "plan.md"
    text = plan.read_text(encoding="utf-8")
    tasks = load_slices(text)
    ledger = Ledger.load(str(repo / ".cld-ledger.json"))

    def crash(phase, cwd):
        if phase == stop:
            (root / "t19-crash.json").write_text(json.dumps({
                "phase": phase, "pid": os.getpid(),
                "head": checked_git(["rev-parse", "HEAD"], cwd).strip(),
            }), encoding="utf-8")
            os._exit(91)  # no finally or recovery unwinding

    save_session = recovery.RecoverySession.save
    def session_save(session, **values):
        save_session(session, **values)
        if values.get("state") == "verified":
            crash("verified", session.cwd)
        if values.get("patch", "").endswith("dispatch.patch"):
            crash("dispatch", session.cwd)
    recovery.RecoverySession.save = session_save

    save_ledger = Ledger.save
    def ledger_save(instance):
        save_ledger(instance)
        if instance.get("A") and instance.get("A").status == "done":
            crash("ledger", instance.build["repo"])
    Ledger.save = ledger_save

    write_integration = integration.atomic_write
    def integration_write(path, data):
        write_integration(path, data)
        if path.name == "outcome.json":
            record = json.loads(data)
            if record.get("state") == "candidate":
                crash("merge", record["worktree"])
            if record.get("state") == "passed":
                crash("test", record["worktree"])
    integration.atomic_write = integration_write

    def runner(args, cwd):
        result = real_git_runner(args, cwd)
        if result[0] == 0 and args[:2] == ["git", "commit"]:
            crash("commit", cwd)
        return result

    with ledger.writer(refresh=True):
        ledger.bind(str(repo), tasks, runner, plan_path=plan, plan_text=text)

    class Writer:
        def run(self, task, workdir, feedback=None):
            with (root / "t19-executions.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"slice": task.id, "pid": os.getpid()}) + "\n")
            for name in task.files:
                (Path(workdir) / name).write_text("VALUE = 42\n", encoding="utf-8")
            return ExecutorResult(True, "", token_usage={"total": 0, "cost": 0}, raw_log="offline fixture")

    def dispatch(sid):
        result = run_plan_parallel([task for task in tasks if task.id == sid], ledger,
            plan_slices=tasks, executor=Writer(), judge_fn=judge, max_workers=1,
            max_retries=0, repo_dir=str(repo), git_runner=runner, test_runner=acceptance)
        if result.failed or result.blocked or result.needs_repair:
            raise RuntimeError(repr(result))
        return {"completed": result.completed, "deferred": result.deferred}

    def merge():
        result = integration.integrate(tasks, ledger, repo_dir=str(repo),
            git_runner=runner, test_runner=acceptance, selector="test_integration.py")
        if not result.passed:
            raise RuntimeError(result.error)
        return {"integrated_sha": result.commit}

    if action == "hold":
        with ledger.writer():
            _install_telemetry(str(repo), ledger, str(plan), "fixture:offline")
            try:
                telemetry.emit("t19_writer_held")
                (root / "t19-ready").write_text(str(os.getpid()), encoding="utf-8")
                sys.stdin.readline()
            finally:
                telemetry.set_sink(None)
                telemetry.set_run_id(None)
        result = {"held": True}
    elif action in ("dispatch-a", "dispatch-b"):
        result = dispatch(action[-1].upper())
    elif action == "integrate":
        result = merge()
    elif action == "resume":
        dispatch("A")
        merge()
        dispatch("B")
        result = merge()
    else:
        raise ValueError(f"Unknown rehearsal action: {action}")
    print(json.dumps(result))


if __name__ == "__main__":
    main(*sys.argv[1:])
