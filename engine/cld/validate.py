"""Evidence-backed headless validation: does a model actually build a trivial slice?

CLI-headless does NOT imply MODEL-headless (a model can run headless yet describe code
instead of writing files, stall, or be throttled). The only honest signal is OBSERVING a
model complete a real slice. This harness spins a throwaway real-git repo with a trivial
known-answer slice (`add(a, b)`), dispatches it to the model via the given executor, runs
the REAL acceptance test (scoped — the Bug B discipline) as the judge, and reports a
promotion: pass -> verified, fail -> revalidate, executor error -> untested.
"""

import sys
from dataclasses import dataclass, field, asdict
import json
import tempfile
from pathlib import Path

from cld.executors.base import SliceTask
from cld.judge import judge
from cld.test_run import TestRun
from cld.process import run_process
from cld.candidate import acceptance_args
from cld.executors._capture import checked
from cld.recovery import RecoverySession, atomic_write
from cld.process import process_scope

_TEST_SRC = (
    "from calc import add\n\n"
    "def test_add():\n    assert add(2, 3) == 5\n"
)


@dataclass
class ValidationResult:
    model: str
    passed: bool
    status: str          # "verified" | "revalidate" | "untested"
    attempts: int
    note: str = ""
    usage: dict = field(default_factory=dict)
    artifact_path: str | None = None
    error: str | None = None


def _pytest(workdir: str, test_path: str) -> TestRun:
    """Run ONLY the slice's acceptance test in the repo (scoped — Bug B), with a
    timeout so a hung test cannot freeze validation.

    test_path may carry a pytest selector (`::node` id or `-k "expr"`) to scope to
    a slice's own tests inside a shared file; shlex.split passes it as separate args.
    """
    target = acceptance_args(test_path)
    proc = run_process([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *target, "-q"], workdir, timeout=120,
                       env={"PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    return TestRun(proc.returncode, proc.output, log_path=proc.stdout_path,
                   timed_out=proc.error == "timeout", error=None if proc.error == "nonzero_exit" else proc.error)


def _init_repo(repo: str, git_runner) -> None:
    """Real git repo with the failing acceptance test committed (HEAD exists)."""
    Path(repo).mkdir(parents=True, exist_ok=True)
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "v@cld.test"],
        ["git", "config", "user.name", "cld-validate"],
        ["git", "config", "commit.gpgsign", "false"],
        ["git", "config", "core.hooksPath", str(Path(repo) / ".git" / "cld-empty-hooks")],
    ):
        checked(git_runner, repo, *args[1:])
    (Path(repo) / ".git" / "cld-empty-hooks").mkdir(exist_ok=True)
    (Path(repo) / "test_calc.py").write_text(_TEST_SRC, encoding="utf-8")
    (Path(repo) / "calc.py").write_text("def add(a, b):\n    return None\n", encoding="utf-8")
    (Path(repo) / ".gitignore").write_text(".cld/\n__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    checked(git_runner, repo, "add", "-A")
    checked(git_runner, repo, "commit", "-qm", "init")


def validate_model(model: str, *, executor, git_runner, base_dir: str) -> ValidationResult:
    from cld.orchestrator import deliver_slice
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="probe-", dir=base_dir))
    repo = str(directory / "repo")
    task = SliceTask("validate", "Implement add(a, b) returning a + b in calc.py.",
                     ["calc.py"], "test_calc.py")
    dispatched = []
    attempted = 0
    interrupted = None
    session = None

    class RecordingExecutor:
        def run(self, task, workdir, feedback=None):
            nonlocal attempted
            attempted += 1
            result = executor.run(task, workdir)
            dispatched.append(result)
            return result

    try:
        _init_repo(repo, git_runner)
        session = RecoverySession(repo, repo, task, str(directory / "ledger.json"), git_runner,
                                  artifact_root=directory / "artifacts")
        outcome = deliver_slice(task, executor=RecordingExecutor(), judge_fn=judge,
            workdir=repo, git_runner=git_runner, test_runner=_pytest, max_retries=0,
            model=model, evidence=session)
        last = dispatched[-1] if dispatched else None
        process = getattr(last, "process", {})
        error = process.get("error")
        if last is None or getattr(last, "ok", None) is not True:
            status, note = "untested", "executor dispatch failed (not a model verdict)"
            error = error or "dispatch_error"
        elif outcome.final and (outcome.final.test_run or {}).get("error"):
            status, note, error = "untested", "validation test process failed", "test_process_error"
        else:
            status = "verified" if outcome.accepted else "revalidate"
            note = "; ".join(outcome.final.failing_tests) if outcome.final else "acceptance failed"
        result = ValidationResult(model, outcome.accepted, status, attempted, note,
            dict(getattr(last, "token_usage", {}) or {}), str(directory), error)
    except BaseException as exc:
        from cld.process import ProcessCleanupError
        if session is not None:
            if isinstance(exc, ProcessCleanupError):
                session.save(state="cleanup_unconfirmed", error=str(exc))
            else:
                try:
                    session.failure(exc)
                except Exception as preservation_error:
                    exc.add_note(f"Recovery incomplete: {preservation_error}; retained at {directory}")
        if not isinstance(exc, Exception):
            interrupted = exc
        result = ValidationResult(model, False, "untested", attempted,
            f"validation infrastructure error: {type(exc).__name__}: {exc}",
            dict(getattr(dispatched[-1], "token_usage", {}) or {}) if dispatched else {},
            str(directory), "infrastructure_error")
    # Includes failed/inconclusive spend; T10 will aggregate it into build budgets.
    atomic_write(directory / "validation.json", json.dumps(asdict(result)).encode("utf-8"))
    if interrupted is not None:
        raise interrupted
    return result


