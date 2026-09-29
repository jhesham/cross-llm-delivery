from pathlib import Path
import pytest

from cld.integration import integrate
from cld.ledger import Ledger
from cld.repair import verify_repair
from cld.test_run import TestRun
from tests.integration.harness import FileCreatingExecutor, real_git_runner
from tests.integration.test_integration_lifecycle import repo, task, dispatch, merge
from tests.integration.test_review_regressions import acceptance, checked_git

pytestmark = pytest.mark.integration


def failed(repo):
    tasks = [task()]
    ledger, result = dispatch(repo, tasks, executor=FileCreatingExecutor(contents={"a.py": "VALUE = -1\n"}))
    assert result.failed == ["A"]
    return tasks, ledger


def repair(repo, tasks, ledger):
    return verify_repair(tasks, ledger, "A", repo_dir=str(repo), git_runner=real_git_runner, test_runner=acceptance)


def test_failed_repair_stays_repair_then_verified_repair_requires_integration(repo):
    tasks, ledger = failed(repo)
    original = ledger.get("A").worktree_path
    rejected = repair(repo, tasks, ledger)
    assert not rejected.passed and ledger.get("A").status == "needs_repair"
    assert Path(original).is_dir()
    (Path(ledger.get("A").worktree_path) / "a.py").write_text("VALUE = 1\n")
    accepted = repair(repo, tasks, ledger)
    assert accepted.passed and ledger.get("A").status == "done"
    assert ledger.get("A").intervened and ledger.build["integrated_sha"] is None
    checked_git(["cat-file", "-e", f"{accepted.commit}:a.py"], repo)
    assert merge(repo, tasks, Ledger.load(ledger.path)).passed
    assert (repo / "a.py").read_text() == "VALUE = 0\n"


def test_repair_protected_test_edit_rejected(repo):
    from cld.executors._capture import CaptureError
    tasks, ledger = failed(repo)
    path = Path(ledger.get("A").worktree_path)
    (path / "test_slice.py").write_text("def test_fake(): assert True\n")
    with pytest.raises(CaptureError, match="Protected"):
        repair(repo, tasks, ledger)
    assert ledger.get("A").status == "failed" and not ledger.get("A").intervened


def test_repair_save_failure_preserves_verified_collection(repo, monkeypatch):
    tasks, ledger = failed(repo)
    (Path(ledger.get("A").worktree_path) / "a.py").write_text("VALUE = 1\n")
    original = ledger.save
    def fail():
        if ledger.get("A").status == "done":
            raise OSError("repair publication failed")
        original()
    monkeypatch.setattr(ledger, "save", fail)
    with pytest.raises(OSError, match="publication failed"):
        repair(repo, tasks, ledger)
    assert ledger.get("A").status == "failed"
    # Ordinary resume reconciles the checked collection without redispatch.
    class Never:
        def run(self, *args, **kwargs):
            pytest.fail("verified repair must be recoverable without redispatch")
    resumed, result = dispatch(repo, tasks, Ledger.load(ledger.path), executor=Never())
    assert result.completed == ["A"] and resumed.get("A").intervened
    assert merge(repo, tasks, resumed).passed


def test_structured_rc_zero_without_summary_passes_real_delivery_and_integration(repo):
    def quiet(where, selector):
        result = acceptance(where, selector)
        from cld.test_run import legacy_result
        actual = legacy_result(result)
        return TestRun(actual.returncode, "... [100%]" if actual.returncode == 0 else actual.output)
    tasks = [task()]
    ledger, result = dispatch(repo, tasks, test_runner=quiet)
    assert result.completed == ["A"]
    assert merge(repo, tasks, ledger, test_runner=quiet).passed


def cli_plan(repo):
    text = "## SLICE: A\nbrief: Implement\nfiles: a.py\nacceptance_test_path: test_slice.py\ndeps:\n"
    path = repo / "plan.md"
    path.write_text(text)
    tasks = [task()]
    ledger = Ledger(str(repo / ".cld-ledger.json"))
    with ledger.writer():
        ledger.bind(str(repo), tasks, real_git_runner, plan_path=path, plan_text=text)
    return path, tasks, ledger


