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


def render_usage_table(ledger, oc_stats: dict, *, cursor_about=None) -> str:
    lines = ["| Slice | Complexity | Model | Rung | Tokens | Cost |",
             "|---|---|---|---|---|---|"]
    total_tokens = 0
    has_cursor_slice = False

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
        if (entry.model or "").startswith("cursor:"):
            has_cursor_slice = True

    lines.append("")
    lines.append(f"**Build total tokens:** {total_tokens}")
    lines.append("")

    # Render account blocks via the provider registry (provider-blind).
    # Fall back to the legacy oc_stats dict for the opencode block (the caller
    # already parsed `opencode stats` into it).  Cursor block uses cursor_about
    # (the parsed `cursor-agent about` dict).
    from cld_providers.opencode.provider import account_block as _oc_block
    lines.extend(_oc_block(oc_stats))

    if cursor_about and has_cursor_slice:
        lines.append("")
        from cld_providers.cursor.provider import account_block as _cur_block
        lines.extend(_cur_block(cursor_about))

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
