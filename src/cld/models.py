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
    ),
    "opencode/gemini-3.1-pro": ModelInfo(
        id="opencode/gemini-3.1-pro",
        provider="opencode",
        cost_class="cheap-metered",  # via OpenCode's account, NOT the flat-rate Google sub
        capability_class="workhorse",
        headless_status="likely",
        rework_risk="low",
        note="same model as the flat-rate workhorse, routed through OpenCode (metered)"
    ),
    "opencode/kimi-k2.6": ModelInfo(
        id="opencode/kimi-k2.6",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="heavy",
        headless_status="untested",
        rework_risk="medium",
        note="strong model; never cleanly validated headless - validate before trusting",
    ),
    "opencode/claude-sonnet-4-6": ModelInfo(
        id="opencode/claude-sonnet-4-6",
        provider="opencode",
        cost_class="premium-metered",
        capability_class="heavy",
        headless_status="likely",
        rework_risk="low",
        note="capable Anthropic Sonnet via OpenCode; bills real money",
    ),
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


# The proven flat-rate workhorse always surfaces in the shortlist, even when it is
# absent from `available_ids` — it runs via the Gemini CLI, not the OpenCode model
# list, so filtering the picker to `opencode models` ids must never hide it. (Bug
# found in a live skill test: shortlist came back with no default/workhorse.)
DEFAULT_WORKHORSE_ID = "gemini:gemini-3.1-pro-preview"

KNOWN_PROVIDERS = ("claude", "gpt", "gemini", "deepseek")

@dataclass
class BrowseItem:
    id: str
    provider: str
    cost_class: str
    headless_status: str
    in_catalog: bool

def _provider_of(model_id: str) -> str:
    name = model_id
    if name.startswith("opencode/"):
        name = name[len("opencode/"):]
    elif ":" in name:
        name = name.split(":", 1)[1]
    token = name.replace(".", "-").split("-", 1)[0].lower()
    return token if token in KNOWN_PROVIDERS else "other"

def browse_models(available_ids, *, session_known_bad=frozenset(),
                  evidence=None) -> Dict[str, List[BrowseItem]]:
    evidence = evidence or {}
    ids = [i for i in available_ids if i not in session_known_bad]
    if DEFAULT_WORKHORSE_ID not in ids and DEFAULT_WORKHORSE_ID not in session_known_bad:
        ids.append(DEFAULT_WORKHORSE_ID)

    groups = {}
    for id in ids:
        if id in MODEL_METADATA:
            info = MODEL_METADATA[id]
            # durable validation evidence overrides the static catalog status
            status = evidence.get(id, info.headless_status)
            if status == "known-bad":
                continue
            item = BrowseItem(id, provider=_provider_of(id), cost_class=info.cost_class, headless_status=status, in_catalog=True)
        else:
            status = evidence.get(id, "untested")
            if status == "known-bad":
                continue
            cost_class = "free" if id.endswith("-free") else "metered-unknown"
            item = BrowseItem(id, provider=_provider_of(id), cost_class=cost_class, headless_status=status, in_catalog=False)
            
        provider = item.provider
        if provider not in groups:
            groups[provider] = []
        groups[provider].append(item)
        
    for p in groups:
        groups[p].sort(key=lambda x: x.id)

    ordered_keys = sorted(groups, key=lambda p: (0 if any(i.in_catalog for i in groups[p]) else 1, p))
    return {k: groups[k] for k in ordered_keys}


def render_browse_list(grouped) -> tuple:
    """Render the grouped browse view verbatim (the chat/CLI surfaces copy these
    lines — never hand-type options). Returns (lines, ordered) where a numeric
    pick N maps to ordered[N-1]. ASCII only ($ = billed, (!) = untested)."""
    lines: List[str] = ["All available models (grouped by provider):"]
    ordered: List[BrowseItem] = []
    n = 0
    for provider, items in grouped.items():
        lines.append(f"  {provider.upper()}")
        for it in items:
            n += 1
            ordered.append(it)
            cost = it.cost_class + (" $" if it.cost_class == "premium-metered" else "")
            warn = "  (!) untested" if it.headless_status == "untested" else ""
            lines.append(
                f"    {n}) {_spec_for(it):42s} {cost:18s} {it.headless_status:8s}{warn}"
            )
    return lines, ordered


