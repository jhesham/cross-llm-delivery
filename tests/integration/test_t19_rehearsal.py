"""Lead-owned T19A acceptance: abrupt death, fresh CLI processes, real Git."""
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from cld.ledger import Ledger
from tests.integration.harness import init_repo
from tests.integration.test_attempt_resume import child_env
from tests.integration.test_review_regressions import checked_git

pytestmark = pytest.mark.integration
DRIVER = Path(__file__).with_name("t19_driver.py")


@pytest.fixture
def rehearsal_repo(tmp_path):
    repo = Path(init_repo(tmp_path / "repo with spaces"))
    files = {
        "a.py": "VALUE = 0\n", "b.py": "VALUE = 0\n",
        "test_a.py": "import a\ndef test_a(): assert a.VALUE == 42\n",
        "test_b.py": "import a, b\ndef test_b(): assert a.VALUE == b.VALUE == 42\n",
        "test_integration.py": "import a, b\ndef test_all(): assert a.VALUE == 42 and b.VALUE in (0, 42)\n",
        "plan.md": ("## SLICE: A\nbrief: Set a VALUE to 42\nfiles: a.py\n"
                    "acceptance_test_path: test_a.py\ndeps:\n\n"
                    "## SLICE: B\nbrief: Set b VALUE to 42\nfiles: b.py\n"
                    "acceptance_test_path: test_b.py\ndeps: A\n"),
    }
    for name, body in files.items():
        (repo / name).write_text(body, encoding="utf-8")
    checked_git(["add", "."], repo)
    checked_git(["commit", "-qm", "T19 immutable acceptance inputs"], repo)
    return repo


def driver(repo, action, stop="", expected=0):
    result = subprocess.run([sys.executable, str(DRIVER), str(repo), action, stop],
                            env=child_env(), capture_output=True, text=True, timeout=90)
    assert result.returncode == expected, result.stdout + result.stderr
    return json.loads(result.stdout) if expected == 0 else result


def cli(repo, *args, ledger=None):
    result = subprocess.run([sys.executable, "-m", "cld", str(repo / "plan.md"),
                             "--repo", str(repo), "--ledger", str(ledger or repo / ".cld-ledger.json"),
                             "--json", *args], env=child_env(), cwd=repo,
                            capture_output=True, text=True, timeout=30)
    return result, json.loads(result.stdout)


def executions(repo):
    path = repo / ".cld/t19-executions.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.mark.parametrize("phase", ["dispatch", "verified", "commit", "ledger", "merge", "test"])
def test_abrupt_death_resumes_without_loss_duplicate_or_skipped_dependency(rehearsal_repo, phase):
    repo = rehearsal_repo
    head = checked_git(["rev-parse", "HEAD"], repo)
    (repo / "a.py").write_text("VALUE = 999\n", encoding="utf-8")
    legacy_events = repo / ".cld/events.jsonl"
    legacy_events.parent.mkdir()
    legacy_events.write_text("old trace sentinel\n", encoding="utf-8")
    if phase in ("merge", "test"):
        driver(repo, "dispatch-a")
    driver(repo, "integrate" if phase in ("merge", "test") else "dispatch-a", phase, expected=91)
    crash = json.loads((repo / ".cld/t19-crash.json").read_text())
    assert crash["phase"] == phase and crash["pid"] > 0
    # A fresh process cannot dispatch B from unintegrated acceptance.
    blocked = driver(repo, "dispatch-b")
    assert blocked["deferred"] == ["B"] and [e["slice"] for e in executions(repo)] == ["A"]
    result = driver(repo, "resume")
    ledger = Ledger.load(str(repo / ".cld-ledger.json"))
    assert result["integrated_sha"] == ledger.build["integrated_sha"]
    assert ledger.get("A").status == ledger.get("B").status == "integrated"
    accepted = {sid: ledger.get(sid).commit for sid in ("A", "B")}
    expected_calls = ["A", "A", "B"] if phase in ("dispatch", "verified", "commit") else ["A", "B"]
    assert [e["slice"] for e in executions(repo)] == expected_calls
    assert len({e["pid"] for e in executions(repo)}) == 2
    for sid, commit in accepted.items():
        checked_git(["merge-base", "--is-ancestor", commit, result["integrated_sha"]], repo)
        assert checked_git(["show", f"{commit}:{sid.lower()}.py"], repo) == "VALUE = 42\n"
    if phase == "commit":
        assert checked_git(["show", f"{crash['head']}:a.py"], repo) == "VALUE = 42\n"
    if phase in ("dispatch", "verified", "commit"):
        records = [json.loads(path.read_text()) for path in (repo / ".cld/runs").glob("*/A/*/outcome.json")]
        prior = [record for record in records if record["state"] != "collected"]
        assert len(prior) == 1 and Path(prior[0]["worktree"]).is_dir()
        assert (Path(prior[0]["worktree"]) / "a.py").read_text() == "VALUE = 42\n"
        assert checked_git(["show", f"{prior[0]['recovery_ref']}:a.py"], repo) == "VALUE = 42\n"
    again = driver(repo, "resume")
    assert again["integrated_sha"] == result["integrated_sha"]
    assert {sid: Ledger.load(ledger.path).get(sid).commit for sid in accepted} == accepted
    assert len(executions(repo)) == len(expected_calls)
    refs = checked_git(["for-each-ref", "--format=%(refname)", "refs/cld/accepted"], repo).splitlines()
    assert len(refs) == 2, "one accepted ref per slice"
    assert checked_git(["rev-parse", "HEAD"], repo) == head
    assert (repo / "a.py").read_text() == "VALUE = 999\n"
    assert (repo / "b.py").read_text() == "VALUE = 0\n"
    assert legacy_events.read_text() == "old trace sentinel\n"