_METERED = ("cheap-metered", "premium-metered", "metered-unknown")


@dataclass
class ResolveResult:
    spec: str
    status: str          # headless status after resolution
    validated: bool      # did a validation dispatch actually run + conclude
    proceeded: bool      # may the build proceed with this model
    note: str = ""


def _evidence_key(spec: str) -> str:
    """Store key = the model id: strip the `opencode:` executor prefix from a spec
    (`opencode:opencode/x` -> `opencode/x`); gemini specs are already ids."""
    return spec.split(":", 1)[1] if spec.startswith("opencode:") else spec


def resolve_and_validate(spec: str, *, headless_status_of, cost_class_of, validate_fn,
                         confirm_fn, output_fn, session_known_bad=None,
                         evidence_store=None, force_revalidate=False) -> ResolveResult:
    """Validate-on-demand gate: only verified/likely models pass straight through; an
    untested pick is validated against a real trivial slice first (metered models
    confirm the validation spend), and a revalidate verdict declines the pick.
    Verdicts persist in the durable evidence_store (keyed by model id) and are
    consulted before spending again; force_revalidate re-runs and refreshes."""
    skb = session_known_bad if session_known_bad is not None else set()
    if spec in skb and not force_revalidate:
        return ResolveResult(spec, "revalidate", False, False,
                             "marked revalidate this session — pick another model")

    key = _evidence_key(spec)
    if evidence_store is not None and not force_revalidate:
        rec = evidence_store.get(key)
        if rec and rec.get("status") == "verified":
            return ResolveResult(spec, "verified", False, True,
                                 f"verified on record ({rec.get('validated_at', '?')})")
        if rec and rec.get("status") == "revalidate":
            return ResolveResult(
                spec, "revalidate", False, False,
                f"marked revalidate in catalog ({rec.get('validated_at', '?')}) — "
                f"re-validate to refresh")

    status = headless_status_of(spec)
    if status in ("verified", "likely") and not force_revalidate:
        return ResolveResult(spec, status, False, True)
    if status == "revalidate" and not force_revalidate:
        skb.add(spec)
        return ResolveResult(spec, "revalidate", False, False, "marked revalidate in catalog")

    # untested -> validate before allowing the build
    if cost_class_of(spec) in _METERED:
        if not confirm_fn(f"Validating {spec} runs one real dispatch that bills real $ "
                          f"(metered model) — proceed?"):
            return ResolveResult(spec, "untested", False, False,
                                 "validation declined (cost)")

    output_fn(f"Validating headless capability for {spec} — this runs one trivial "
              f"slice (~30s), please wait...")
    vr = validate_fn(spec)
    if vr.status == "verified":
        output_fn(f"{spec}: verified headless-capable.")
        if evidence_store is not None:
            evidence_store.record(key, "verified", note=vr.note or "")
        return ResolveResult(spec, "verified", True, True)
    if vr.status == "revalidate":
        output_fn(f"{spec}: did not complete our validation slice — "
                  f"re-validate or pick another model.")
        skb.add(spec)
        if evidence_store is not None:
            evidence_store.record(key, "revalidate", note=vr.note or "failed validation")
        return ResolveResult(spec, "revalidate", True, False,
                             vr.note or "failed validation")
    output_fn(f"{spec}: couldn't validate ({vr.note}). Not a model verdict — "
              f"you may retry or pick another model.")
    return ResolveResult(spec, "untested", False, False, f"couldn't validate: {vr.note}")
