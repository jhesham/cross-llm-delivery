import json
import os
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
import threading
from dataclasses import asdict, fields

from cld.locking import file_owner
from cld.recovery import atomic_write

SCHEMA_VERSION = 2


class StateError(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def resolve_ledger(repo, explicit=None):
    return str(Path(explicit).resolve() if explicit is not None else Path(repo).resolve() / ".cld-ledger.json")

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
    collection: dict = field(default_factory=dict)
    recovery_path: str | None = None
    worktree_path: str | None = None
    fingerprint: str | None = None
    updated_at: str | None = None
    history: list = field(default_factory=list)

class Ledger:
    def __init__(self, path: str):
        self.path = str(Path(path).resolve())
        self._entries: dict[str, LedgerEntry] = {}
        self.build = None
        self.legacy = False
        self._expected = None
        self._writing = False
        self._writer_thread = None

    @classmethod
    def load(cls, path: str) -> "Ledger":
        ledger = cls(path)
        try:
            raw = Path(ledger.path).read_bytes()
        except FileNotFoundError:
            return ledger
        except OSError as exc:
            raise StateError(f"Cannot read ledger {ledger.path}: {exc}") from exc
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("expected an object")
            if "schema_version" in data:
                if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
                    raise ValueError("unsupported ledger schema")
                entries = data["entries"]
                ledger.build = data["build"]
                if ledger.build is not None:
                    from cld.build_state import validate_build
                    validate_build(ledger.build)
                    if ledger.build["ledger_path"] != ledger.path:
                        raise ValueError("ledger path identity mismatch; use the original ledger location")
            else:
                entries = data
                ledger.legacy = True
            if not isinstance(entries, dict):
                raise ValueError("invalid entries")
            names = {f.name for f in fields(LedgerEntry)} - {"slice_id"}
            for sid, values in entries.items():
                if not isinstance(sid, str) or not sid or not isinstance(values, dict):
                    raise ValueError("invalid slice entry")
                if set(values) - names:
                    raise ValueError(f"unknown fields in slice {sid}")
                entry = LedgerEntry(slice_id=sid, **values)
                if (entry.status not in {PENDING, IN_PROGRESS, DONE, FAILED, "needs_repair", "deferred", "integrated"}
                        or type(entry.attempts) is not int or entry.attempts < 0
                        or not isinstance(entry.collection, dict) or not isinstance(entry.token_usage, dict)
                        or not isinstance(entry.history, list)
                        or not all(isinstance(item, dict) for item in entry.history)):
                    raise ValueError(f"invalid slice state: {sid}")
                ledger._entries[sid] = entry
            ledger._expected = raw
        except (ValueError, TypeError, KeyError) as exc:
            raise StateError(f"Invalid ledger {ledger.path}: {exc}; original file retained") from exc
        return ledger

    @contextmanager
    def writer(self, *, refresh=False):
        if self._writing:
            if self._writer_thread != threading.get_ident():
                raise StateError("Writer context belongs to another thread")
            yield self
            return
        with file_owner(self.path + ".lock"):
            if refresh:
                disk = Ledger.load(self.path)
                if self._expected != disk._expected:
                    if self._entries or self.build is not None:
                        raise StateError(f"Ledger changed since load; reload {self.path}")
                    self._entries, self.build, self.legacy = disk.entries, disk.build, disk.legacy
                    self._expected = disk._expected
            self._writing, self._writer_thread = True, threading.get_ident()
            try:
                atomic_write(Path(self.path + ".owner.json"), json.dumps(
                    dict(pid=os.getpid(), acquired_at=now(), ledger=self.path,
                         run_id=(self.build or {}).get("run_id"))).encode("utf-8"))
                yield self
            finally:
                self._writing, self._writer_thread = False, None

    def bind(self, repo, tasks, runner, **options):
        from cld.build_state import bind_build
        if not self._writing:
            raise StateError("Build binding requires writer ownership")
        return bind_build(self, repo, tasks, runner, **options)

    @property
    def entries(self) -> dict[str, LedgerEntry]:
        return self._entries

    def get(self, slice_id: str) -> LedgerEntry | None:
        return self._entries.get(slice_id)

    def set(self, slice_id: str, *, status=None, commit=None, attempts=None,
            model=None, effort=None, token_usage=None, cost=None,
            complexity=None, chosen_by=None, final_rung=None, intervened=None,
            collection=None, recovery_path=None, worktree_path=None):
        if slice_id not in self._entries:
            self._entries[slice_id] = LedgerEntry(slice_id=slice_id)
        entry = self._entries[slice_id]
        entry.updated_at = now()
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
        if collection is not None:
            entry.collection = collection
        if recovery_path is not None:
            entry.recovery_path = recovery_path
        if worktree_path is not None:
            entry.worktree_path = worktree_path

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
        if not self._writing:
            with self.writer():
                return self.save()
        if self.legacy:
            raise StateError(f"Legacy ledger requires explicit --migrate-ledger: {self.path}")
        try:
            actual = Path(self.path).read_bytes()
        except FileNotFoundError:
            actual = None
        if actual != self._expected:
            raise StateError(f"Ledger changed since load; reload {self.path}")
        build = {**self.build, "updated_at": now()} if self.build is not None else None
        entries = {sid: {k: v for k, v in asdict(entry).items() if k != "slice_id"}
                   for sid, entry in self.entries.items()}
        raw = json.dumps(dict(schema_version=SCHEMA_VERSION, build=build, entries=entries),
                         indent=2, ensure_ascii=True).encode("utf-8")
        atomic_write(Path(self.path), raw)
        self._expected, self.build = raw, build
