"""T06: real commits and offline pytest, including publication fault boundaries."""
import json
from pathlib import Path

import pytest

from cld.executors.base import SliceTask
from cld.integration import integrate, verified_base
from cld.judge import judge
from cld.ledger import Ledger, StateError
from cld.orchestrator import run_plan_parallel
from tests.integration.harness import FileCreatingExecutor, real_git_runner
from tests.integration.test_review_regressions import acceptance, checked_git

pytestmark = pytest.mark.integration


@pytest.fixture
def repo(git_repo):
    root = Path(git_repo)
    for name, body in {
        "a.py": "VALUE = 0\n", "b.py": "VALUE = 0\n",
        "test_slice.py": "import a, b\ndef test_slice(): assert a.VALUE >= 0 and b.VALUE >= 0\n",
        "test_integration.py": "import a, b\ndef test_combined(): assert a.VALUE + b.VALUE >= 0\n",
        "test_regression.py": "import a, b\ndef test_combined(): assert a.VALUE + b.VALUE <= 1\n",
        "test_red.py": "def test_red(): assert False\n",
    }.items():
        (root / name).write_text(body, encoding="utf-8")
    checked_git(["add", "."], root)
    checked_git(["commit", "-qm", "integration inputs"], root)
    return root


def task(sid="A", file="a.py", deps=()):
    return SliceTask(sid, "Implement", [file], "test_slice.py", deps=list(deps))


def dispatch(repo, tasks, ledger=None, *, selected=None, **kwargs):
    ledger = ledger or Ledger(str(repo / ".cld-ledger.json"))
    options = dict(executor=FileCreatingExecutor(contents={"a.py": "VALUE = 1\n", "b.py": "VALUE = 1\n"}),
                   judge_fn=judge, max_workers=1, max_retries=0, repo_dir=str(repo),
                   git_runner=real_git_runner, test_runner=acceptance, plan_slices=tasks)
    options.update(kwargs)
    result = run_plan_parallel(selected or tasks, ledger, **options)
    return ledger, result


def merge(repo, tasks, ledger, **kwargs):
    options = dict(repo_dir=str(repo), git_runner=real_git_runner, test_runner=acceptance,
                   selector="test_integration.py")
    options.update(kwargs)
    return integrate(tasks, ledger, **options)


def test_acceptance_is_not_integration_and_repeat_is_noop(repo):
    tasks = [task()]
    head = checked_git(["rev-parse", "HEAD"], repo)
    ledger, result = dispatch(repo, tasks)
    assert result.integration_required == ["A"]
    assert ledger.build["integrated_sha"] is None
    first = merge(repo, tasks, ledger)
    assert first.passed and first.integrated == ("A",)
    assert ledger.get("A").status == "integrated"
    assert verified_base(Ledger.load(ledger.path), real_git_runner) == first.commit
    again = merge(repo, tasks, ledger, test_runner=lambda *_: pytest.fail("no repeat tests"))
    assert again.passed and again.commit == first.commit and not again.integrated
    assert checked_git(["rev-parse", "HEAD"], repo) == head
    assert (repo / "a.py").read_text() == "VALUE = 0\n"


@pytest.mark.parametrize("status", ["done", "failed", "deferred", "needs_repair", "in_progress", "pending"])
def test_unintegrated_dependency_never_dispatches(repo, status):
    tasks = [task(), task("B", "b.py", ["A"])]
    ledger = Ledger(str(repo / ".cld-ledger.json"))
    with ledger.writer():
        ledger.bind(str(repo), tasks, real_git_runner)
        ledger.set("A", status=status)
        ledger.save()
    class Never:
        def run(self, *args, **kwargs):
            pytest.fail("blocked dependent dispatched")
    _, result = dispatch(repo, tasks, ledger, selected=[tasks[1]], executor=Never())
    assert result.deferred == ["B"]
    assert f"Dependency A is {status}" in result.details["B"].failing_tests[0]


def test_whole_multilayer_requires_explicit_suite_before_dispatch(repo):
    with pytest.raises(StateError, match="Multi-layer"):
        dispatch(repo, [task(), task("B", "b.py", ["A"])])
    assert len(checked_git(["worktree", "list"], repo).splitlines()) == 1


