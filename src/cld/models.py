import os
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

@dataclass
class Recommendation:
    id: str
    bucket: str
    capability_class: str
    cost_class: str
    headless_status: str
    why: str
    is_default: bool = False
    warning: str = ""
    confirm_cost: bool = False


def recommend(*, available_ids, job=None) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for id, info in MODEL_METADATA.items():
        if id not in available_ids:
            continue
        if info.headless_status == "known-bad":
            continue
        warning = ""
        if info.headless_status == "untested":
            warning = "untested: may not complete builds reliably; validate first"
        confirm_cost = info.cost_class == "premium-metered"
        rec = Recommendation(
            id=id,
            bucket=info.capability_class,
            capability_class=info.capability_class,
            cost_class=info.cost_class,
            headless_status=info.headless_status,
            why=info.note,
            warning=warning,
            confirm_cost=confirm_cost,
        )
        recs.append(rec)

    default_candidate = None
    for rec in recs:
        if rec.id == "gemini:gemini-3.1-pro-preview":
            default_candidate = rec
            break
    if default_candidate is None:
        for rec in recs:
            if rec.headless_status == "proven" and rec.bucket == "workhorse":
                default_candidate = rec
                break
    if default_candidate is None:
        for rec in recs:
            if rec.headless_status == "proven":
                default_candidate = rec
                break
    if default_candidate is not None:
        default_candidate.is_default = True

    return recs


def list_models(runner: Callable[[List[str], str], Tuple[int, str]]) -> List[str]:
    """List available OpenCode model ids via `opencode models`.

    Resolves the platform-correct command (Windows npm shim is `opencode.cmd`,
    overridable with OPENCODE_CLI_CMD). Degrades to [] on any failure — nonzero
    exit OR the CLI not being on PATH (FileNotFoundError) — so the picker can
    fall back to "Gemini only" instead of crashing.
    """
    oc_cmd = os.environ.get("OPENCODE_CLI_CMD") or (
        "opencode.cmd" if os.name == "nt" else "opencode"
    )
    try:
        rc, out = runner([oc_cmd, "models"], ".")
    except OSError:
        return []
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]
