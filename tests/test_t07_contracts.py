from dataclasses import replace
import pytest

from cld.plan.slice import load_slices, PlanError
from cld.test_run import TestRun, legacy_result
from cld.judge import judge
from cld.integration_gate import integration_gate
from cld.orchestrator import PlanResult
from cld.summary import classify_gate, summarize_layer

PLAN = "## SLICE: A\nbrief: implement a\nfiles: src/a.py\nacceptance_test_path: tests/test_a.py\ndeps:\n"


@pytest.mark.parametrize("text, reason", [
    (PLAN + PLAN, "duplicate"),
    (PLAN.replace("SLICE: A", "SLICE:"), "empty ID"),
    (PLAN + "## SUBSLICE: child\nbrief: no\n", "SUBSLICE"),
    (PLAN.replace("deps:", "deps: missing"), "unknown dependencies"),
    (PLAN.replace("deps:", "deps: A"), "Cycle"),
    (PLAN + "complexity: huge\n", "complexity"),
    (PLAN.replace("acceptance_test_path: tests/test_a.py", "acceptance_test_path:"), "selector"),
    (PLAN.replace("src/a.py", "../a.py"), "Unsafe"),
    (PLAN.replace("src/a.py", "C:/a.py"), "Unsafe"),
    (PLAN.replace("src/a.py", "src\\a.py"), "Unsafe"),
    (PLAN.replace("brief: implement a", "brief: |\n  more lines"), "multiline"),
    (PLAN.replace("brief: implement a", "brief: one\n  silently lost"), "multiline"),
    (PLAN + "brief: duplicate\n", "repeated"),
    (PLAN + "unknown: value\n", "unknown"),
    (PLAN.replace("SLICE: A", "SLICE: integration"), "reserved"),
])
def test_invalid_plan_has_line_diagnostic(text, reason):
    with pytest.raises(PlanError, match="line [0-9]+:.*" + reason):
        load_slices(text)


def test_spaces_and_quoted_selector_round_trip():
    from cld.plan.slice import slices_to_markdown
    text = PLAN.replace("src/a.py", "src folder/a.py").replace("tests/test_a.py", '"tests folder/test_a.py" -k "case and not slow"')
    assert load_slices(slices_to_markdown(load_slices(text))) == load_slices(text)


@pytest.mark.parametrize("result, passed", [
    (TestRun(0, "... [100%]"), True),
    (TestRun(1, "1 passed, 1 error"), False),
    (TestRun(2, "1 passed"), False),
    (TestRun(-9, "1 passed"), False),
    (TestRun(5, "no tests ran"), False),
    (TestRun(0, "", tests_run=0), False),
    (TestRun(0, "1 passed", timed_out=True), False),
    (TestRun(0, "1 passed", error="launch_error"), False),
    (TestRun(1, "__CLD_PYTEST_RC__=0\n1 passed"), False),
    ("1 passed", False),
    (legacy_result("1 passed", allow_prose=True), True),
])
def test_slice_and_integration_use_same_rc_authority(result, passed):
    assert judge([], [], run_tests=lambda: result).passed is passed
    assert integration_gate(["A"], run_full_suite=lambda: result).passed is passed


def test_candidate_identity_mismatch_cannot_pass():
    from cld.test_run import test_result
    verdict = test_result(TestRun(0, candidate_id="wrong"), candidate_id="actual-tree")
    assert not verdict.passed and verdict.error == "candidate_identity_mismatch"


@pytest.mark.parametrize("result, more, gate", [
    (PlanResult(build_complete=False), True, 0),
    (PlanResult(failed=["A"]), False, 2),
    (PlanResult(deferred=["A"]), False, 2),
    (PlanResult(build_complete=True), False, 3),
    (PlanResult(needs_repair=["A"]), False, 4),
    (PlanResult(integration_error="conflict"), False, 4),
    (PlanResult(integration_required=["A"]), False, 6),
    (PlanResult(blocked=["A"], deferred=["A"]), False, 5),
])
def test_gate_table_and_summary_never_hide_failure(result, more, gate):
    assert classify_gate(result, more_layers=more) == gate
    summary = summarize_layer(result, layer_index=0, total_layers=1, next_layer=[])
    if gate in (2, 4, 6):
        assert "build complete" not in summary


def test_dry_run_rejects_invalid_plan_without_provider_or_state(tmp_path, monkeypatch, capsys):
    import skill.scripts.run_delivery as rd
    def never(*args, **kwargs):
        pytest.fail("dry-run touched provider or Git")
    monkeypatch.setattr(rd, "prompt_for_executor", never)
    monkeypatch.setattr(rd, "_preflight_executor", never)
    monkeypatch.setattr(rd, "_preflight_git", never)
    path = tmp_path / "plan.md"
    path.write_text(PLAN.replace("deps:", "deps: missing"))
    assert rd.main([str(path), "--repo", str(tmp_path), "--dry-run"]) == 5
    assert "line 1" in capsys.readouterr().err
    assert not (tmp_path / ".cld-ledger.json").exists()
    path.write_text(PLAN)
    assert rd.main([str(path), "--repo", str(tmp_path), "--dry-run"]) == 0


def test_validation_probe_cannot_promote_nonzero_rc(monkeypatch, tmp_path):
    import cld.validate as validation
    from cld.executors.base import ExecutorResult
    class Executor:
        def run(self, *args):
            return ExecutorResult(True, "", ["calc.py"])
    monkeypatch.setattr(validation, "_init_repo", lambda *_: None)
    monkeypatch.setattr(validation, "_pytest", lambda *_: TestRun(1, "1 passed, 1 error"))
    result = validation.validate_model("fake", executor=Executor(), git_runner=None, base_dir=str(tmp_path))
    assert not result.passed and result.status == "revalidate"


def test_markdown_fenced_plan_is_supported():
    assert load_slices("```markdown\n" + PLAN + "```\n") == load_slices(PLAN)


def test_timeout_preserves_partial_output():
    import subprocess
    from cld.test_run import process_failure
    result = process_failure(subprocess.TimeoutExpired("pytest", 1, output=b"partial output", stderr=b"diagnostic"))
    assert result.timed_out and not result.passed and result.error == "timeout"
    assert "partial output" in result.output and "diagnostic" in result.output


@pytest.mark.parametrize("selector", ['"tests\\test_a.py"', 'tests/test_a.py --maxfail=1', '"unclosed'])
def test_selector_rejects_platform_escapes_and_unsupported_flags(selector):
    from cld.candidate import acceptance_args
    from cld.executors._capture import CaptureError
    with pytest.raises(CaptureError):
        acceptance_args(selector)
