"""cld.cli_response — bounded schema-version-1 JSON CLI responses (T11).

JSON mode writes exactly ONE JSON object to stdout; progress goes to
stderr/artifacts. This module is the single place that assembles that object:
required fields, truthful gate exit codes, bounded text/collections so a
response never dumps raw logs or history, and truncation markers when a
collection had to be limited.

Gate meanings (preserved from the text driver):
    pending=0/resume, failed=2/resume, needs_repair=4/repair,
    integration_required=6/integrate, passed=3/complete, blocked=5/correct_input
"""

import json

SCHEMA_VERSION = 1
MAX_BYTES = 32768  # acceptance bound for the default response
TEXT_LIMIT = 2000  # no single string may dump more than this
ITEM_LIMIT = 100   # collections are capped; truncation is marked

# gate -> (process exit code, next action)
GATES = {
    "pending": (0, "resume"),
    "failed": (2, "resume"),
    "needs_repair": (4, "repair"),
    "integration_required": (6, "integrate"),
    "passed": (3, "complete"),
    "blocked": (5, "correct_input"),
}
_GATES_BY_CODE = {code: gate for gate, (code, _action) in GATES.items()}

_DEFAULT_ARTIFACTS = {"run_directory": None, "events": None}


def gate_code(gate: str) -> int:
    return GATES[gate][0]


def next_action(gate: str) -> str:
    return GATES[gate][1]


def gate_for_code(code: int) -> str:
    """Truthful exit-code -> gate mapping; unknown codes are blocked (fail closed)."""
    return _GATES_BY_CODE.get(code, "blocked")


def null_usage() -> dict:
    """Explicit empty usage: unknown usage is null, never an invented number."""
    return {"attempts": 0, "input": None, "output": None, "total": None, "cost": None}


def null_budget() -> dict:
    return {"tokens": None, "cost": None, "attempts": None,
            "attempt_tokens": None, "attempt_cost": None, "unknown": None}


def bounded_text(value, limit: int = TEXT_LIMIT) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) > limit:
        return text[:limit] + "...[truncated]"
    return text


def make_error(reason, action: str = "correct_input") -> dict:
    """One structured error: a bounded reason plus a useful next action."""
    return {"reason": bounded_text(reason), "next_action": action}


def bound(value, _depth: int = 0):
    """Recursively bound a JSON-serializable value (strings and collections)."""
    if _depth >= 8:
        return {"truncated": True}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return bounded_text(value)
    if isinstance(value, dict):
        items = list(value.items())
        out = {bounded_text(k, 200): bound(v, _depth + 1) for k, v in items[:ITEM_LIMIT]}
        if len(items) > ITEM_LIMIT:
            out["truncated"] = True
            out["total"] = len(items)
        return out
    if isinstance(value, (list, tuple)):
        out = [bound(v, _depth + 1) for v in value[:ITEM_LIMIT]]
        if len(value) > ITEM_LIMIT:
            out.append({"truncated": True, "total": len(value)})
        return out
    return bounded_text(value)


def build(*, command: str, gate: str, run_id=None, repository=None, ledger=None,
          artifacts=None, usage=None, budget=None, accepted_refs=None,
          errors=None, extra=None) -> dict:
    """Assemble one schema-version-1 response with every required field."""
    code, action = GATES[gate]
    response = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "gate": gate,
        "gate_code": code,
        "next_action": action,
        "run_id": run_id,
        "repository": repository,
        "ledger": ledger,
        "artifacts": artifacts if artifacts is not None else dict(_DEFAULT_ARTIFACTS),
        "usage": usage if usage is not None else null_usage(),
        "budget": budget if budget is not None else null_budget(),
        "accepted_refs": accepted_refs if accepted_refs is not None else [],
        "errors": errors if errors is not None else [],
    }
    if extra:
        for key, value in extra.items():
            response[key] = bound(value)
    return response


def dumps(response: dict, limit: int = MAX_BYTES) -> str:
    """Bound output without changing a collection's JSON type or ref contents."""
    shrunk = dict(response)

    def serialize():
        return json.dumps(shrunk, ensure_ascii=True, allow_nan=False)

    # Keep useful exact references, and report omitted counts separately.
    for key in ("accepted_refs", "slices", "layers", "errors"):
        value = shrunk.get(key)
        if isinstance(value, list) and len(value) > ITEM_LIMIT:
            shrunk[key + "_count"] = len(value)
            shrunk[key + "_truncated"] = True
            shrunk[key] = value[:ITEM_LIMIT]
    raw = serialize()
    for key in ("details", "slices", "layers", "accepted_refs", "artifacts", "errors"):
        if len(raw.encode("utf-8")) < limit:
            return raw
        value = shrunk.get(key)
        if not isinstance(value, (dict, list)) or not value:
            continue
        shrunk.setdefault(key + "_count", len(value))
        shrunk[key + "_truncated"] = True
        # Reduce progressively, preserving useful entries and container types.
        while value and len(raw.encode("utf-8")) >= limit:
            size = len(value) // 2
            value = value[:size] if isinstance(value, list) else dict(list(value.items())[:size])
            shrunk[key] = value
            raw = serialize()
    if len(raw.encode("utf-8")) >= limit:
        raise ValueError("Response identity or scalar fields exceed the JSON size limit")
    return raw