def test_advancing_user_head_does_not_rebase_build_or_dependents(repo):
    tasks = [task(), task("B", "b.py", ["A"])]
    ledger, _ = dispatch(repo, tasks, selected=[tasks[0]])
    initial = ledger.build["initial_base"]
    first = merge(repo, tasks, ledger)
    (repo / "user.txt").write_text("unrelated user change\n")
    checked_git(["add", "user.txt"], repo)
    checked_git(["commit", "-qm", "user advanced"], repo)
    head = checked_git(["rev-parse", "HEAD"], repo)
    with ledger.writer():
        ledger.bind(str(repo), tasks, real_git_runner)
    assert ledger.build["initial_base"] == initial
    _, result = dispatch(repo, tasks, ledger, selected=[tasks[1]])
    assert result.completed == ["B"]
    assert ledger.get("B").collection["base"] == first.commit
    assert checked_git(["show", f"{ledger.get('B').commit}:a.py"], repo) == "VALUE = 1\n"
    assert "user.txt" not in checked_git(["ls-tree", "--name-only", ledger.get("B").commit], repo)
    assert merge(repo, tasks, ledger).passed
    assert checked_git(["rev-parse", "HEAD"], repo) == head


@pytest.mark.parametrize("selector, reason", [("test_regression.py", "layer regression"),
                                              ("test_red.py", "baseline failure persists")])
def test_failed_suite_preserves_candidate_without_advancing(repo, selector, reason):
    tasks = [task(), task("C", "b.py")]
    ledger, _ = dispatch(repo, tasks)
    gate = merge(repo, tasks, ledger, selector=selector)
    assert not gate.passed and reason in gate.error
    assert ledger.build["integrated_sha"] is None
    assert all(e.status == "done" for e in ledger.entries.values())
    record = json.loads((Path(gate.evidence) / "outcome.json").read_text())
    assert Path(record["worktree"]).is_dir() and record["candidate"]["tree"]
    assert (Path(gate.evidence) / "candidate.txt").exists()


def test_conflict_retained_then_manual_resolution_verified(repo):
    tasks = [task(), task("C")]
    ledger, _ = dispatch(repo, tasks, selected=[tasks[0]])
    dispatch(repo, tasks, ledger, selected=[tasks[1]],
             executor=FileCreatingExecutor(contents={"a.py": "VALUE = 2\n"}))
    gate = merge(repo, tasks, ledger)
    assert not gate.passed and "CONFLICT" in gate.error
    record = json.loads((Path(gate.evidence) / "outcome.json").read_text())
    wt = Path(record["worktree"])
    assert checked_git(["ls-files", "--unmerged"], wt).strip()
    assert ledger.build["integrated_sha"] is None
    (wt / "a.py").write_text("VALUE = 3\n")
    checked_git(["add", "a.py"], wt)
    checked_git(["commit", "-qm", "manual conflict resolution"], wt)
    manual = checked_git(["rev-parse", "HEAD"], wt).strip()
    good = merge(repo, tasks, ledger, manual_ref=manual)
    assert good.passed and good.commit == manual
    for entry in ledger.entries.values():
        checked_git(["merge-base", "--is-ancestor", entry.commit, manual], repo)


def test_manual_commit_missing_accepted_ancestry_rejected(repo):
    tasks = [task()]
    ledger, _ = dispatch(repo, tasks)
    gate = merge(repo, tasks, ledger, manual_ref="HEAD")
    assert not gate.passed and ledger.get("A").status == "done"


def test_restart_after_pass_before_ledger_save_reuses_commit(repo, monkeypatch):
    tasks = [task()]
    ledger, _ = dispatch(repo, tasks)
    original = ledger.save
    def fail_publish():
        if ledger.build.get("integrated_sha"):
            raise OSError("injected publication failure")
        original()
    monkeypatch.setattr(ledger, "save", fail_publish)
    with pytest.raises(OSError, match="publication failure"):
        merge(repo, tasks, ledger)
    assert ledger.get("A").status == "done" and ledger.build["integrated_sha"] is None
    root = repo / ".cld/runs" / ledger.build["run_id"] / "integration"
    passed = [json.loads(p.read_text()) for p in root.glob("*/outcome.json")]
    assert len(passed) == 1 and passed[0]["state"] == "passed"
    fresh = Ledger.load(ledger.path)
    gate = merge(repo, tasks, fresh)
    assert gate.passed and gate.commit == passed[0]["commit"]


