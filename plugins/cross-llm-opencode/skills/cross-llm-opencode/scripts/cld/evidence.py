"""Durable validation-evidence store (supersedes session-only revalidate marks,
user-directed 2026-06-13).

Validation verdicts cost real time/tokens — they are evidence worth keeping. This
store persists CONCLUDED verdicts (verified / revalidate) per model id in a small JSON
file, with timestamps, so a verdict survives across sessions. The blacklist risk
that motivated session-only is handled differently: records carry their date, and
`resolve_and_validate(force_revalidate=True)` re-runs validation and overwrites the
record — a transient failure is one re-validation away from being cleared.

Inconclusive outcomes (untested / executor errors) are never recorded.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path.home() / ".cld" / "validation-evidence.json"


class EvidenceStore:
    """JSON-file-backed verdict store. Keyed by MODEL ID (e.g. `opencode/kimi-k2.6`,
    `gemini:gemini-3.1-pro-preview`) — not the executor spec. Never raises on a
    missing or corrupt file (degrades to empty)."""

    def __init__(self, path=None):
        self._path = Path(path) if path is not None else DEFAULT_PATH

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            _MIGRATE = {"proven": "verified", "known-bad": "revalidate"}
            for rec in data.values():
                if isinstance(rec, dict) and rec.get("status") in _MIGRATE:
                    rec["status"] = _MIGRATE[rec["status"]]
            return data
        except Exception:
            return {}

    def get(self, model_id: str) -> dict | None:
        """The recorded verdict for a model id, or None."""
        return self._load().get(model_id)

    def statuses(self) -> dict[str, str]:
        """{model_id: status} mapping — the overlay for recommend/browse_models."""
        return {k: v.get("status") for k, v in self._load().items()
                if isinstance(v, dict) and v.get("status")}

    def record(self, model_id: str, status: str, *, note: str = "", attempts: int = 1) -> None:
        """Record (or overwrite) a concluded verdict, timestamped UTC."""
        data = self._load()
        data[model_id] = {
            "status": status,
            "note": note,
            "attempts": attempts,
            "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
