"""Durable dispatch accounting and reservation-based admission (not a token kill switch)."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import inspect
import json
import math
from pathlib import Path
from uuid import uuid4

from cld.admission import AdmissionBlocked
from cld.build_state import run_directory
from cld.ledger import StateError, now
from cld.recovery import atomic_write

_context = ContextVar("dispatch_accounting", default={})


@contextmanager
def dispatch_context(**fields):
    token = _context.set(fields)
    try:
        yield
    finally:
        _context.reset(token)


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def normalize(raw):
    raw = raw if isinstance(raw, dict) else {}
    out = {k: number(raw.get(k)) for k in ("input", "output", "cache_read", "cache_write", "total", "cost")}
    out["total_source"] = "reported" if out["total"] is not None else "unknown"
    # Cache categories are retained separately, never added to input/output: they may overlap.
    if out["total"] is None and out["input"] is not None and out["output"] is not None:
        out["total"] = out["input"] + out["output"]
        out["total_source"] = "derived_input_output"
    out["cost_source"] = "provider_reported" if out["cost"] is not None else "unknown"
    return out


def aggregate(records):
    records = list(records)
    result = {"attempts": len(records), "in_flight": sum(r["state"] == "reserved" for r in records)}
    for field in ("input", "output", "cache_read", "cache_write", "total", "cost"):
        values = [r.get("usage", {}).get(field) for r in records]
        result[field + "_known"] = sum(v for v in values if v is not None)
        result[field + "_unknown"] = sum(v is None for v in values)
        result[field] = result[field + "_known"] if not result[field + "_unknown"] else None
    return result


class Accounting:
    def __init__(self, ledger, policy=None):
        if not ledger._writing or not ledger.build:
            raise StateError("Accounting requires bound build writer ownership")
        self.ledger = ledger
        self.lock = ledger.mutation_lock
        self.directory = run_directory(ledger.build["repo"], ledger.build["run_id"]) / "usage"
        self.directory.mkdir(parents=True, exist_ok=True)
        previous = ledger.build.get("usage", {}).get("policy", {})
        self.policy = {**previous, **{k: v for k, v in (policy or {}).items() if v is not None}}
        self.policy.setdefault("unknown", "deny")
        if self.policy["unknown"] not in ("deny", "reserve"):
            raise ValueError("Unknown usage policy must be deny or reserve")
        for key in ("tokens", "cost", "attempts", "attempt_tokens", "attempt_cost"):
            value = self.policy.get(key)
            if value is not None and (number(value) is None or (key in ("tokens", "attempts", "attempt_tokens") and type(value) is not int)):
                raise ValueError(f"Invalid budget {key}")
        for limit, allowance in (("tokens", "attempt_tokens"), ("cost", "attempt_cost")):
            if self.policy.get(limit) is not None and (self.policy.get(allowance) is None or self.policy[allowance] <= 0):
                raise ValueError(f"Budget {limit} requires explicit {allowance} reservation")
        self.broken = None
        self.records = {}
        for path in self.directory.glob("attempt-*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if record["id"] != path.stem[8:] or record["state"] not in ("reserved", "finished", "interrupted"):
                    raise ValueError("invalid attempt identity/state")
                if (not isinstance(record.get("model"), str) or not isinstance(record.get("slice_id"), str)
                        or record.get("kind") not in ("production", "validation")
                        or not isinstance(record.get("usage"), dict) or not isinstance(record.get("reservation"), dict)):
                    raise ValueError("invalid attempt payload")
                for field in ("input", "output", "cache_read", "cache_write", "total", "cost"):
                    if field not in record["usage"] or (record["usage"][field] is not None and number(record["usage"][field]) is None):
                        raise ValueError("invalid usage value")
                for value in record["reservation"].values():
                    if value is not None and number(value) is None:
                        raise ValueError("invalid reservation")
                if record["state"] == "reserved":
                    record.update(state="interrupted", ended_at=now(), error="previous invocation ended without completion")
                    self._write(record)
                self.records[record["id"]] = record
            except (ValueError, KeyError, TypeError, OSError) as exc:
                raise StateError(f"Invalid usage journal: {path}") from exc
        if not ledger.build.get("usage"):
            # Old ledgers only held the final attempt. Never call it a complete history.
            import hashlib
            for sid, entry in ledger.entries.items():
                if entry.attempts or entry.commit:
                    ident = hashlib.sha256(("legacy:" + sid).encode()).hexdigest()[:32]
                    if ident not in self.records:
                        record = dict(id=ident, model=entry.model or "unknown", slice_id=sid,
                            kind="production", state="interrupted", usage=normalize({}),
                            reservation={}, legacy_final_usage=entry.token_usage,
                            error="Pre-T10 attempt history unavailable")
                        self._write(record)
                        self.records[ident] = record
        self.blocked = None
        self._publish()

    def _write(self, record):
        atomic_write(self.directory / ("attempt-" + record["id"] + ".json"),
                     json.dumps(record, allow_nan=False).encode("utf-8"))

    def _publish(self):
        summary = aggregate(self.records.values())
        summary.update(policy=self.policy, blocked=self.blocked,
            active=[{k: r.get(k) for k in ("id", "model", "slice_id", "kind", "started_at", "reservation")} for r in self.records.values() if r["state"] == "reserved"],
            by_model={m: aggregate(r for r in self.records.values() if r["model"] == m)
                      for m in {r["model"] for r in self.records.values()}},
            validation=aggregate(r for r in self.records.values() if r["kind"] == "validation"),
            by_slice={sid: aggregate(r for r in self.records.values() if r["kind"] == "production" and r["slice_id"] == sid)
                      for sid in {r["slice_id"] for r in self.records.values() if r["kind"] == "production"}})
        for field, allowance in (("total", "attempt_tokens"), ("cost", "attempt_cost")):
            summary[field + "_reserved"] = sum(r["reservation"].get(allowance) or 0 for r in self.records.values() if r["state"] == "reserved")
            limit = self.policy.get("tokens" if field == "total" else "cost")
            summary[field + "_overrun"] = max(0, summary[field + "_known"] - limit) if limit is not None else None
        summary["attempt_overruns"] = sum(any(
            r.get("usage", {}).get(field) is not None and r["reservation"].get(allowance) is not None
            and r["usage"][field] > r["reservation"][allowance]
            for field, allowance in (("total", "attempt_tokens"), ("cost", "attempt_cost"))) for r in self.records.values())
        self.ledger.build["usage"] = summary
        for sid, entry in self.ledger.entries.items():
            rows = [r for r in self.records.values() if r["kind"] == "production" and r["slice_id"] == sid]
            if rows:
                totals = aggregate(rows)
                entry.token_usage = {k: totals[k] for k in ("input", "output", "cache_read", "cache_write", "total")}
                entry.cost = totals["cost"]
        try:
            self.ledger.save()
        except (OSError, StateError, ValueError, TypeError) as exc:
            self.broken = str(exc)
            raise

    def _block(self, reason):
        self.blocked = reason
        self._publish()
        raise AdmissionBlocked(reason)

    def reserve(self, *, model, slice_id, kind, identity):
        with self.lock:
            if self.broken:
                raise AdmissionBlocked("Usage persistence failed; resume to reconcile: " + self.broken)
            if self.policy.get("attempts") is not None and any("legacy_final_usage" in r for r in self.records.values()):
                self._block("Pre-T10 attempt count is incomplete; start a new build for an attempt budget")
            if self.policy.get("attempts") is not None and len(self.records) >= self.policy["attempts"]:
                self._block("Attempt budget exhausted")
            for field, limit_key, allowance in (("total", "tokens", "attempt_tokens"), ("cost", "cost", "attempt_cost")):
                limit = self.policy.get(limit_key)
                if limit is None:
                    continue
                charge = 0
                for r in self.records.values():
                    value = r.get("usage", {}).get(field)
                    if value is None:
                        if r["state"] != "reserved" and self.policy["unknown"] == "deny":
                            self._block(f"Unknown {field} from prior attempt blocks budget admission")
                        value = r["reservation"].get(allowance)
                        if value is None:
                            self._block(f"Unknown {field} has no recorded reservation")
                    charge += value
                if charge + self.policy[allowance] > limit:
                    self._block(f"{limit_key} budget exhausted including in-flight reservations")
            for field, allowance in (("total", "attempt_tokens"), ("cost", "attempt_cost")):
                ceiling = self.policy.get(allowance)
                if ceiling is not None and self.policy["unknown"] == "deny" and any(r["state"] != "reserved" and r.get("usage", {}).get(field) is None for r in self.records.values()):
                    self._block(f"Unknown per-attempt {field}; explicit reserve policy required")
                if ceiling is not None and any((r.get("usage", {}).get(field) or 0) > ceiling for r in self.records.values()):
                    self._block(f"Observed per-attempt {field} overrun; explicitly revise admission allowance before continuing")
            self.blocked = None
            record = dict(id=uuid4().hex, model=model, provider=model.split(":", 1)[0],
                effort=model.rsplit("@", 1)[1] if "@" in model else None,
                slice_id=slice_id, kind=kind, cli_identity=identity, cli_version=(identity or {}).get("cli_fingerprint"),
                cli_version_source="content_fingerprint", state="reserved", started_at=now(),
                reservation={k: self.policy.get(k) for k in ("attempt_tokens", "attempt_cost")},
                dispatch=deepcopy(_context.get()), policy=deepcopy(self.policy), usage=normalize({}), raw_usage={})
            self._write(record)  # Durable reservation BEFORE external execution.
            self.records[record["id"]] = record
            self._publish()
            return record["id"]

    def finish(self, ident, result=None, error=None):
        with self.lock:
            record = deepcopy(self.records[ident])
            raw = getattr(result, "token_usage", {})
            record.update(state="interrupted" if error else "finished", ended_at=now(),
                usage=normalize(raw), raw_usage=raw if isinstance(raw, dict) else {},
                provider_usage=getattr(result, "usage_raw", {}), error=error,
                process=getattr(result, "process", {}))
            if record["provider"] == "cursor" and isinstance(record["provider_usage"], dict) and "inputTokens" in record["provider_usage"] and "outputTokens" in record["provider_usage"]:
                record["usage"]["total_source"] = "derived_input_output"
            self._write(record)
            self.records[ident] = record
            self._publish()

    def wrap(self, executor, model, *, kind="production", identity=None):
        if getattr(executor, "accounting_owner", None) is self:
            return executor
        owner = self
        class MeteredExecutor:
            accounting_owner = owner
            def run(self, task, workdir, feedback=None):
                try:
                    ident = owner.reserve(model=model, slice_id=task.id, kind=kind, identity=identity)
                except (OSError, StateError, ValueError, TypeError) as exc:
                    owner.broken = str(exc)
                    raise AdmissionBlocked("Usage reservation failed; resume to reconcile") from exc
                try:
                    try:
                        inspect.signature(executor.run).bind(task, workdir, feedback=feedback)
                        accepts = True
                    except TypeError:
                        accepts = False
                    result = executor.run(task, workdir, feedback=feedback) if accepts else executor.run(task, workdir)
                except BaseException as exc:
                    try:
                        owner.finish(ident, error=type(exc).__name__)
                    except Exception as persistence_error:
                        owner.broken = str(persistence_error)
                        if isinstance(exc, Exception):
                            raise AdmissionBlocked("Usage persistence failed after executor error; resume to reconcile") from persistence_error
                        exc.add_note("Usage completion could not be saved; reservation retained")
                    raise
                try:
                    owner.finish(ident, result)
                except (OSError, StateError, ValueError, TypeError) as exc:
                    owner.broken = str(exc)
                    raise AdmissionBlocked("Usage completion persistence failed; resume to reconcile") from exc
                return result
        return MeteredExecutor()
