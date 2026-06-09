import json
import os
import tempfile
from dataclasses import dataclass

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
                )
        except Exception:
            pass
        return ledger

    @property
    def entries(self) -> dict[str, LedgerEntry]:
        return self._entries

    def get(self, slice_id: str) -> LedgerEntry | None:
        return self._entries.get(slice_id)

    def set(self, slice_id: str, *, status=None, commit=None, attempts=None):
        if slice_id not in self._entries:
            self._entries[slice_id] = LedgerEntry(slice_id=slice_id)
        
        entry = self._entries[slice_id]
        if status is not None:
            entry.status = status
        if commit is not None:
            entry.commit = commit
        if attempts is not None:
            entry.attempts = attempts

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
