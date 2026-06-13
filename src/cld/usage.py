import re


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


def render_usage_table(ledger, oc_stats: dict) -> str:
    lines = ["| Slice | Model | Tokens | Cost |", "|---|---|---|---|"]
    total_tokens = 0
    for entry in ledger.entries.values():
        tokens = entry.token_usage.get("total", 0)
        total_tokens += tokens
        cost_str = "" if entry.cost is None else str(entry.cost)
        lines.append(f"| {entry.slice_id} | {entry.model} | {tokens} | {cost_str} |")
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
    return "\n".join(lines)