@pytest.mark.parametrize("phase", ["merging", "candidate"])
def test_restart_between_merge_and_test_retains_interrupted_attempt(repo, monkeypatch, phase):
    tasks = [task()]
    ledger, _ = dispatch(repo, tasks)
    import cld.integration as module
    original = module.atomic_write
    def stop(path, raw):
        original(path, raw)
        if path.name == "outcome.json" and json.loads(raw).get("state") == phase:
            raise KeyboardInterrupt("injected process interruption")
    monkeypatch.setattr(module, "atomic_write", stop)
    with pytest.raises(KeyboardInterrupt):
        merge(repo, tasks, ledger)
    monkeypatch.setattr(module, "atomic_write", original)
    assert ledger.get("A").status == "done"
    assert merge(repo, tasks, Ledger.load(ledger.path)).passed
    records = list((repo / ".cld/runs" / ledger.build["run_id"] / "integration").glob("*/outcome.json"))
    assert len(records) == 2
    assert any(json.loads(p.read_text())["state"] == phase for p in records)


def test_forged_pass_prose_and_changed_suite_are_rejected(repo):
    tasks = [task()]
    ledger, _ = dispatch(repo, tasks)
    calls = []
    def error(where, selector):
        calls.append(where)
        return acceptance(where, selector) if len(calls) == 1 else "__CLD_PYTEST_RC__=1\n1 passed, 1 error"
    gate = merge(repo, tasks, ledger, test_runner=error)
    assert not gate.passed and ledger.build["integrated_sha"] is None
    with pytest.raises(StateError, match="suite changed"):
        merge(repo, tasks, ledger, selector="test_slice.py")


def test_deleted_integration_ref_blocks_dispatch(repo):
    tasks = [task(), task("B", "b.py", ["A"])]
    ledger, _ = dispatch(repo, tasks, selected=[tasks[0]])
    assert merge(repo, tasks, ledger).passed
    checked_git(["update-ref", "-d", ledger.build["integrated_ref"]], repo)
    with pytest.raises(StateError, match="Invalid integration evidence"):
        dispatch(repo, tasks, ledger, selected=[tasks[1]])


def test_reconcile_preserves_acceptance_but_requires_fresh_gate(repo):
    tasks = [task()]
    ledger, _ = dispatch(repo, tasks)
    assert merge(repo, tasks, ledger).passed
    previous = ledger.build["run_id"]
    with ledger.writer():
        ledger.bind(str(repo), tasks, real_git_runner, reconcile=True)
    assert ledger.build["run_id"] != previous and ledger.build["integrated_sha"] is None
    assert ledger.get("A").status == "done"
    assert merge(repo, tasks, ledger).passed


def test_cli_integrates_without_provider_and_reports_pending_work(repo, monkeypatch, capsys):
    import skill.scripts.run_delivery as rd
    tasks = [task()]
    text = "## SLICE: A\nbrief: Implement\nfiles: a.py\nacceptance_test_path: test_slice.py\ndeps:\n"
    plan = repo / "plan.md"
    plan.write_text(text, encoding="utf-8")
    ledger = Ledger(str(repo / ".cld-ledger.json"))
    with ledger.writer():
        ledger.bind(str(repo), tasks, real_git_runner, plan_path=plan, plan_text=text)
    dispatch(repo, tasks, ledger)
    def never(*args, **kwargs):
        pytest.fail("integration must not access a provider")
    monkeypatch.setattr(rd, "prompt_for_executor", never)
    monkeypatch.setattr(rd, "_preflight_executor", never)
    monkeypatch.setattr(rd, "build_executor_factory", never)
    monkeypatch.setattr(rd, "pytest_test_runner", acceptance)
    args = [str(plan), "--repo", str(repo), "--integrate"]
    assert rd.main(args) == 5
    assert "explicit suite" in capsys.readouterr().err
    assert rd.main(args + ["--integration-tests", "test_integration.py"]) == 3
    assert rd.main(args) == 3  # persisted selector; no tests or provider needed


def test_integration_suite_cannot_mutate_frozen_candidate(repo):
    tasks = [task()]
    ledger, _ = dispatch(repo, tasks)
    calls = []
    def mutate(where, selector):
        output = acceptance(where, selector)
        calls.append(where)
        if len(calls) == 2:
            (Path(where) / "a.py").write_text("VALUE = 99\n")
        return output
    gate = merge(repo, tasks, ledger, test_runner=mutate)
    assert not gate.passed and "mutated the frozen candidate" in gate.error
    assert ledger.build["integrated_sha"] is None


def test_integration_artifact_link_cannot_escape_run(repo, tmp_path):
    import os
    tasks = [task()]
    ledger, _ = dispatch(repo, tasks)
    external = tmp_path / "external"
    external.mkdir()
    root = repo / ".cld/runs" / ledger.build["run_id"] / "integration"
    try:
        os.symlink(external, root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory symlinks unavailable: {exc}")
    with pytest.raises(StateError, match="escapes the build run"):
        merge(repo, tasks, ledger)
    assert not list(external.iterdir())
