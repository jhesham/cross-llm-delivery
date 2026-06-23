"""Acceptance tests for the Judge module (T3.3 contract).

Authored by Claude (architect) BEFORE implementation. The executor must make
these pass without editing this file. The Judge runs acceptance tests via an
INJECTED runner (no hardcoded subprocess), parses results, and enforces the
diff rule (no edits outside the allowed file set).
"""

from cld.judge import JudgeResult, check_diff_rule, judge, parse_pytest_output


# ---- JudgeResult dataclass ----

def test_judgeresult_defaults():
    r = JudgeResult(passed=True, tests_passed=3, tests_failed=0)
    assert r.failing_tests == []
    assert r.disallowed_edits == []
    assert r.raw_output == ""


def test_judgeresult_defaults_not_shared():
    a = JudgeResult(passed=True, tests_passed=1, tests_failed=0)
    b = JudgeResult(passed=True, tests_passed=1, tests_failed=0)
    a.failing_tests.append("x")
    a.disallowed_edits.append("y")
    assert b.failing_tests == []
    assert b.disallowed_edits == []


# ---- parse_pytest_output ----

def test_parse_passed_only():
    passed, failed, failing = parse_pytest_output("3 passed in 0.10s")
    assert (passed, failed, failing) == (3, 0, [])


def test_parse_passed_and_failed_with_node_ids():
    out = (
        "FAILED tests/test_a.py::test_one\n"
        "FAILED tests/test_a.py::test_two\n"
        "2 failed, 5 passed in 0.42s"
    )
    passed, failed, failing = parse_pytest_output(out)
    assert passed == 5
    assert failed == 2
    assert failing == ["tests/test_a.py::test_one", "tests/test_a.py::test_two"]


def test_parse_failed_only():
    out = "FAILED tests/test_x.py::test_z\n1 failed in 0.05s"
    passed, failed, failing = parse_pytest_output(out)
    assert passed == 0
    assert failed == 1
    assert failing == ["tests/test_x.py::test_z"]


def test_parse_unparseable_surfaces_reason_safely():
    # A non-pass with no recognizable summary must NOT silently return empty (that hid
    # the concurrency false-negative as "(no test id)"). It returns 0/0 with a concrete,
    # surfaced reason instead — never raises.
    p, f, empty = parse_pytest_output("")
    assert (p, f) == (0, 0) and any("EMPTY JUDGE OUTPUT" in x for x in empty)
    p, f, garbage = parse_pytest_output("garbage with no summary")
    assert (p, f) == (0, 0) and any("INDETERMINATE" in x for x in garbage)


def test_parse_tolerates_extra_whitespace():
    passed, failed, _ = parse_pytest_output("   7 passed,   1 failed   in 1.2s  ")
    assert (passed, failed) == (7, 1)


# ---- check_diff_rule ----

def test_diff_rule_within_bounds():
    assert check_diff_rule(["a.py"], ["a.py", "b.py"]) == []


def test_diff_rule_flags_and_sorts_disallowed():
    out = check_diff_rule(["z.py", "a.py", "ok.py"], ["ok.py"])
    assert out == ["a.py", "z.py"]


# ---- judge() orchestration ----

def test_judge_clean_pass():
    res = judge(
        files_changed=["src/cld/judge.py"],
        allowed=["src/cld/judge.py"],
        run_tests=lambda: "4 passed in 0.2s",
    )
    assert res.passed is True
    assert res.tests_passed == 4
    assert res.tests_failed == 0
    assert res.failing_tests == []
    assert res.disallowed_edits == []
    assert res.raw_output == "4 passed in 0.2s"


def test_judge_fails_on_test_failure():
    res = judge(
        files_changed=["src/cld/judge.py"],
        allowed=["src/cld/judge.py"],
        run_tests=lambda: "FAILED tests/t.py::test_a\n1 failed, 2 passed in 0.1s",
    )
    assert res.passed is False
    assert res.tests_failed == 1
    assert res.failing_tests == ["tests/t.py::test_a"]


def test_judge_fails_on_disallowed_edit():
    res = judge(
        files_changed=["src/cld/judge.py", "tests/test_judge.py"],
        allowed=["src/cld/judge.py"],
        run_tests=lambda: "3 passed in 0.1s",
    )
    assert res.passed is False
    assert res.disallowed_edits == ["tests/test_judge.py"]


def test_judge_zero_collected_is_not_a_pass():
    res = judge(
        files_changed=["src/cld/judge.py"],
        allowed=["src/cld/judge.py"],
        run_tests=lambda: "no tests ran in 0.01s",
    )
    assert res.passed is False
