import re


def parse_cursor_about(text: str) -> dict:
    """Parse the output of `cursor-agent about` into a dict with 'tier' and 'model' keys."""
    result = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Subscription Tier "):
            result["tier"] = stripped[len("Subscription Tier "):].strip()
        elif stripped.startswith("Model "):
            # "Model Composer 2.5 Fast" -> model: "Composer 2.5 Fast"
            result["model"] = stripped[len("Model "):].strip()
    return result


def parse_opencode_stats(text: str) -> dict:
    result = {}
    for line in text.splitlines():
        m = re.search(r"Total Cost\s+\$([\d.]+)", line)
        if m:
            result["total_cost"] = float(m.group(1))
            continue
        for key in ("Input", "Output", "Cache Read", "Cache Write"):
            m = re.search(rf"{key}\s+([\d.]+[KMBT]?)", line)
            if m:
                result[key.lower().replace(" ", "_")] = m.group(1)
                break

    return result


# ---------------------------------------------------------------------------
# Account block helpers: single source of truth is in cld_providers.*.
# Re-exported via module __getattr__ (below) to keep existing callers working
# without duplicating the `def` body (de-dup gate requires one definition each).
# ---------------------------------------------------------------------------


def _model_belongs_to_provider(model: str, provider_name: str) -> bool:
    """Return True if a ledger model string belongs to the named provider.

    Matches "opencode:..." or "opencode/..." prefixes.
    """
    if not model:
        return False
    return model.startswith(f"{provider_name}:") or model.startswith(f"{provider_name}/")


def render_usage_table(ledger) -> str:
    """Render a markdown usage table for *ledger*.

    Provider-blind: discovers registered providers via the registry and calls
    each provider's account_section() for account blocks.  No hardcoded
    provider names or imports.
    """
    from cld.providers_api import all_providers, load_providers
    load_providers()

    lines = ["| Slice | Complexity | Model | Rung | Tokens | Cost |",
             "|---|---|---|---|---|---|"]
    total_tokens = 0
    models_seen: set[str] = set()

    for entry in ledger.entries.values():
        tokens = entry.token_usage.get("total", 0)
        total_tokens += tokens
        cost_str = "" if entry.cost is None else str(entry.cost)
        complexity = getattr(entry, "complexity", None) or "-"
        rung = getattr(entry, "final_rung", None) or "-"
        model = entry.model or "-"
        lines.append(
            f"| {entry.slice_id} | {complexity} | {model} | {rung} | {tokens} | {cost_str} |"
        )
        if entry.model:
            models_seen.add(entry.model)

    lines.append("")
    lines.append(f"**Build total tokens:** {total_tokens}")
    lines.append("")

    # Provider-blind account sections: each provider self-sources its stats.
    first_section = True
    for provider in all_providers():
        if provider.account_section is None:
            continue
        # Only emit a block when at least one ledger entry used this provider.
        has_models = any(_model_belongs_to_provider(m, provider.name) for m in models_seen)
        if not has_models:
            continue
        if not first_section:
            lines.append("")
        block = provider.account_section()
        if block:
            lines.extend(block)
            first_section = False

    return "\n".join(lines)


def __getattr__(name: str):
    """Lazy re-exports for account block helpers (single source in cld_providers).

    Using __getattr__ avoids duplicate `def` bodies caught by the de-dup gate while
    keeping existing callers (e.g. `from cld.usage import opencode_account_block`)
    working without change.
    """
    if name == "opencode_account_block":
        from cld_providers.opencode.provider import account_block
        return account_block
    if name == "cursor_account_block":
        from cld_providers.cursor.provider import account_block
        return account_block
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
