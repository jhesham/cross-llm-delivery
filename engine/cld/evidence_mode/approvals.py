"""Append-only approvals for writes to real environments."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cld.locking import file_owner


def record_approval(repo, *, env, sql_hash, approved_by, reason) -> dict:
    """Append and return an approval record for one environment and SQL hash."""
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise ValueError("approved_by must not be blank")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must not be blank")

    directory = Path(repo) / ".cld"
    path = directory / "approvals.jsonl"
    record = {
        "env": env,
        "sql_hash": sql_hash,
        "approved_by": approved_by,
        "reason": reason,
        "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    line = json.dumps(record, separators=(",", ":")) + "\n"

    with file_owner(directory / "approvals.lock", wait_seconds=10):
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)

    return record


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value):
    raise ValueError(f"invalid JSON constant: {value}")


def _valid_record(record):
    if not isinstance(record, dict):
        return False
    if not {"env", "sql_hash", "approved_by", "reason", "approved_at"}.issubset(record):
        return False
    if not isinstance(record["approved_by"], str) or not record["approved_by"].strip():
        return False
    if not isinstance(record["reason"], str) or not record["reason"].strip():
        return False
    if not isinstance(record["approved_at"], str):
        return False
    try:
        approved_at = datetime.fromisoformat(record["approved_at"])
    except ValueError:
        return False
    return approved_at.tzinfo is not None and approved_at.utcoffset() == timedelta(0)


def is_approved(repo, *, env, sql_hash) -> bool:
    """Return whether a valid approval exists, failing closed on corrupt data."""
    path = Path(repo) / ".cld" / "approvals.jsonl"
    approved = False
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(
                    line,
                    object_pairs_hook=_reject_duplicate_keys,
                    parse_constant=_reject_nonstandard_constant,
                )
                if not _valid_record(record):
                    return False
                if record["env"] == env and record["sql_hash"] == sql_hash:
                    approved = True
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    return approved
