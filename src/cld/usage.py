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


def render_usage_table(ledger, oc_stats: dict, *, cursor_about=None) -> str:
    lines = ["| Slice | Model | Tokens | Cost |", "|---|---|---|---|"]
    total_tokens = 0
    has_cursor_slice = False

    for entry in ledger.entries.values():
        tokens = entry.token_usage.get("total", 0)
        total_tokens += tokens
        cost_str = "" if entry.cost is None else str(entry.cost)
        lines.append(f"| {entry.slice_id} | {entry.model} | {tokens} | {cost_str} |")
        if entry.model.startswith("cursor:"):
            has_cursor_slice = True
    lines.append("")
    lines.append(f"**Build total tokens:** {total_tokens}")
    lines.append("")
    lines.append("## OpenCode account")
    if "total_cost" in oc_stats:
        lines.append(f"Total cost: ${oc_stats['total_cost']}")
        if "input" in oc_stats:
            lines.append(f"Input: {oc_stats['input']}")
        if "output" in oc_stats:
            lines.append(f"Output: {oc_stats['output']}")
    else:
        lines.append("OpenCode stats unavailable")
    if cursor_about and has_cursor_slice:
        tier = cursor_about.get("tier", "?")
        model = cursor_about.get("model", "?")
        lines.append("")
        lines.append("## Cursor account")
        lines.append(f"Tier: {tier}   Default model: {model}")
        lines.append(
            "Token/cost totals are server-side - run /usage in the Cursor TUI or see cursor.com."
        )
    return "\n".join(lines)
