"""T05 state safety with actual Git/files/process ownership, no paid providers."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from cld import ledger as ledger_module
from cld.build_state import run_directory
from cld.executors.base import SliceTask
from cld.ledger import Ledger, StateError, resolve_ledger
from cld.locking import OwnerBusy
from tests.integration.harness import real_git_runner, init_repo
from tests.integration.test_attempt_resume import child_env
from tests.integration.test_review_regressions import delivery_repo

pytestmark = pytest.mark.integration


def task(sid="A", deps=(), brief="implement"):
    return SliceTask(id=sid, brief=brief, files=["code.py"], acceptance_test_path="test_code.py", deps=list(deps))


def bind(repo, tasks=None, *, ledger=None, **options):
    ledger = ledger or Ledger(resolve_ledger(repo))
    with ledger.writer(refresh=True):
        ledger.bind(str(repo), tasks or [task()], real_git_runner, **options)
    return ledger


def test_default_repo_scope_and_explicit_cwd_semantics(tmp_path, monkeypatch):
    first = Path(init_repo(tmp_path / "one"))
    second = Path(init_repo(tmp_path / "two"))
    caller = tmp_path / "caller"
    caller.mkdir()
    monkeypatch.chdir(caller)
    one, two = bind(first), bind(second)
    assert one.path != two.path and one.build["run_id"] != two.build["run_id"]
    assert resolve_ledger(first, "explicit.json") == str(caller / "explicit.json")
    before = Path(one.path).read_bytes()
    monkeypatch.chdir(tmp_path)
    same = bind(first)
    assert same.build["run_id"] == one.build["run_id"]
    assert Path(one.path).read_bytes() == before


def test_repo_mismatch_cannot_be_reconciled(git_repo, tmp_path):
    ledger = bind(git_repo)
    original = Path(ledger.path).read_bytes()
    other = init_repo(tmp_path / "other")
    for options in ({}, {"reconcile": True}, {"new_build": True}):
        with pytest.raises(StateError, match="Repository identity mismatch"):
            bind(other, ledger=ledger, **options)
    assert Path(ledger.path).read_bytes() == original


def test_copied_ledger_cannot_create_a_second_writer_identity(git_repo, tmp_path):
    ledger = bind(git_repo)
    copy = tmp_path / "copy.json"
    copy.write_bytes(Path(ledger.path).read_bytes())
    with pytest.raises(StateError, match="ledger path identity mismatch"):
        Ledger.load(str(copy))


@pytest.mark.parametrize("data", [b"{broken", b"[]", b'{"schema_version":99}',
                                  b'{"A":{"status":"fictional"}}',
                                  b'{"schema_version":2,"build":{},"entries":{}}'])
def test_corrupt_or_unsupported_state_preserved(tmp_path, data):
    path = tmp_path / "state.json"
    path.write_bytes(data)
    with pytest.raises(StateError):
        Ledger.load(str(path))
    assert path.read_bytes() == data


def test_unreadable_state_is_not_a_cache_miss(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    original = Path.read_bytes
    def denied(p):
        if p == path:
            raise PermissionError("injected access denial")
        return original(p)
    monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(StateError, match="Cannot read ledger"):
        Ledger.load(str(path))


def test_legacy_migration_backup_reachability_and_idempotence(git_repo):
    path = Path(resolve_ledger(git_repo))
    rc, base = real_git_runner(["git", "rev-parse", "HEAD"], git_repo)
    assert rc == 0
    original = json.dumps({"A": {"status": "done", "commit": base.strip()},
                           "B": {"status": "done", "commit": "missing"}}).encode()
    path.write_bytes(original)
    with pytest.raises(StateError, match="migrate-ledger"):
        bind(git_repo, [task(), task("B")])
    assert path.read_bytes() == original
    migrated = bind(git_repo, [task(), task("B")], migrate=True)
    assert Path(migrated.build["backup"]).read_bytes() == original
    assert migrated.build["integrated_sha"] is None
    assert migrated.get("A").status == migrated.get("B").status == "needs_repair"
    assert migrated.get("A").history[0]["reachable_commit"] == base.strip()
    assert migrated.get("B").history[0]["reachable_commit"] is None
    before = path.read_bytes()
    again = bind(git_repo, [task(), task("B")], migrate=True)
    assert path.read_bytes() == before and again.build["run_id"] == migrated.build["run_id"]
    reconciled = bind(git_repo, [task(), task("B")], reconcile=True)
    assert reconciled.get("A").status == reconciled.get("B").status == "pending"


def test_unbound_schema_two_cannot_bypass_migration(git_repo):
    ledger = Ledger(resolve_ledger(git_repo))
    ledger.set("A", status="done")
    ledger.save()
    with pytest.raises(StateError, match="migrate-ledger"):
        bind(git_repo)


def test_changed_plan_invalidates_downstream_preserves_independent_and_history(git_repo):
    original_tasks = [task(), task("B", ["A"]), task("C")]
    ledger = bind(git_repo, original_tasks)
    with ledger.writer():
        for sid in ["A", "B", "C"]:
            ledger.set(sid, status="done")
        ledger.save()
    old_run = ledger.build["run_id"]
    events = run_directory(git_repo, old_run) / "events.jsonl"
    events.write_text("historical events\n")
    before = Path(ledger.path).read_bytes()
    changed = [task(brief="changed"), task("B", ["A"]), task("C")]
    with pytest.raises(StateError, match="Plan/base mismatch"):
        bind(git_repo, changed)
    assert Path(ledger.path).read_bytes() == before
    updated = bind(git_repo, changed, reconcile=True)
    assert updated.build["run_id"] != old_run and updated.build["previous_run"] == old_run
    assert updated.build["invalidated"] == ["A", "B"]
    assert updated.get("A").status == updated.get("B").status == "pending"
    assert updated.get("C").status == "done"
    assert Path(updated.build["backup"]).read_bytes() == before
    assert events.read_text() == "historical events\n"
    pointer = json.loads((Path(git_repo) / ".cld/current-run.json").read_text())
    assert pointer["run_id"] == updated.build["run_id"]


def test_stale_loaded_writer_cannot_overwrite_newer_state(git_repo):
    first = bind(git_repo)
    stale = Ledger.load(first.path)
    first.set("A", status="failed")
    first.save()
    stale.set("A", status="done")
    with pytest.raises(StateError, match="changed since load"):
        stale.save()
    assert Ledger.load(first.path).get("A").status == "failed"


def test_interrupted_migration_replace_preserves_original_and_backup(git_repo, monkeypatch):
    path = Path(resolve_ledger(git_repo))
    original = b'{"A":{"status":"failed","attempts":1}}'
    path.write_bytes(original)
    real_replace = ledger_module.os.replace
    def fail(source, destination):
        if Path(destination) == path:
            raise OSError("injected replacement failure")
        return real_replace(source, destination)
    monkeypatch.setattr(ledger_module.os, "replace", fail)
    with pytest.raises(OSError, match="replacement failure"):
        bind(git_repo, migrate=True)
    assert path.read_bytes() == original
    assert any(p.read_bytes() == original for p in path.parent.glob(path.name + ".legacy-*.bak"))
    monkeypatch.setattr(ledger_module.os, "replace", real_replace)
    assert bind(git_repo, migrate=True).get("A").attempts == 1


def test_reader_does_not_lock_and_process_death_releases_writer(git_repo):
    ledger = bind(git_repo)
    code = '''
import os, sys
from cld.ledger import Ledger
ledger = Ledger(sys.argv[1])
with ledger.writer(refresh=True):
    print("owned", flush=True)
    sys.stdin.readline()
    os._exit(17)
'''
    child = subprocess.Popen([sys.executable, "-c", code, ledger.path], env=child_env(),
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "owned"
        assert Ledger.load(ledger.path).build["run_id"] == ledger.build["run_id"]
        with pytest.raises(OwnerBusy):
            with Ledger(ledger.path).writer(refresh=True):
                pytest.fail("second active writer")
    finally:
        child.communicate("exit\n", timeout=20)
    assert child.returncode == 17
    with ledger.writer(refresh=True):
        ledger.set("A", status="failed")
        ledger.save()
    assert Ledger.load(ledger.path).get("A").status == "failed"


def test_new_build_does_not_reuse_prior_acceptance_and_preserves_refs(delivery_repo):
    from tests.integration.test_review_regressions import run, task as delivery_task, checked_git
    from tests.integration.test_collection_recovery import Writer
    ex = Writer()
    first = run(delivery_repo, executor=ex)
    first_path = Path(first.details["A"].recovery_path)
    first_bytes = (first_path / "outcome.json").read_bytes()
    old = Ledger.load(resolve_ledger(delivery_repo))
    fresh = bind(delivery_repo, [delivery_task()], new_build=True)
    assert fresh.build["run_id"] != old.build["run_id"]
    second = run(delivery_repo, executor=ex)
    assert first.completed == second.completed == ["A"] and len(ex.calls) == 2
    assert first_path != Path(second.details["A"].recovery_path)
    assert (first_path / "outcome.json").read_bytes() == first_bytes
    ref = old.get("A").collection["ref"]
    assert checked_git(["rev-parse", ref], delivery_repo).strip() == first.details["A"].commit


def test_verified_legacy_journal_migrates_without_claiming_integration(delivery_repo):
    from dataclasses import asdict
    from tests.integration.test_review_regressions import run, task as delivery_task
    result = run(delivery_repo)
    current = Ledger.load(resolve_ledger(delivery_repo))
    record_path = Path(result.details["A"].recovery_path) / "outcome.json"
    record = json.loads(record_path.read_bytes())
    legacy_dir = delivery_repo / ".cld/A" / record["session_id"]
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "outcome.json").write_bytes(record_path.read_bytes())
    entry = asdict(current.get("A"))
    entry.pop("slice_id")
    Path(current.path).write_text(json.dumps({"A": entry}), encoding="utf-8")
    migrated = bind(delivery_repo, [delivery_task()], migrate=True)
    assert migrated.is_done("A") and migrated.build["integrated_sha"] is None
    assert migrated.get("A").history[-1]["verified_journal"] == str(legacy_dir)


def test_telemetry_appends_within_run_and_preserves_previous_runs(git_repo):
    import skill.scripts.run_delivery as rd
    from cld import telemetry
    first = bind(git_repo)
    try:
        with first.writer():
            old_path = Path(rd._install_telemetry(git_repo, first, "plan.md", "fake"))
            telemetry.emit("sentinel")
            telemetry.set_sink(None)
            rd._install_telemetry(git_repo, first, "plan.md", "fake")
            telemetry.set_sink(None)
        records = [json.loads(line) for line in old_path.read_text().splitlines()]
        assert [r["type"] for r in records] == ["run_start", "sentinel"]
        before = old_path.read_bytes()
        second = bind(git_repo, new_build=True)
        with second.writer():
            new_path = Path(rd._install_telemetry(git_repo, second, "plan.md", "fake"))
        telemetry.set_sink(None)
        assert new_path != old_path and old_path.read_bytes() == before
        assert json.loads(new_path.read_text())["run_id"] == second.build["run_id"]
    finally:
        telemetry.set_sink(None)
        telemetry.set_run_id(None)


def test_cli_default_paths_and_corruption_block_before_provider(git_repo, tmp_path, monkeypatch, capsys):
    import skill.scripts.run_delivery as rd
    plan = tmp_path / "plan.md"
    plan.write_text("## SLICE: A\nbrief: implement\nfiles: code.py\nacceptance_test_path: test_code.py\ndeps:\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(rd, "_preflight_executor", lambda *a: pytest.fail("provider preflight not allowed"))
    assert rd.main([str(plan), "--repo", git_repo, "--new-build"]) == 0
    path = Path(resolve_ledger(git_repo))
    assert path.is_file() and not (tmp_path / ".cld-ledger.json").exists()
    events = run_directory(git_repo, Ledger.load(str(path)).build["run_id"]) / "events.jsonl"
    events.write_text("preserved\n")
    path.write_bytes(b"{corrupt")
    assert rd.main([str(plan), "--repo", git_repo]) == 5
    assert path.read_bytes() == b"{corrupt" and events.read_text() == "preserved\n"
    assert str(path) in capsys.readouterr().err
