import json
import os
import tempfile
from dataclasses import dataclass, field

PENDING = "pending"
IN_PROGRESS = "in_progress"
DONE = "done"
FAILED = "failed"

@dataclass
class LedgerEntry:
    slice_id: str
    status: str = PENDING
    commit: str | None = None
    attempts: int = 0
    model: str | None = None
    effort: str | None = None
    token_usage: dict = field(default_factory=dict)
    cost: float | None = None
    complexity: str | None = None
    chosen_by: str | None = None
    final_rung: str | None = None
    intervened: bool = False

class Ledger:
    def __init__(self, path: str):
        self.path = path
        self._entries: dict[str, LedgerEntry] = {}

    @classmethod
    def load(cls, path: str) -> "Ledger":
        ledger = cls(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for slice_id, entry_data in data.items():
                ledger._entries[slice_id] = LedgerEntry(
                    slice_id=slice_id,
                    status=entry_data.get("status", PENDING),
                    commit=entry_data.get("commit", None),
                    attempts=entry_data.get("attempts", 0),
                    model=entry_data.get("model"),
                    effort=entry_data.get("effort"),
                    token_usage=entry_data.get("token_usage", {}) or {},
                    cost=entry_data.get("cost"),
                    complexity=entry_data.get("complexity"),
                    chosen_by=entry_data.get("chosen_by"),
                    final_rung=entry_data.get("final_rung"),
                    intervened=entry_data.get("intervened", False),
                )
        except Exception:
            pass
        return ledger

    @property
    def entries(self) -> dict[str, LedgerEntry]:
        return self._entries

    def get(self, slice_id: str) -> LedgerEntry | None:
        return self._entries.get(slice_id)

    def set(self, slice_id: str, *, status=None, commit=None, attempts=None,
            model=None, effort=None, token_usage=None, cost=None,
            complexity=None, chosen_by=None, final_rung=None, intervened=None):
        if slice_id not in self._entries:
            self._entries[slice_id] = LedgerEntry(slice_id=slice_id)
        entry = self._entries[slice_id]
        if status is not None:
            entry.status = status
        if commit is not None:
            entry.commit = commit
        if attempts is not None:
            entry.attempts = attempts
        if model is not None:
            entry.model = model
        if effort is not None:
            entry.effort = effort
        if token_usage is not None:
            entry.token_usage = token_usage
        if cost is not None:
            entry.cost = cost
        if complexity is not None:
            entry.complexity = complexity
        if chosen_by is not None:
            entry.chosen_by = chosen_by
        if final_rung is not None:
            entry.final_rung = final_rung
        if intervened is not None:
            entry.intervened = intervened

    def mark_attempt(self, slice_id: str):
        if slice_id not in self._entries:
            self._entries[slice_id] = LedgerEntry(slice_id=slice_id)
        self._entries[slice_id].attempts += 1

    def pending_ids(self) -> list[str]:
        return [
            entry.slice_id
            for entry in self._entries.values()
            if entry.status != DONE
        ]

    def is_done(self, slice_id: str) -> bool:
        entry = self.get(slice_id)
        if not entry:
            return False
        return entry.status == DONE

    def save(self):
        directory = os.path.dirname(self.path)
        if not directory:
            directory = "."

        data = {
            slice_id: {
                "status": entry.status,
                "commit": entry.commit,
                "attempts": entry.attempts,
                "model": entry.model,
                "effort": entry.effort,
                "token_usage": entry.token_usage,
                "cost": entry.cost,
                "complexity": entry.complexity,
                "chosen_by": entry.chosen_by,
                "final_rung": entry.final_rung,
                "intervened": entry.intervened,
            }
            for slice_id, entry in self._entries.items()
        }

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            os.replace(temp_path, self.path)
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise
