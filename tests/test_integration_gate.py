"""T5.3: integration gate — full-suite pass on the merged tree, else mark rework."""

from cld.integration_gate import GateResult, integration_gate


def test_gate_passes_on_green_merged_tree():
    res = integration_gate(["A", "B"], run_full_suite=lambda: "12 passed in 0.5s")
    assert isinstance(res, GateResult)
    assert res.passed is True
    assert res.tests_passed == 12
    assert res.tests_failed == 0
    assert res.rework_batch == []
    assert res.batch == ["A", "B"]


def test_gate_fails_and_marks_rework_on_red():
    out = "FAILED tests/test_x.py::test_z\n11 passed, 1 failed in 0.5s"
    res = integration_gate(["A", "B"], run_full_suite=lambda: out)
    assert res.passed is False
    assert res.tests_failed == 1
    assert res.failing_tests == ["tests/test_x.py::test_z"]
    assert res.rework_batch == ["A", "B"]  # whole batch sent back


def test_gate_zero_collected_is_failure():
    res = integration_gate(["A"], run_full_suite=lambda: "no tests ran in 0.01s")
    assert res.passed is False
    assert res.rework_batch == ["A"]


def test_gate_captures_raw_output():
    res = integration_gate([], run_full_suite=lambda: "3 passed in 0.1s")
    assert res.raw_output == "3 passed in 0.1s"


def test_gate_reuses_judge_parser():
    # both-counts line parsed correctly (delegates to cld.judge.parse_pytest_output)
    res = integration_gate(["X"], run_full_suite=lambda: "5 passed, 2 failed in 0.3s")
    assert (res.tests_passed, res.tests_failed) == (5, 2)
    assert res.passed is False
