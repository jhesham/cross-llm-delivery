import dataclasses
import os
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase
from deepeval.test_case import LLMTestCaseParams
from deepeval.models import AnthropicModel

# Ensure AnthropicModel can be constructed offline without failing
os.environ.setdefault("ANTHROPIC_API_KEY", "mock-offline")

@dataclasses.dataclass
class BehavioralResult:
    score: float
    passed: bool
    reason: str = ""

def make_compliance_metric(*, judge_model="claude-sonnet-4-6", threshold=0.8) -> GEval:
    return GEval(
        name="Architectural Compliance",
        criteria="Assess whether the generated code satisfies every function, constraint, and error-handling requirement in the spec. Penalise missing functions or ignored constraints.",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=AnthropicModel(model=judge_model, temperature=0.0),
        threshold=threshold,
    )

def evaluate_compliance(spec, code, *, metric=None) -> BehavioralResult:
    if metric is None:
        metric = make_compliance_metric()
    
    test_case = LLMTestCase(input=spec, actual_output=code)
    metric.measure(test_case)
    
    return BehavioralResult(
        score=metric.score,
        passed=metric.score >= metric.threshold,
        reason=getattr(metric, "reason", "") or ""
    )
