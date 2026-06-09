"""T5.6a: behavioral G-Eval wrapper (Claude judge, no OpenAI).

Runs fully offline: evaluate_compliance accepts an injected fake metric, so no
live LLM call and no API key are needed. One test confirms the real metric
constructs lazily (no network on construction).
"""

from cld.behavioral import (
    BehavioralResult,
    evaluate_compliance,
    make_compliance_metric,
)


class FakeMetric:
    """Duck-typed stand-in for a deepeval GEval metric."""

    def __init__(self, score, threshold=0.8, reason="ok"):
        self._score = score
        self.threshold = threshold
        self.reason = reason
        self.measured_with = None

    def measure(self, test_case):
        self.measured_with = test_case
        self.score = self._score


def test_evaluate_compliance_pass_with_injected_metric():
    m = FakeMetric(score=0.9, threshold=0.8, reason="all good")
    res = evaluate_compliance("the spec", "the code", metric=m)
    assert isinstance(res, BehavioralResult)
    assert res.score == 0.9
    assert res.passed is True
    assert res.reason == "all good"


def test_evaluate_compliance_fail_below_threshold():
    m = FakeMetric(score=0.5, threshold=0.8, reason="missing error handling")
    res = evaluate_compliance("spec", "code", metric=m)
    assert res.passed is False
    assert res.reason == "missing error handling"


def test_evaluate_compliance_builds_testcase_from_spec_and_code():
    m = FakeMetric(score=1.0)
    evaluate_compliance("SPEC-TEXT", "CODE-TEXT", metric=m)
    tc = m.measured_with
    # spec -> input, code -> actual_output
    assert tc.input == "SPEC-TEXT"
    assert tc.actual_output == "CODE-TEXT"


def test_make_compliance_metric_constructs_offline():
    # Constructing the real metric must NOT make a network call (lazy judge).
    metric = make_compliance_metric(threshold=0.75)
    assert metric.threshold == 0.75
    # name carries our rubric label
    assert "Compliance" in getattr(metric, "name", "")
