import os
from dataclasses import dataclass, field
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
    tier: str | None = None

MODEL_METADATA: Dict[str, ModelInfo] = {
    "gemini:gemini-3.1-pro-preview": ModelInfo(
        id="gemini:gemini-3.1-pro-preview",
        provider="gemini",
        cost_class="flat",
        capability_class="workhorse",
        headless_status="verified",
        rework_risk="low",
        note="our 14/14 grade-A workhorse; $0 flat-rate",
        tier="workhorse"
    ),
    "opencode/claude-opus-4-8": ModelInfo(
        id="opencode/claude-opus-4-8",
        provider="opencode",
        cost_class="premium-metered",
        capability_class="heavy",
        headless_status="likely",
        rework_risk="medium",
        note="top capability, bills real money",
        tier=None
    ),
    "opencode/deepseek-v4-flash-free": ModelInfo(
        id="opencode/deepseek-v4-flash-free",
        provider="opencode",
        cost_class="free",
        capability_class="quick",
        headless_status="untested",
        rework_risk="medium",
        note="cheap, validate before trusting",
        tier="quick"
    ),
    "opencode/deepseek-v4-pro": ModelInfo(
        id="opencode/deepseek-v4-pro",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="workhorse",
        headless_status="likely",
        rework_risk="low",
        note="solid choice",
        tier="workhorse"
    ),
    "opencode/gemini-3.1-pro": ModelInfo(
        id="opencode/gemini-3.1-pro",
        provider="opencode",
        cost_class="cheap-metered",  # via OpenCode's account, NOT the flat-rate Google sub
        capability_class="workhorse",
        headless_status="likely",
        rework_risk="low",
        note="same model as the flat-rate workhorse, routed through OpenCode (metered)",
        tier="workhorse"
    ),
    "opencode/kimi-k2.6": ModelInfo(
        id="opencode/kimi-k2.6",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="heavy",
        headless_status="untested",
        rework_risk="medium",
        note="strong model; never cleanly validated headless - validate before trusting",
        tier="workhorse"
    ),
    "opencode/kimi-k2.7": ModelInfo(
        id="opencode/kimi-k2.7",
        provider="opencode",
        cost_class="cheap-metered",
        capability_class="heavy",
        headless_status="untested",
        rework_risk="medium",
        # Catalogued ahead of availability: stays filtered out of the shortlist until
        # `opencode models` lists it (gated by available_ids), then auto-appears.
        note="newer Kimi via OpenCode; validate before trusting headless",
        tier="workhorse"
    ),
    "opencode/claude-sonnet-4-6": ModelInfo(
        id="opencode/claude-sonnet-4-6",
        provider="opencode",
        cost_class="premium-metered",
        capability_class="heavy",
        headless_status="likely",
        rework_risk="low",
        note="capable Anthropic Sonnet via OpenCode; bills real money",
        tier=None
    ),
    "cursor:composer-2.5": ModelInfo(
        id="cursor:composer-2.5",
        provider="cursor",
        cost_class="cheap-metered",
        capability_class="heavy",
        headless_status="untested",
        rework_risk="low",
        note="Cursor's cost-optimized Composer; resolve_composer_default tracks the current version",
        tier="workhorse"
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


# The verified flat-rate workhorse always surfaces in the shortlist, even when it is
# absent from `available_ids` — it runs via the Gemini CLI, not the OpenCode model
# list, so filtering the picker to `opencode models` ids must never hide it. (Bug
# found in a live skill test: shortlist came back with no default/workhorse.)
DEFAULT_WORKHORSE_ID = "gemini:gemini-3.1-pro-preview"

KNOWN_PROVIDERS = ("claude", "gpt", "gemini", "deepseek", "grok", "kimi", "qwen", "glm", "minimax")
TIERS = ("quick", "workhorse")

@dataclass
class ModelChoice:
    spec: str
    executor: str
    provider: str
    model: str
    label: str
    cost_class: str
    headless_status: str
    efforts: list = field(default_factory=list)
    default_effort: str | None = None


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
    token = token.rstrip("0123456789")
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
            if status == "revalidate":
                continue
            item = BrowseItem(id, provider=_provider_of(id), cost_class=info.cost_class, headless_status=status, in_catalog=True)
        else:
            status = evidence.get(id, "untested")
            if status == "revalidate":
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
    # Always consider the verified default available (it's not an OpenCode model).
    evidence = evidence or {}
    effective_ids = (set(available_ids) | {DEFAULT_WORKHORSE_ID}) - set(session_known_bad)
    recs: list[Recommendation] = []
    for id, info in MODEL_METADATA.items():
        if id not in effective_ids:
            continue
        # Cursor models are intentionally NOT offered in the first-selection shortlist:
        # cursor-agent's long-prompt headless dispatch is a known defect (see
        # docs/notes/cursor-cli-notes.md), so Composer/cursor live ONLY in the Browse
        # drill-down (build_model_index), never as a default shortlist pick.
        if id.startswith("cursor:"):
            continue
        # durable validation evidence overrides the static catalog status
        status = evidence.get(id, info.headless_status)
        if status == "revalidate":
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
            if rec.headless_status == "verified" and rec.bucket == "workhorse":
                default_candidate = rec
                break
    if default_candidate is None:
        for rec in recs:
            if rec.headless_status == "verified":
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


def render_chat_picker(recs: List["Recommendation"]) -> str:
    """The COMPLETE agent-surface picker dialog, as one verbatim string.

    Use this — not a hand-assembled list — whenever you (the lead agent) present the
    executor picker in chat. It guarantees the required dialog shape every time:
      1. the curated shortlist (from `render_shortlist`, verbatim);
      2. a numbered ``Browse all models…`` entry → opens the secondary drill-down
         (executor → provider → model → effort) over the full unified index;
      3. a numbered ``Other`` free-text escape hatch.
    Paste the returned text directly. The failure this prevents: building the dialog by
    hand and dropping the ``Browse all models…`` option (so the user can't reach the
    full model list). Output is cp1252-safe.
    """
    lines, ordered = render_shortlist(recs)
    n = len(ordered)
    lines.append(f"    {n + 1}) Browse all models...   (full list: executor -> provider -> model -> effort, with search)")
    lines.append(f"    {n + 2}) Other (type a model id, e.g. opencode:opencode/<model>)")
    lines.append("Pick one [default: workhorse]:")
    return "\n".join(lines)


def pick_executor(recs, *, input_fn=input, output_fn=print) -> str:
    """Interactive picker: show the shortlist, read a choice, return an executor spec.

    - Pressing enter selects the default (verified workhorse).
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


def list_cursor_models(runner: Callable[[List[str], str], Tuple[int, str]]) -> List[Tuple[str, str]]:
    try:
        rc, out = runner(["cursor-agent", "--list-models"], ".")
    except OSError:
        return []
    if rc != 0:
        return []
    
    models = []
    for line in out.splitlines():
        line = line.strip()
        if not line or " - " not in line:
            continue
        id_part, label_part = line.split(" - ", 1)
        id_part = id_part.strip()
        label_part = label_part.strip()
        if id_part == "auto":
            continue
        models.append((id_part, label_part))
    return models


def resolve_composer_default(runner) -> str:
    fallback = "composer-2.5"
    try:
        models = list_cursor_models(runner)
        composers = [(mid, label) for mid, label in models if mid.startswith("composer")]
        if not composers:
            return fallback

        for mid, label in composers:
            if "(current)" in label:
                return mid

        for mid, label in composers:
            if "(default)" in label:
                return mid

        max_ver = -1.0
        max_id = fallback
        found_version = False
        for mid, label in composers:
            if mid.startswith("composer-"):
                ver_str = mid[len("composer-"):].split("-")[0]
                try:
                    ver = float(ver_str)
                    if ver > max_ver:
                        max_ver = ver
                        max_id = mid
                        found_version = True
                except ValueError:
                    pass
        
        if found_version:
            return max_id
        return fallback
    except Exception:
        return fallback


def build_model_index(*, opencode_ids, cursor_models, evidence) -> List[ModelChoice]:
    out = []

    gemini_id = "gemini:gemini-3.1-pro-preview"
    gem_info = MODEL_METADATA[gemini_id]
    out.append(
        ModelChoice(
            spec=gemini_id,
            executor="gemini",
            provider="gemini",
            model="gemini-3.1-pro-preview",
            label=gem_info.note,
            cost_class=gem_info.cost_class,
            headless_status=evidence.get(gemini_id, gem_info.headless_status),
            efforts=[],
            default_effort=None,
        )
    )

    for id in opencode_ids:
        if id in MODEL_METADATA:
            cost_class = MODEL_METADATA[id].cost_class
            base_status = MODEL_METADATA[id].headless_status
        else:
            cost_class = "free" if id.endswith("-free") else "metered-unknown"
            base_status = "untested"

        status = evidence.get(id, base_status)
        if status == "revalidate":
            continue
            
        out.append(
            ModelChoice(
                spec="opencode:" + id,
                executor="opencode",
                provider=_provider_of(id),
                model=id.rsplit("/", 1)[-1],
                label=id.rsplit("/", 1)[-1],
                cost_class=cost_class,
                headless_status=status,
                efforts=[],
                default_effort=None,
            )
        )

    cursor_groups = {}
    for cid, clabel in cursor_models:
        working_id = cid
        if working_id.endswith("-fast"):
            working_id = working_id[:-5]
        if working_id.endswith("-thinking"):
            working_id = working_id[:-9]
        
        parts = working_id.rsplit("-", 1)
        if len(parts) == 2 and parts[1] in {"low", "medium", "high", "xhigh", "max"}:
            effort = parts[1]
            base_id = parts[0]
        else:
            effort = None
            base_id = working_id
            
        if base_id not in cursor_groups:
            cursor_groups[base_id] = []
        cursor_groups[base_id].append((cid, clabel, effort))
        
    for base_id, items in cursor_groups.items():
        key = "cursor:" + base_id
        if key in MODEL_METADATA:
            cost_class = MODEL_METADATA[key].cost_class
            base_status = MODEL_METADATA[key].headless_status
        else:
            cost_class = "metered-unknown"
            base_status = "untested"

        status = evidence.get(key, base_status)
        if status == "revalidate":
            continue

        no_effort_item = next((item for item in items if item[2] is None), None)
        raw_label = no_effort_item[1] if no_effort_item else items[0][1]
        
        if raw_label.endswith(" (current)"):
            clean_label = raw_label[:-10].strip()
        elif raw_label.endswith(" (default)"):
            clean_label = raw_label[:-10].strip()
        else:
            clean_label = raw_label

        efforts_set = {item[2] for item in items if item[2] is not None}
        efforts = sorted(list(efforts_set))
        
        marked_item = next((item for item in items if "(default)" in item[1] or "(current)" in item[1]), None)
        if marked_item:
            default_effort = marked_item[2]
        elif "high" in efforts:
            default_effort = "high"
        elif not efforts:
            default_effort = None
        else:
            default_effort = efforts[0]

        out.append(
            ModelChoice(
                spec=key,
                executor="cursor",
                provider=_provider_of(base_id),
                model=base_id,
                label=clean_label,
                cost_class=cost_class,
                headless_status=status,
                efforts=efforts,
                default_effort=default_effort,
            )
        )

    return out


def browse_filter(choices: List[ModelChoice], *, headless_only: bool = True) -> List[ModelChoice]:
    filtered = []
    for choice in choices:
        if choice.headless_status == "revalidate":
            continue
        if headless_only and choice.headless_status not in ("verified", "likely"):
            continue
        filtered.append(choice)
    return filtered


def rank_provider_models(choices: List[ModelChoice], *, n: int = 12) -> List[ModelChoice]:
    ranks = {"verified": 0, "likely": 1, "untested": 2}
    sorted_choices = sorted(choices, key=lambda c: ranks.get(c.headless_status, 3))
    return sorted_choices[:n]


def search_models(index, query, *, headless_only=True) -> list[ModelChoice]:
    query = query.lower()
    pool = browse_filter(index, headless_only=headless_only)
    kept = []
    for choice in pool:
        if (query in choice.spec.lower() or
            query in choice.provider.lower() or
            query in choice.executor.lower() or
            query in choice.model.lower() or
            query in choice.label.lower()):
            kept.append(choice)

    def rank_key(choice):
        c_model = choice.model.lower()
        if c_model == query:
            return 0
        if c_model.startswith(query):
            return 1
        return 2

    return sorted(kept, key=rank_key)


def render_executor_level(index):
    execs = []
    for c in index:
        if c.executor not in execs:
            execs.append(c.executor)
    lines = ["Choose an executor:"]
    for i, e in enumerate(execs, 1):
        n = sum(1 for c in index if c.executor == e)
        lines.append(f"  {i}) {e}   ({n} models)")
    lines.append("  S) Search models...")
    return lines, execs


def render_provider_level(index, *, executor):
    provs = []
    for c in index:
        if c.executor == executor and c.provider not in provs:
            provs.append(c.provider)
    provs.sort()
    lines = [f"{executor} - choose a provider:"]
    for i, p in enumerate(provs, 1):
        n = sum(1 for c in index if c.executor == executor and c.provider == p)
        lines.append(f"  {i}) {p}   ({n})")
    lines.append("  S) Search models...")
    return lines, provs


def render_model_level(index, *, executor, provider, headless_only=True, n=12):
    pool = [c for c in index if c.executor == executor and c.provider == provider]
    pool = browse_filter(pool, headless_only=headless_only)
    ranked = rank_provider_models(pool, n=n)
    lines = [f"{executor}/{provider} - choose a model:"]
    ordered = []
    for i, c in enumerate(ranked, 1):
        ordered.append(c)
        eff = f"  efforts: {','.join(c.efforts)}" if c.efforts else ""
        warn = "  (!) untested" if c.headless_status == "untested" else ""
        lines.append(f"  {i}) {c.spec:42s} {c.cost_class:16s} {c.headless_status:8s}{eff}{warn}")
    if len(pool) > len(ranked):
        lines.append(f"  M) More... ({len(pool) - len(ranked)} more)")
    lines.append("  S) Search models...")
    return lines, ordered


def render_effort_level(choice):
    if not choice.efforts:
        return [], []
    lines = [f"{choice.label} - choose effort:"]
    for i, e in enumerate(choice.efforts, 1):
        mark = "  (default)" if e == choice.default_effort else ""
        lines.append(f"  {i}) {e}{mark}")
    return lines, list(choice.efforts)


def spec_with_effort(choice, effort) -> str:
    """The choice's base spec, plus @<effort> UNLESS effort is None or the CLI default
    (default = bare spec, so the CLI's own default applies)."""
    if not effort or effort == choice.default_effort:
        return choice.spec
    return f"{choice.spec}@{effort}"


def render_routing_plan(slices, *, provider: str, evidence: dict, available_ids: list) -> str:
    """Render a one-screen routing plan table for all slices.

    For each slice: calls plan_rungs to determine the recommended model (first rung's
    spec). Marks pinned slices with [you] and auto-routed with [rec]. Flags complex
    slices with !. Returns ASCII/cp1252-safe string.
    """
    header = f"  {'SLICE':6} {'COMPLEXITY':9} -> {'RECOMMENDED MODEL':42} {'MARK':6}"
    lines: List[str] = [header]
    for s in slices:
        rungs = plan_rungs(s, provider=provider, evidence=evidence, available_ids=available_ids)
        rec = rungs[0][1]
        mark = "[you]" if s.executor else "[rec]"
        flag = " !" if s.complexity == "complex" else ""
        lines.append(f"  {s.id:6} {s.complexity:9} -> {rec:42} {mark}{flag}")
    return "\n".join(lines)


# ---- Complexity routing table ----

COMPLEXITY_ROUTING: dict[str, tuple[str, int]] = {
    "easy": ("quick", 1),
    "standard": ("workhorse", 2),
    "complex": ("workhorse", 1),
}

# Climb chains: for each entry tier, which tiers to try in order
_CLIMB_CHAINS: dict[str, list[str]] = {
    "quick": ["quick", "workhorse"],
    "workhorse": ["workhorse"],
}


def plan_rungs(
    task,
    *,
    provider: str,
    evidence: dict,
    available_ids: list[str],
    max_retries: int = 2,
) -> list[tuple[str, str, int]]:
    """Return the ordered list of cheap executor rungs for a slice to climb.

    Each element is (rung_name, spec, budget).
    - Tagged slice (task.executor set): single pinned rung ("workhorse", spec, max_retries).
    - Untagged: build the chain from COMPLEXITY_ROUTING[task.complexity], de-dupe specs.
    - Fallback: if nothing resolves, return [("workhorse", DEFAULT_WORKHORSE_ID, max_retries)].
    """
    # Tagged: pinned to the nominated executor, no auto-routing
    if task.executor:
        return [("workhorse", task.executor, max_retries)]

    complexity = getattr(task, "complexity", "standard")
    entry_tier, entry_budget = COMPLEXITY_ROUTING[complexity]
    chain = _CLIMB_CHAINS[entry_tier]

    rungs: list[tuple[str, str, int]] = []
    seen_specs: set[str] = set()

    for i, tier in enumerate(chain):
        spec = resolve_tier_model(provider, tier, evidence=evidence, available_ids=available_ids)
        if spec is None or spec in seen_specs:
            continue
        seen_specs.add(spec)
        # Entry tier uses the complexity's budget; higher fallback tiers use standard budget (2)
        budget = entry_budget if i == 0 else 2
        rungs.append((tier, spec, budget))

    if not rungs:
        return [("workhorse", DEFAULT_WORKHORSE_ID, max_retries)]

    return rungs


# ---- resolve_tier_model: cheapest viable model in a (provider, tier) ----

_COST_RANK = {"free": 0, "flat": 0, "cheap-metered": 1, "metered-unknown": 2, "premium-metered": 3}


def _spec_of_catalog_id(cid: str) -> str:
    """Map a catalog id to an --executor spec string.

    opencode/<...> ids need the opencode: executor prefix.
    ids that already contain ':' (e.g. gemini:<model>) are returned as-is.
    """
    return f"opencode:{cid}" if cid.startswith("opencode/") else cid


def resolve_tier_model(
    provider: str,
    tier: str,
    *,
    evidence: dict,
    available_ids: list[str],
) -> str | None:
    """Return the cheapest viable catalog model spec for (provider, tier).

    Here `provider` is the executor name ("opencode", "gemini", "cursor").

    Viability rules:
    - Effective status = evidence.get(id, info.headless_status).
    - Skip 'revalidate' entirely.
    - Prefer verified/likely; include untested ONLY if no verified/likely exists.
    - The DEFAULT_WORKHORSE_ID (Gemini flat workhorse) is always considered available.
    - Sort viable candidates by (cost_rank, id); return the spec of the first.
    - Returns None when nothing viable.
    """
    avail = set(available_ids) | {DEFAULT_WORKHORSE_ID}
    cands = []
    for cid, info in MODEL_METADATA.items():
        if info.tier != tier or info.provider != provider:
            continue
        if cid not in avail:
            continue
        status = (evidence or {}).get(cid, info.headless_status)
        if status == "revalidate":
            continue
        cands.append((cid, info, status))

    if not cands:
        return None

    trusted = [c for c in cands if c[2] in ("verified", "likely")]
    pool = trusted if trusted else cands  # untested only if no trusted
    pool.sort(key=lambda c: (_COST_RANK.get(c[1].cost_class, 9), c[0]))
    return _spec_of_catalog_id(pool[0][0])

