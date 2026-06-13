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
