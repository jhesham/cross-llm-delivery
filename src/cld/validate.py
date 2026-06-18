"""Evidence-backed headless validation: does a model actually build a trivial slice?

CLI-headless does NOT imply MODEL-headless (a model can run headless yet describe code
instead of writing files, stall, or be throttled). The only honest signal is OBSERVING a
model complete a real slice. This harness spins a throwaway real-git repo with a trivial
known-answer slice (`add(a, b)`), dispatches it to the model via the given executor, runs
the REAL acceptance test (scoped — the Bug B discipline) as the judge, and reports a
promotion: pass -> verified, fail -> revalidate, executor error -> untested.
"""

import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cld.executors.base import SliceTask
from cld.judge import judge

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


def _pytest(workdir: str, test_path: str) -> str:
    """Run ONLY the slice's acceptance test in the repo (scoped — Bug B), with a
    timeout so a hung test cannot freeze validation.

    test_path may carry a pytest selector (`::node` id or `-k "expr"`) to scope to
    a slice's own tests inside a shared file; shlex.split passes it as separate args.
    """
    target = shlex.split(test_path) if test_path else []
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *target, "-q"],
            cwd=workdir, capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        return (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return "1 failed in 120s (timeout)"


def _init_repo(repo: str, git_runner) -> None:
    """Real git repo with the failing acceptance test committed (HEAD exists)."""
    Path(repo).mkdir(parents=True, exist_ok=True)
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "v@cld.test"],
        ["git", "config", "user.name", "cld-validate"],
        ["git", "config", "commit.gpgsign", "false"],
    ):
        git_runner(args, repo)
    (Path(repo) / "test_calc.py").write_text(_TEST_SRC, encoding="utf-8")
    git_runner(["git", "add", "-A"], repo)
    git_runner(["git", "commit", "-qm", "init"], repo)


def validate_model(model: str, *, executor, git_runner, base_dir: str) -> ValidationResult:
    repo = str(Path(base_dir) / "validate-repo")
    _init_repo(repo, git_runner)

    task = SliceTask(
        id="validate",
        brief="Implement add(a, b) returning a + b in calc.py.",
        files=["calc.py"],
        acceptance_test_path="test_calc.py",
    )
    try:
        result = executor.run(task, repo)
    except Exception as exc:  # executor blew up -> untested, not a model-failure verdict
        return ValidationResult(model, False, "untested", 0, note=f"executor error: {exc}")
    if not result.ok:
        # the dispatch itself failed (CLI/model error) — no code was attempted, so
        # this is NOT evidence the model writes bad code (found live: kimi-k2.6)
        return ValidationResult(model, False, "untested", 1,
                                note="executor dispatch failed (not a model verdict)")

    jr = judge(
        result.files_changed, task.files,
        run_tests=lambda: _pytest(repo, task.acceptance_test_path),
    )
    if jr.passed:
        return ValidationResult(model, True, "verified", 1)
    return ValidationResult(
        model, False, "revalidate", 1,
        note="; ".join(jr.failing_tests) or "acceptance test failed",
    )


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
    if spec in skb:
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
    if status in ("verified", "likely"):
        return ResolveResult(spec, status, False, True)
    if status == "revalidate":
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
