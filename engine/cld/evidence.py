"""Atomic, synchronized validation evidence; corruption fails closed."""
import json
from datetime import datetime, timezone
from pathlib import Path
from cld.locking import file_owner
from cld.recovery import atomic_write

DEFAULT_PATH = Path.home() / ".cld" / "validation-evidence.json"


class EvidenceError(RuntimeError):
    """Unreadable evidence is distinct from a missing cache."""


class EvidenceStore:
    def __init__(self, path=None):
        self._path = Path(path) if path is not None else DEFAULT_PATH

    def _load(self):
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            raise EvidenceError(f"Cannot read validation evidence {self._path}: {type(exc).__name__}") from exc
        if not isinstance(data, dict):
            raise EvidenceError(f"Invalid validation evidence object: {self._path}")
        for rec in data.values():
            if not isinstance(rec, dict):
                raise EvidenceError(f"Invalid validation evidence record: {self._path}")
            rec["status"] = {"proven": "verified", "known-bad": "revalidate"}.get(rec.get("status"), rec.get("status"))
            if rec["status"] not in ("verified", "revalidate"):
                raise EvidenceError(f"Invalid validation status: {self._path}")
        return data

    def get(self, model_id):
        return self._load().get(model_id)

    def statuses(self):
        return {key: rec["status"] for key, rec in self._load().items()}

    def record(self, model_id, status, *, note="", attempts=1, context=None, usage=None, artifact_path=None):
        if status not in ("verified", "revalidate"):
            raise ValueError("Only concluded validation verdicts may be recorded")
        with file_owner(self._path.with_suffix(self._path.suffix + ".lock"), wait_seconds=10):
            data = self._load()
            data[model_id] = dict(status=status, note=note, attempts=attempts,
                validated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                context=context, usage=usage, artifact_path=artifact_path)
            atomic_write(self._path, json.dumps(data, indent=2).encode("utf-8"))


def fresh_record(record, context, max_age_seconds, *, now=None):
    if not record or record.get("context") != context:
        return False
    try:
        timestamp = datetime.fromisoformat(record["validated_at"])
        age = ((now or datetime.now(timezone.utc)) - timestamp).total_seconds()
        return 0 <= age <= max_age_seconds
    except (ValueError, KeyError, TypeError):
        return False