def recommend(*, available_ids, job=None, session_known_bad=frozenset(),
              evidence=None) -> list[Recommendation]:
    # Always consider the proven default available (it's not an OpenCode model).
    evidence = evidence or {}
    effective_ids = (set(available_ids) | {DEFAULT_WORKHORSE_ID}) - set(session_known_bad)
    recs: list[Recommendation] = []
    for id, info in MODEL_METADATA.items():
        if id not in effective_ids:
            continue
        # durable validation evidence overrides the static catalog status
        status = evidence.get(id, info.headless_status)
        if status == "known-bad":
            continue
        warning = ""
        if status == "untested":
            warning = "untested: may not complete builds reliably; validate first"
        confirm_cost = info.cost_class == "premium-metered"
        rec = Recommendation(
            id=id,
            bucket=info.capability_class,
            capability_class=info.capability_class,
            cost_class=info.cost_class,
            headless_status=status,
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


_BUCKET_LABELS = [
    ("workhorse", "WORKHORSE (default)"),
    ("heavy", "HEAVY (hard slices, worth more $)"),
    ("quick", "QUICK / BUDGET"),
]


def _spec_for(rec: "Recommendation") -> str:
    """Map a catalogued model id to an `--executor` spec.

    Gemini catalog ids are already spec-shaped (`gemini:<model>`). OpenCode ids
    look like `opencode/<provider>/<model>` and need the `opencode:` executor
    prefix in front.
    """
    if rec.id.startswith("opencode/"):
        return f"opencode:{rec.id}"
    return rec.id  # gemini:<model> (already a spec)


def render_shortlist(recs: List["Recommendation"]) -> List[str]:
    """Build the bucketed shortlist lines (numbered), default marked with '>'."""
    lines = ["Recommended executors (installed + available):"]
    n = 0
    ordered: List["Recommendation"] = []
    seen = set()
    for bucket, label in _BUCKET_LABELS:
        bucket_recs = [r for r in recs if r.bucket == bucket]
        if not bucket_recs:
            continue
        lines.append(f"  {label}")
        for r in bucket_recs:
            n += 1
            ordered.append(r)
            seen.add(id(r))
            marker = ">" if r.is_default else " "
            cost = r.cost_class + (" $" if r.confirm_cost else "")
            warn = "  (!) " + r.warning if r.warning else ""
            lines.append(
                f"  {marker} {n}) {_spec_for(r):42s} {cost:18s} {r.headless_status:8s}{warn}"
            )
    # any uncatalogued-bucket recs (defensive) appended last
    for r in recs:
        if id(r) not in seen:
            n += 1
            ordered.append(r)
            lines.append(f"    {n}) {_spec_for(r)}")
    return lines, ordered


def pick_executor(recs, *, input_fn=input, output_fn=print) -> str:
    """Interactive picker: show the shortlist, read a choice, return an executor spec.

    - Pressing enter selects the default (proven workhorse).
    - A number selects that line; a premium-metered pick (confirm_cost) requires a
      y/N confirmation — declining falls back to the default.
    - input_fn/output_fn are injected for testing (default to builtin input/print).
    Returns a spec string suitable for parse_executor_spec / --executor.
    """
    lines, ordered = render_shortlist(recs)
    for ln in lines:
        output_fn(ln)

    default_rec = next((r for r in ordered if r.is_default), ordered[0] if ordered else None)
    if default_rec is None:
        return "gemini"  # empty catalog -> safe default

    raw = (input_fn("Pick one [default: workhorse]: ") or "").strip()
    if not raw:
        return _spec_for(default_rec)

    try:
        choice = int(raw)
    except ValueError:
        output_fn("Unrecognized choice — using the default workhorse.")
        return _spec_for(default_rec)

    if not (1 <= choice <= len(ordered)):
        output_fn("Out of range — using the default workhorse.")
        return _spec_for(default_rec)

    chosen = ordered[choice - 1]
    if chosen.confirm_cost:
        output_fn(f"(!) {_spec_for(chosen)} bills real $ per dispatch (not flat-rate).")
        ans = (input_fn("Proceed with a billed model? [y/N]: ") or "").strip().lower()
        if ans not in ("y", "yes"):
            output_fn("Declined — using the default workhorse instead.")
            return _spec_for(default_rec)
    if chosen.warning:
        output_fn(f"Note: {chosen.warning}")
    return _spec_for(chosen)


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
