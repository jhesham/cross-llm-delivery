"""Admission limits survive independent interpreter sessions, without providers."""
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tests.integration.test_attempt_resume import child_env
from tests.integration.test_t19_rehearsal import cli, rehearsal_repo

pytestmark = pytest.mark.integration


def test_second_process_cannot_spend_exhausted_first_process_budget(rehearsal_repo):
    repo = rehearsal_repo
    code = r'''
import json, sys
from cld.accounting import Accounting
from cld.admission import AdmissionBlocked
from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from tests.integration.harness import real_git_runner
repo, action = sys.argv[1:]
task = SliceTask("A", "offline budget probe", ["a.py"], "test_a.py")
ledger = Ledger.load(repo + "/.cld-ledger.json")
with ledger.writer(refresh=True):
    ledger.bind(repo, [task], real_git_runner)
    policy = {"attempts": 1, "tokens": 10, "attempt_tokens": 10} if action == "first" else None
    account = Accounting(ledger, policy)
    class Executor:
        def run(self, *args, **kwargs):
            assert action == "first", "a second executor invocation bypassed the persisted budget"
            return ExecutorResult(False, "", token_usage={"total": 10, "cost": 0})
    blocked = False
    try:
        account.wrap(Executor(), "fixture:offline").run(task, repo)
    except AdmissionBlocked:
        blocked = True
    print(json.dumps({"blocked": blocked, "usage": ledger.build["usage"]}))
'''
    rows = []
    for action in ("first", "second"):
        process = subprocess.run([sys.executable, "-c", code, str(repo), action],
                                 env=child_env(), capture_output=True, text=True, timeout=30)
        assert process.returncode == 0, process.stdout + process.stderr
        rows.append(json.loads(process.stdout))
    assert not rows[0]["blocked"] and rows[1]["blocked"]
    assert all(row["usage"]["attempts"] == 1 and row["usage"]["total"] == 10 for row in rows)
    assert rows[1]["usage"]["policy"]["attempts"] == 1
    attempts = list((Path(repo) / ".cld/runs").glob("*/usage/attempt-*.json"))
    assert len(attempts) == 1
    assert json.loads(attempts[0].read_text())["state"] == "finished"


def test_cli_readers_remain_valid_during_active_atomic_writes(rehearsal_repo):
    repo = rehearsal_repo
    ready = repo / ".cld/t19-writing"
    stop = repo / ".cld/t19-stop-writes"
    code = r'''
from pathlib import Path
import sys, time
from cld.cli import _install_telemetry
from cld.ledger import Ledger
from cld.plan.slice import load_slices
from cld import telemetry
from tests.integration.harness import real_git_runner
repo = Path(sys.argv[1])
ledger = Ledger.load(str(repo / ".cld-ledger.json"))
plan = repo / "plan.md"
text = plan.read_text()
with ledger.writer(refresh=True):
    ledger.bind(str(repo), load_slices(text), real_git_runner, plan_path=plan, plan_text=text)
    _install_telemetry(str(repo), ledger, str(plan), "fixture:offline")
    try:
        count = 0
        while not (repo / ".cld/t19-stop-writes").exists():
            count += 1
            ledger.set("A", status="pending", attempts=count)
            ledger.save()
            telemetry.emit("t19_write", count=count)
            (repo / ".cld/t19-writing").touch()
            time.sleep(.02)
    finally:
        telemetry.set_sink(None)
        telemetry.set_run_id(None)
'''
    child = subprocess.Popen([sys.executable, "-c", code, str(repo)], env=child_env(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.exists(), "atomic writer did not start"
        views = []
        for _ in range(3):
            process, view = cli(repo, "--status")
            assert process.returncode == 0, process.stderr
            views.append(view)
        assert len({view["run_id"] for view in views}) == 1
        counts = [next(row["attempts"] for row in view["slices"] if row["slice_id"] == "A") for view in views]
        assert counts == sorted(counts) and counts[-1] > counts[0]
        assert not (repo / ".cld/t19-executions.jsonl").exists()
    finally:
        stop.parent.mkdir(exist_ok=True)
        stop.touch()
        out, err = child.communicate(timeout=30)
    assert child.returncode == 0, out + err
