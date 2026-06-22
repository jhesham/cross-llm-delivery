import dataclasses
import os

try:  # deepeval is an OPTIONAL dependency — behavioral judging is off without it
    from deepeval.metrics import GEval
    from deepeval.models import AnthropicModel
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    _DEEPEVAL_IMPORT_ERROR = None
except ImportError as _e:  # pragma: no cover - exercised by the deps-blocked subprocess test
    GEval = AnthropicModel = LLMTestCase = LLMTestCaseParams = None
    _DEEPEVAL_IMPORT_ERROR = _e


def _require_deepeval() -> None:
    if GEval is None:
        raise ImportError(
            "behavioral (G-Eval) judging requires the optional 'deepeval' package "
            "(pip install deepeval). It is off by default; the deterministic judge "
            "needs nothing extra."
        ) from _DEEPEVAL_IMPORT_ERROR


@dataclasses.dataclass
class BehavioralResult:
    score: float
    passed: bool
    reason: str = ""


def make_compliance_metric(*, judge_model="claude-sonnet-4-6", threshold=0.8):
    """Build the code-compliance G-Eval metric judged by Claude (no OpenAI).

    `AnthropicModel` requires an API key at construction time. When ANTHROPIC_API_KEY
    is absent (offline tests that inject a fake metric and never call the judge), we
    pass a scoped placeholder so the object constructs — it is never used unless
    `.measure()` actually runs, which only happens with a real key present. This keeps
    the workaround local to the factory instead of a module-import side effect.
    """
    _require_deepeval()
    api_key = os.environ.get("ANTHROPIC_API_KEY") or "offline-placeholder"
    return GEval(
        name="Architectural Compliance",
        criteria=(
            "Assess whether the generated code satisfies every function, constraint, "
            "and error-handling requirement in the spec. Penalise missing functions "
            "or ignored constraints."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=AnthropicModel(model=judge_model, temperature=0.0, api_key=api_key),
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
