from dataclasses import dataclass
from typing import Optional, List, Callable, Tuple, Dict

@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str
    cost_class: str
    capability_class: str
    headless_status: str
    rework_risk: str
    note: str
    last_validated: Optional[str] = None

MODEL_METADATA: Dict[str, ModelInfo] = {
    "gemini:gemini-3.1-pro-preview": ModelInfo(
        id="gemini:gemini-3.1-pro-preview",
        provider="gemini",
        cost_class="flat",
        capability_class="workhorse",
        headless_status="proven",
        rework_risk="low",
        note="our 14/14 grade-A workhorse; $0 flat-rate"
    ),
    "opencode/claude-opus-4-8": ModelInfo(
        id="opencode/claude-opus-4-8",
        provider="opencode",
        cost_class="premium-metered",
        capability_class="heavy",
        headless_status="likely",
        rework_risk="medium",
        note="top capability, bills real money"
    ),
    "opencode/deepseek-v4-flash-free": ModelInfo(
        id="opencode/deepseek-v4-flash-free",
        provider="opencode",
        cost_class="free",
        capability_class="quick",
        headless_status="untested",
        rework_risk="medium",
        note="cheap, validate before trusting"
    ),
    "opencode/deepseek-v4-pro": ModelInfo(
        id="opencode/deepseek-v4-pro",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="workhorse",
        headless_status="likely",
        rework_risk="low",
        note="solid choice"
    )
}

def list_models(runner: Callable[[List[str], str], Tuple[int, str]]) -> List[str]:
    rc, out = runner(["opencode", "models"], ".")
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]