def test_legacy_partial_failed_missing_ref_backup_and_reconcile_in_fresh_cli(rehearsal_repo):
    repo = rehearsal_repo
    driver(repo, "dispatch-a")
    current = Ledger.load(str(repo / ".cld-ledger.json"))
    record = Path(current.get("A").recovery_path) / "outcome.json"
    journal = json.loads(record.read_text())
    legacy_dir = repo / ".cld/A" / journal["session_id"]
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "outcome.json").write_bytes(record.read_bytes())
    raw = json.loads(Path(current.path).read_text())
    raw = json.dumps({"A": raw["entries"]["A"], "B": {"status": "failed", "commit": "missing"}}).encode()
    Path(current.path).write_bytes(raw)
    (repo / "a.py").write_text("VALUE = 999\n")
    denied, _ = cli(repo, "--step")
    assert denied.returncode == 5 and Path(current.path).read_bytes() == raw
    migrated, _ = cli(repo, "--migrate-ledger")
    assert migrated.returncode == 0, migrated.stderr
    state = Ledger.load(current.path)
    assert state.get("A").status == "done" and state.get("B").status == "failed"
    assert state.build["integrated_sha"] is None
    assert Path(state.build["backup"]).read_bytes() == raw
    before = Path(state.path).read_bytes()
    repeated, _ = cli(repo, "--migrate-ledger")
    assert repeated.returncode == 0 and Path(state.path).read_bytes() == before
    # Missing accepted ref must never become integration success.
    checked_git(["update-ref", "-d", state.get("A").collection["ref"]], repo)
    bad, _ = cli(repo, "--integrate", "--integration-tests", "test_integration.py")
    assert bad.returncode == 5 and Ledger.load(state.path).build["integrated_sha"] is None
    plan = repo / "plan.md"
    plan.write_text(plan.read_text().replace("Set a VALUE", "Changed a VALUE"))
    blocked, _ = cli(repo, "--step")
    assert blocked.returncode == 5
    old_run = state.build["run_id"]
    reconciled, _ = cli(repo, "--reconcile-plan")
    assert reconciled.returncode == 0
    fresh = Ledger.load(state.path)
    assert fresh.build["run_id"] != old_run
    assert fresh.get("A").status == fresh.get("B").status == "pending"
    assert Path(fresh.build["backup"]).read_bytes() != raw
    assert record.exists() and (legacy_dir / "outcome.json").exists()
    assert (repo / "a.py").read_text() == "VALUE = 999\n"


def test_corrupt_state_is_preserved_by_fresh_cli(rehearsal_repo):
    repo = rehearsal_repo
    path = repo / ".cld-ledger.json"
    path.write_bytes(b"{corrupt T19")
    result, _ = cli(repo, "--migrate-ledger")
    assert result.returncode == 5 and path.read_bytes() == b"{corrupt T19"
    assert not executions(repo)


def test_status_under_writer_and_separate_cli_build_isolation(rehearsal_repo):
    repo = rehearsal_repo
    ready = repo / ".cld/t19-ready"
    child = subprocess.Popen([sys.executable, str(DRIVER), str(repo), "hold", ""],
                             env=child_env(), stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.exists(), "writer did not acquire ledger"
        current = Ledger.load(str(repo / ".cld-ledger.json"))
        before = Path(current.path).read_bytes()
        status, view = cli(repo, "--status")
        assert status.returncode == 0 and view["run_id"] == current.build["run_id"]
        same, _ = cli(repo, "--new-build")
        assert same.returncode == 5 and Path(current.path).read_bytes() == before
        other = repo / ".cld/other-ledger.json"
        separate, _ = cli(repo, "--new-build", ledger=other)
        assert separate.returncode == 0, separate.stderr
        second = Ledger.load(str(other))
        assert second.build["run_id"] != current.build["run_id"]
        assert Path(current.path).read_bytes() == before
        first_events = repo / ".cld/runs" / current.build["run_id"] / "events.jsonl"
        second_events = repo / ".cld/runs" / second.build["run_id"] / "events.jsonl"
        # State preparation deliberately emits no delivery telemetry. Start a
        # second run-scoped sink in its own process without accessing a provider.
        assert not second_events.exists()
        first_trace = first_events.read_bytes()
        code = '''
import sys
from cld.cli import _install_telemetry
from cld.ledger import Ledger
from cld import telemetry
repo, path = sys.argv[1:]
ledger = Ledger.load(path)
with ledger.writer():
    _install_telemetry(repo, ledger, repo + "/plan.md", "fixture:offline")
    telemetry.emit("t19_separate_build")
    telemetry.set_sink(None)
    telemetry.set_run_id(None)
'''
        emitted = subprocess.run([sys.executable, "-c", code, str(repo), str(other)],
                                 env=child_env(), capture_output=True, text=True, timeout=30)
        assert emitted.returncode == 0, emitted.stdout + emitted.stderr
        assert first_events.read_bytes() == first_trace
        for path, run_id in ((first_events, current.build["run_id"]), (second_events, second.build["run_id"])):
            assert all(json.loads(line)["run_id"] == run_id for line in path.read_text().splitlines())
        assert not executions(repo)
    finally:
        out, err = child.communicate("release\n", timeout=20)
    assert child.returncode == 0, out + err
    released, _ = cli(repo, "--new-build")
    assert released.returncode == 0