def test_cli_repair_and_integration_codes_without_provider(repo, monkeypatch, capsys):
    import skill.scripts.run_delivery as rd
    path, tasks, ledger = cli_plan(repo)
    _, result = dispatch(repo, tasks, ledger, executor=FileCreatingExecutor(contents={"a.py": "VALUE = -1\n"}))
    assert result.failed == ["A"]
    def never(*args, **kwargs):
        pytest.fail("repair/integration/no-op must not touch provider")
    monkeypatch.setattr(rd, "prompt_for_executor", never)
    monkeypatch.setattr(rd, "_preflight_executor", never)
    monkeypatch.setattr(rd, "build_executor_factory", never)
    monkeypatch.setattr(rd, "pytest_test_runner", acceptance)
    args = [str(path), "--repo", str(repo)]
    assert rd.main(args + ["--mark-repaired", "A"]) == 4
    fresh = Ledger.load(ledger.path)
    (Path(fresh.get("A").worktree_path) / "a.py").write_text("VALUE = 1\n")
    assert rd.main(args + ["--mark-repaired", "A"]) == 6
    assert rd.main(args + ["--step"]) == 6
    assert rd.main(args + ["--integrate", "--integration-tests", "test_integration.py"]) == 3
    assert rd.main(args + ["--step"]) == 3
    assert "gate: passed" in rd._render_build_status(str(repo), Ledger.load(ledger.path))


@pytest.mark.parametrize("step", [False, True])
def test_cli_needs_repair_is_four_in_whole_and_step_mode(repo, monkeypatch, capsys, step):
    import skill.scripts.run_delivery as rd
    from cld.orchestrator import PlanResult
    path, tasks, ledger = cli_plan(repo)
    monkeypatch.setattr(rd, "_preflight_executor", lambda *_: None)
    monkeypatch.setattr(rd, "build_executor_factory", lambda: None)
    monkeypatch.setattr(rd, "prepare_dispatch", lambda *args: (None, None))
    monkeypatch.setattr(rd, "build_rung_planner", lambda *_: None)
    def result(slices, led, **kwargs):
        led.set("A", status="needs_repair")
        led.save()
        return PlanResult(needs_repair=["A"], build_complete=False)
    monkeypatch.setattr(rd, "run_plan_parallel", result)
    args = [str(path), "--repo", str(repo), "--executor", "opencode:fake"]
    assert rd.main(args + (["--step"] if step else [])) == 4
    assert "repair" in capsys.readouterr().out.lower()
    assert "gate: needs_repair" in rd._render_build_status(str(repo), Ledger.load(ledger.path))


def test_existing_repair_state_blocks_automatic_provider_retry(repo, monkeypatch):
    import skill.scripts.run_delivery as rd
    path, tasks, ledger = cli_plan(repo)
    with ledger.writer():
        ledger.set("A", status="needs_repair")
        ledger.save()
    def never(*args, **kwargs):
        pytest.fail("needs_repair must not trigger provider setup or dispatch")
    monkeypatch.setattr(rd, "_preflight_executor", never)
    monkeypatch.setattr(rd, "build_executor_factory", never)
    monkeypatch.setattr(rd, "build_rung_planner", never)
    assert rd.main([str(path), "--repo", str(repo), "--step"]) == 4


def test_subset_cannot_change_validated_task_contract(repo):
    from dataclasses import replace
    from cld.ledger import StateError
    tasks = [task()]
    with pytest.raises(StateError, match="differs from the validated complete plan"):
        dispatch(repo, tasks, selected=[replace(tasks[0], files=["README.md"])])


def test_integration_failure_has_repair_gate_and_durable_status(repo, monkeypatch):
    import skill.scripts.run_delivery as rd
    path, tasks, ledger = cli_plan(repo)
    dispatch(repo, tasks, ledger)
    monkeypatch.setattr(rd, "pytest_test_runner", acceptance)
    args = [str(path), "--repo", str(repo)]
    assert rd.main(args + ["--integrate", "--integration-tests", "test_red.py"]) == 4
    fresh = Ledger.load(ledger.path)
    assert fresh.build["integration_failure"]["evidence"]
    assert "gate: needs_repair" in rd._render_build_status(str(repo), fresh)
    monkeypatch.setattr(rd, "_preflight_executor", lambda *_: pytest.fail("repair block must precede provider"))
    assert rd.main(args + ["--step"]) == 4
