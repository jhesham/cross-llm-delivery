"""One noninteractive model admission policy for defaults, tags and rungs."""
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from cld.evidence import EvidenceError, fresh_record
from cld.models import resolve_spec, model_policy
from cld.validate import ResolveResult, ValidationResult, _evidence_key
from cld.recovery import atomic_write


class AdmissionBlocked(ValueError):
    pass


def writable_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=path) as stream:
        stream.write(b"cld preflight")
        stream.flush()
        os.fsync(stream.fileno())


def file_identity(path):
    path = Path(path)
    try:
        path.stat()
    except FileNotFoundError:
        return {"path": str(path.absolute()), "missing": True}
    if not path.is_file():
        raise ValueError(f"Validation context input is not a file: {path}")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path.resolve()), "sha256": digest}


def validation_context(spec, *, cli_paths, config_paths=(), extra="", repo=""):
    # No environment values or config contents enter the stored diagnostic record.
    data = dict(contract=1, spec=spec, cli=[file_identity(p) for p in cli_paths],
        config=[file_identity(p) for p in config_paths], extra=extra,
        repo=str(Path(repo).resolve()), environment=sorted(os.environ.items()))
    return {"contract": 1, "cli_fingerprint": hashlib.sha256(json.dumps(data["cli"], sort_keys=True).encode("utf-8")).hexdigest(), "fingerprint": hashlib.sha256(
        json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()}


class Admission:
    def __init__(self, *, store, validate_fn, context_of, policy="deny", force=False,
                 max_age_seconds=30 * 86400, policy_of=model_policy, report_path=None):
        if policy not in ("deny", "unmetered", "allow"):
            raise ValueError("Unknown validation spend policy")
        if not math.isfinite(max_age_seconds) or max_age_seconds < 0:
            raise ValueError("Validation evidence age must be finite and nonnegative")
        self.store, self.validate_fn, self.context_of = store, validate_fn, context_of
        self.policy, self.force, self.max_age_seconds = policy, force, max_age_seconds
        self.policy_of, self.report_path = policy_of, report_path
        self.cache, self.records = {}, []

    def _record(self, result, **details):
        self.records.append({**asdict(result), **details})
        if self.report_path is not None:
            atomic_write(Path(self.report_path), json.dumps(dict(schema_version=1,
                validation_policy=self.policy, force_revalidate=self.force,
                max_age_seconds=self.max_age_seconds, models=self.records), indent=2).encode("utf-8"))
        return result

    def check(self, value, *, execute=True):
        spec, _, _ = resolve_spec(value)
        context = self.context_of(spec)
        cache_key = (spec, json.dumps(context, sort_keys=True))
        if cache_key in self.cache:
            return self.cache[cache_key]
        key = _evidence_key(spec)
        try:
            rec = self.store.get(key)
        except EvidenceError as exc:
            return self._record(ResolveResult(spec, "blocked", False, False, str(exc)))
        status, cost = self.policy_of(spec)
        if not self.force:
            if rec and rec.get("status") == "revalidate":
                return self._record(ResolveResult(spec, "revalidate", False, False,
                    "Failed validation evidence; explicit --revalidate-models is required"))
            if fresh_record(rec, context, self.max_age_seconds):
                result = ResolveResult(spec, "verified", False, True, "current validation evidence")
                self.cache[cache_key] = result
                return self._record(result, context=context)
            if status == "revalidate":
                return self._record(ResolveResult(spec, "revalidate", False, False,
                    "Catalog marks this model failed; explicit --revalidate-models is required"))
        # Static catalog claims do not prove this CLI/configuration can execute.
        if self.policy == "deny" or (self.policy == "unmetered" and cost not in ("free", "flat")):
            return self._record(ResolveResult(spec, "blocked", False, False,
                "Validation requires recorded --validation-policy unmetered or allow; unknown costs require allow"), context=context)
        if not execute:
            return ResolveResult(spec, "validation_required", False, True)
        verdict = self.validate_fn(spec)
        if not isinstance(verdict, ValidationResult):
            return self._record(ResolveResult(spec, "blocked", False, False,
                "Invalid validation result; production dispatch refused"))
        passed = verdict.passed is True and verdict.status == "verified"
        status = verdict.status if verdict.status in ("verified", "revalidate", "untested") else "untested"
        if status == "verified" and not passed:
            status = "untested"
        if status in ("verified", "revalidate"):
            self.store.record(key, status, note=verdict.note, attempts=verdict.attempts,
                context=context, usage=verdict.usage, artifact_path=verdict.artifact_path)
        result = ResolveResult(spec, status, verdict.attempts > 0, passed, verdict.note)
        self.cache[cache_key] = result
        return self._record(result, context=context, usage=verdict.usage,
                            artifact_path=verdict.artifact_path, error=verdict.error)
