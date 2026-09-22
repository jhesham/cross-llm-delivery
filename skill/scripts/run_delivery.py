#!/usr/bin/env python
"""Drive a cross-llm-delivery run from a plan file.

Assembles the cld engine end-to-end:
  load_slices(plan.md) -> get_executor(<provider>) -> run_plan_parallel(...)
with a real git runner (for per-slice worktree isolation) and a real pytest-based
judge. Progress is persisted to a JSON ledger so the run is resumable.

Usage:
    python run_delivery.py <plan.md> [--repo <dir>] [--ledger <path>]
                           [--workers N] [--dry-run]

The plan is markdown with one block per slice (see cld.plan.slice.load_slices):

    ## SLICE: T1
    brief: <natural-language task / spec>
    files: src/a.py, tests/test_a.py
    acceptance_test_path: tests/test_a.py
    deps:

Exit 3 means verified integration is complete; 6 means accepted work awaits integration.
Exit 0 means more work remains; 2 is failure/defer, 4 repair, and 5 invalid state.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Self-contained-skill shim: when this driver is VENDORED into a generated skill,
# the engine (`cld`) and providers (`cld_providers`) are vendored beside it in the
# same `scripts/` dir. Putting that dir on sys.path lets `import cld` resolve with
# NO pip install. Harmless in the monorepo (where `cld` is already importable via
# the engine pythonpath) -- it just prepends this dir, which has no `cld` there.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Monorepo shim: when run from a fresh clone (skill/scripts/run_delivery.py) without
# `pip install -e .`, the engine lives at <repo>/engine — put it on sys.path too so the
# documented `python skill/scripts/run_delivery.py ... --dry-run` works out of the box.
_engine_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "engine")
if os.path.isdir(os.path.join(_engine_dir, "cld")):
    sys.path.insert(1, _engine_dir)

from cld.providers_api import load_providers, get_provider, all_providers, default_workhorse
from cld.executors import get_executor
from cld.judge import judge
from cld.evidence import EvidenceError
from cld.test_run import TestRun
from cld.process import run_process
from cld.candidate import acceptance_args
from cld.executors._capture import CaptureError
from cld.ledger import Ledger, DONE, StateError, resolve_ledger
from cld.locking import OwnerBusy
from cld.build_state import run_directory
from cld.orchestrator import run_plan_parallel
from cld.plan.slice import load_slices, PlanError

# Load all providers at startup so the registry is populated before any
# call to get_executor / get_provider / KNOWN_EXECUTORS.
load_providers()

# ---------------------------------------------------------------------------
# KNOWN_EXECUTORS: dynamic shim (registry-backed) for backward-compat callers
# within this module (e.g. _parse_name_model, _provider_of_spec).
# ---------------------------------------------------------------------------
KNOWN_EXECUTORS = tuple(p.name for p in all_providers())


def _default_spec() -> str:
    """The default executor SPEC when the user names none — the engine's current default
    workhorse (provider-blind). Replaces the old hardcoded ``"gemini"`` defaults, which
    pointed at a provider that has since been removed (a defaulted/empty executor would
    otherwise resolve to a deleted provider and crash get_executor)."""
    return default_workhorse()


def _default_provider() -> str:
    """The default executor NAME (the default spec's provider prefix), e.g. 'antigravity'."""
    spec = _default_spec()
    return spec.split(":", 1)[0] if ":" in spec else spec


def _events_path(repo_dir: str, ledger=None) -> str:
    """Run-scoped stream; legacy fallback is read-only."""
    ledger = ledger or Ledger.load(resolve_ledger(repo_dir))
    if ledger.build:
        if ledger.build["repo"] != os.path.realpath(repo_dir):
            raise StateError("Ledger belongs to another repository")
        return str(run_directory(repo_dir, ledger.build["run_id"]) / "events.jsonl")
    return os.path.join(os.path.abspath(repo_dir), ".cld", "events.jsonl")


def _read_event_stream(repo_dir: str, ledger=None) -> "list":
    """Load .cld/events.jsonl into a list of records (skips blank/torn lines). [] if absent."""
    import json
    events = []
    try:
        with open(_events_path(repo_dir, ledger), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass  # a final line may be torn mid-flush; skip it
    except FileNotFoundError:
        pass
    return events


def _run_id_from_stream(events_path: str) -> "str | None":
    """Read the stable run_id from an existing event stream (the run_start line),
    so every --step invocation of one build shares it. None if unreadable."""
    import json
    try:
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                if isinstance(d, dict) and d.get("run_id"):
                    return d["run_id"]
    except Exception:
        pass
    return None


def _install_telemetry(repo_dir: str, ledger: Ledger, plan_path: str, default_spec: str) -> str:
    """Append to the bound run; a missing/corrupt ledger never truncates history."""
    from cld import telemetry
    if not ledger.build or not ledger._writing:
        raise StateError("Telemetry setup requires a bound build and writer ownership")
    events_path = _events_path(repo_dir, ledger)
    os.makedirs(os.path.dirname(events_path), exist_ok=True)
    fresh = not os.path.exists(events_path) or os.path.getsize(events_path) == 0
    telemetry.set_run_id(ledger.build["run_id"])
    jsonl = telemetry.JsonlSink(events_path)
    otel = _maybe_otel_sink()
    telemetry.set_sink(telemetry.MultiSink([jsonl, otel]) if otel is not None else jsonl)
    if fresh:
        telemetry.emit("run_start", plan=os.path.basename(plan_path), executor_default=default_spec)
    return events_path



def _dispatch_needed(slices, ledger):
    return any(not ledger.is_done(s.id) and (ledger.get(s.id) is None or ledger.get(s.id).status != "needs_repair") for s in slices)


def _record_operation(args, ledger, operation, code):
    from cld import telemetry
    labels = {0: "pending", 2: "failed", 3: "passed", 4: "needs_repair", 5: "blocked", 6: "integration_required"}
    try:
        _install_telemetry(args.repo, ledger, args.plan, args.executor or _default_spec())
        telemetry.emit("operation_done", operation=operation, gate=labels[code], gate_code=code)
        if code == 3:
            telemetry.emit("run_done", gate="passed", gate_code=3)
    finally:
        telemetry.set_sink(None)
        telemetry.set_run_id(None)


def _render_build_status(repo, ledger):
    from cld.status import render_status
    if ledger.build and ledger.build.get("usage") is not None:
        from cld.status import render_accounting_status
        return render_accounting_status(ledger)
    events = _read_event_stream(repo, ledger)
    if ledger.build is None:
        return render_status(events)
    from collections import Counter
    from cld.integration import pending_integration
    counts = Counter(e.status for e in ledger.entries.values())
    if counts["needs_repair"] or ledger.build.get("integration_failure"):
        gate = "needs_repair"
    elif counts["failed"]:
        gate = "failed"
    elif pending_integration(ledger):
        gate = "integration_required"
    elif counts["integrated"] == len(ledger.entries) and ledger.build.get("integration_proof"):
        gate = "passed"
    else:
        gate = "pending"
    events = [*events, {"type": "build_state", "gate": gate}]
    return render_status(events) + "\nRECORDED STATE: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def _layer_gate(result) -> str:
    """Coarse gate label for a layer/run result, ASCII-safe."""
    if getattr(result, "blocked", None):
        return "blocked"
    if getattr(result, "needs_repair", None) or getattr(result, "integration_error", None):
        return "needs_repair"
    if getattr(result, "failed", None) or getattr(result, "deferred", None):
        return "failed"
    if getattr(result, "integration_required", None):
        return "integration_required"
    return "passed"


def _otel_target_from_env(env=None):
    """Resolve (endpoint, headers) for OTLP trace export from env, or None. Encodes the
    Langfuse keys-convenience. Pure (env in -> target out) so it's unit-testable.

    - OTEL_EXPORTER_OTLP_ENDPOINT (+ optional OTEL_EXPORTER_OTLP_HEADERS "k=v,k=v") wins.
    - else LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY -> {LANGFUSE_HOST|cloud}/api/public/otel/v1/traces
      with an `Authorization: Basic base64(pk:sk)` header (Langfuse is OTLP-native).
    """
    import base64
    env = env if env is not None else os.environ
    headers = {}
    raw = env.get("OTEL_EXPORTER_OTLP_HEADERS")
    if raw:
        for pair in raw.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                headers[k.strip()] = v.strip()
    endpoint = env.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        pk, sk = env.get("LANGFUSE_PUBLIC_KEY"), env.get("LANGFUSE_SECRET_KEY")
        if pk and sk:
            host = env.get("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
            endpoint = f"{host}/api/public/otel/v1/traces"
            token = base64.b64encode(f"{pk}:{sk}".encode()).decode()
            headers.setdefault("Authorization", f"Basic {token}")
    if not endpoint:
        return None
    return endpoint, headers


def _maybe_otel_sink():
    """Build an OtelSink wired to the env-configured OTLP endpoint, or None. Guarded:
    a missing target, SDK, or exporter => None (JSONL stays the only sink). Never raises."""
    target = _otel_target_from_env()
    if target is None:
        return None
    endpoint, headers = target
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from cld.telemetry import OtelSink
        provider = TracerProvider()
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers or None)))
        return OtelSink(tracer=provider.get_tracer("cld"), close_fn=provider.shutdown)
    except Exception:
        return None


def _otel_status_line() -> str:
    """One-line OTLP export status for the build header."""
    target = _otel_target_from_env()
    if target is None:
        return ("otel: OFF (set OTEL_EXPORTER_OTLP_ENDPOINT, or LANGFUSE_PUBLIC_KEY+"
                "LANGFUSE_SECRET_KEY; see references/observability.md)")
    try:
        import opentelemetry.sdk  # noqa: F401
        import opentelemetry.exporter.otlp.proto.http  # noqa: F401
        return f"otel: ON -> {target[0]}"
    except Exception:
        return (f"otel: configured ({target[0]}) but SDK missing — "
                "pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http")


def _warn_unmerged_deps(repo_dir: str, slices: list, ledger: Ledger, next_layer_ids: list) -> None:
    """Loud preflight for the caller-merge contract. Worktrees branch from HEAD; accepted slice
    work lands on `slice-<id>` branches that the CALLER must merge before dependents run. If a
    pending slice depends on a DONE slice whose branch is NOT merged into HEAD, that dependent's
    worktree is dep-blind (missing the dep's code) -> it fails or rewrites the deps and gets
    diff-rejected. Detect + warn (best-effort; never blocks the build)."""
    try:
        by_id = {s.id: s for s in slices}
        needed = set()
        for sid in next_layer_ids:
            t = by_id.get(sid)
            if t:
                needed.update(getattr(t, "deps", None) or [])
        unmerged = []
        for dep in sorted(needed):
            if not ledger.is_done(dep):
                continue
            br = ledger.get(dep).commit or f"slice-{dep}"
            rc, _ = git_runner(["git", "rev-parse", "--verify", "--quiet", br], repo_dir)
            if rc != 0:
                continue  # branch gone (merged+deleted, or never created) -> can't flag it
            rc, _ = git_runner(["git", "merge-base", "--is-ancestor", br, "HEAD"], repo_dir)
            if rc != 0:  # not an ancestor of HEAD == accepted but unmerged
                unmerged.append(dep)
        if unmerged:
            bar = "!" * 68
            print(bar)
            print(f"WARNING: {len(unmerged)} accepted slice(s) are NOT merged into your base "
                  f"(HEAD): {', '.join(unmerged)}")
            print("This layer's worktrees branch from HEAD and will be DEP-BLIND (missing that")
            print("code) -> slices depending on them will fail or rewrite deps and be rejected.")
            print("Merge the accepted branches into your base first, e.g.:")
            print("   " + " && ".join(f"git merge {ledger.get(d).commit or ('slice-' + d)}" for d in unmerged))
            print(bar)
    except Exception:
        pass


def git_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Run a git command; return (returncode, combined output)."""
    # Decode explicitly: universal-newline translation would corrupt CR/LF in
    # NUL-delimited Git filenames. Undecodable paths fail rather than be renamed.
    proc = subprocess.run(args, cwd=cwd, capture_output=True)
    return (proc.returncode, (proc.stdout + proc.stderr).decode("utf-8"))


def make_judge_fn(repo_dir: str):
    """Judge wrapper — delegates to cld.judge.judge with the run_tests deliver_slice
    supplies. The TRUSTWORTHY test output comes from `pytest_test_runner` (below),
    which deliver_slice invokes in the worktree; this just forwards it."""

    def judge_fn(*, files_changed, allowed, run_tests):
        return judge(files_changed=files_changed, allowed=allowed, run_tests=run_tests)

    return judge_fn


def pytest_test_runner(workdir: str, acceptance_test_path: str | None = None) -> TestRun:
    """Run ONLY the slice's acceptance test in the worktree and return raw output.

    This is the authoritative judge signal (BUG1/Defect2 fix): the verdict comes
    from REALLY running the test in the worktree, never from the executor's
    self-reported stdout. Wired as deliver_slice's `test_runner`.

    BUG B fix: scope pytest to the slice's `acceptance_test_path`, NOT the whole
    repo suite. Running the whole suite (a) bills a paid LLM if the target repo's
    tests call one (e.g. the advisor's headless `claude -p`), and (b) lets a hang
    in an unrelated test freeze the entire build. A short timeout guards against a
    test that hangs anyway.

    TEST SELECTOR: `acceptance_test_path` may carry a pytest selector beyond a bare
    file — a `::node` id or a `-k "expr"` — to scope to JUST the slice's own tests
    inside a SHARED accumulating test file (where sibling tests are legitimately red
    until later slices land). The shared selector parser accepts one literal path/node and an optional -k
    filter. Paths containing spaces stay one argument; quote a path when using
    -k. Extra pytest flags and paths are rejected by candidate preflight.
    """
    target = acceptance_args(acceptance_test_path or "")

    # BUG B fix: when the project lives in a SUBDIR of the repo/worktree, the test's
    # imports (e.g. `from schemas import base`) need that subdir on sys.path. pytest's
    # default import resolution puts the WORKTREE ROOT (or repo root) there, not the
    # package subdir, so collection fails with ModuleNotFoundError and the judge sees a
    # spurious non-pass. Make import resolution robust + packaging-agnostic by adding
    # the worktree root AND every ancestor dir of each target test file (up to the
    # worktree root) onto PYTHONPATH — whatever level the package root sits at, it is an
    # ancestor of the test file, so its imports resolve.
    env = os.environ.copy()
    work_abs = os.path.abspath(workdir)
    roots = [work_abs]
    for tok in target:
        if tok.startswith("-"):
            continue  # a flag like -k, not a path
        rel = tok.split("::", 1)[0]  # strip any ::node-id selector
        test_abs = os.path.normpath(os.path.join(work_abs, rel))
        d = os.path.dirname(test_abs)
        while d and len(d) >= len(work_abs) and d.startswith(work_abs):
            roots.append(d)
            if d == work_abs:
                break
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    seen, ordered = set(), []
    for r in roots:
        if r not in seen:
            seen.add(r)
            ordered.append(r)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(ordered + ([existing] if existing else []))
    # Concurrency hardening: when layers fan out (--workers N), multiple judge pytest
    # processes run at once. Disable bytecode + pytest's cache so concurrent runs never
    # contend on writing `__pycache__`/`.pytest_cache` files. Cheap and side-effect-free.
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    proc = run_process(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *target, "-q"],
        workdir, env=env, timeout=600)
    return TestRun(proc.returncode, proc.output, log_path=proc.stdout_path,
                   timed_out=proc.error == "timeout", error=None if proc.error == "nonzero_exit" else proc.error)


def _parse_name_model(spec: str) -> tuple[str, dict]:
    """Parse the name:model (or slash) portion of an executor spec.

    Forms: "gemini" -> ("gemini", {}); "gemini:gemini-3-pro-preview" ->
    ("gemini", {"model": "gemini-3-pro-preview"}). The part before the first
    colon is the executor name; the remainder (if any) is the model.

    TOLERANT: the picker's catalog id uses a SLASH (opencode/<model>) while the
    canonical form uses a COLON (opencode:<model>). A copy-pasted slash id must not
    error with "Unknown executor", so if there's no colon but the spec starts with a
    known executor name followed by "/", we split on that first slash instead.
    """
    if ":" in spec:
        name, model = spec.split(":", 1)
        name = name.strip() or _default_provider()
        model = model.strip()
        return (name, {"model": model} if model else {})
    # no colon: accept "<known-executor>/<model>" (the picker/catalog slash form)
    if "/" in spec:
        head = spec.split("/", 1)[0].strip().lower()
        if head in KNOWN_EXECUTORS:
            name, model = spec.split("/", 1)
            model = model.strip()
            return (name.strip(), {"model": model} if model else {})
    return (spec or _default_provider(), {})


def parse_executor_spec(spec: str) -> tuple[str, dict]:
    """Parse an --executor value into (name, kwargs).

    Forms: "gemini" -> ("gemini", {}); "gemini:gemini-3-pro-preview" ->
    ("gemini", {"model": "gemini-3-pro-preview"}). The part before the first
    colon is the executor name; the remainder (if any) is the model. This is how
    the USER picks the LLM at invocation (not the orchestrator autonomously).

    An optional @<effort> suffix (e.g. "cursor:claude-opus-4-8@low") is split
    off and returned as kwargs["effort"]. Specs without @ are unchanged.
    """
    spec = (spec or _default_spec()).strip()
    effort = None
    if "@" in spec:
        spec, effort = spec.rsplit("@", 1)
        spec, effort = spec.strip(), (effort.strip() or None)
    name, kwargs = _parse_name_model(spec)
    if effort:
        kwargs["effort"] = effort
    return name, kwargs


def build_executor_factory():
    """Return factory(spec) -> executor, resolving a spec via parse_executor_spec +
    get_executor. Used by run_plan_parallel for per-slice executor selection."""
    def factory(spec: str):
        name, kwargs = parse_executor_spec(spec)
        return get_executor(name, **kwargs)
    return factory


def _resolve_cli(cmd: str) -> str | None:
    """Return a usable CLI path/name if cmd exists on this machine, else None."""
    if not cmd:
        return None
    if os.path.isfile(cmd):
        return cmd if os.name == "nt" or os.access(cmd, os.X_OK) else None
    found = shutil.which(cmd)
    return found if found else None


def _executor_cli_status() -> dict[str, str | None]:
    """Machine-independent contract: resolved CLI command per provider, or None if absent."""
    status = {}
    for provider in all_providers():
        invocation = provider.cli_invocation() if provider.cli_invocation else []
        executable = _resolve_cli(invocation[0]) if invocation else None
        scripts = [p for p in invocation[1:] if not p.startswith("-")]
        status[provider.name] = (scripts[-1] if scripts else executable) if executable and all(os.path.isfile(p) for p in scripts) else None
    return status


def _install_hint(provider: str) -> str:
    """One-line install guidance for a missing executor CLI."""
    hints = {
        "antigravity": "Install Antigravity and ensure `agy` is on PATH (or set AGY_CMD).",
        "opencode": "Install OpenCode: npm install -g opencode-ai (or set OPENCODE_CLI_CMD).",
        "cursor": "Install Cursor and ensure `cursor-agent` is on PATH (or set CURSOR_AGENT_CMD).",
    }
    return hints.get(provider, f"Install the {provider} CLI.")


def _is_git_repo(repo: str) -> bool:
    """Return True if repo is inside a git work tree."""
    rc, _ = git_runner(["git", "rev-parse", "--is-inside-work-tree"], repo)
    return rc == 0


def _preflight_git(repo: str) -> str | None:
    """Return None if git is on PATH and repo is a git repository; else an actionable message."""
    if not shutil.which("git"):
        return ("Git is not installed or not on PATH. Install git to use worktree isolation "
                "(https://git-scm.com/downloads).")
    if not _is_git_repo(repo):
        return (f"Not a git repository: {os.path.abspath(repo)}. "
                "Run `git init` in the target --repo directory first.")
    return None


def _preflight_executor(spec: str) -> str | None:
    """Return None if the spec's provider CLI is present; else a human-readable error message."""
    provider = _provider_of_spec(spec)
    status = _executor_cli_status()
    if status.get(provider):
        return None

    msg = (f"Executor CLI not found for provider '{provider}'. "
           f"{_install_hint(provider)}")
    installed = [p for p, cmd in status.items() if cmd]
    if installed:
        alt = installed[0]
        msg += f" Alternatively, use an installed provider: --executor {alt}"
    return msg


def _provider_of_spec(spec: str) -> str:
    """Extract the executor provider name from an --executor spec.

    Strips a trailing @effort if present, then takes the part before the first ':'.
    Lowercases and returns it if it's a registered executor; falls back to the default
    workhorse's provider.

    Examples:
        "antigravity"                       -> "antigravity"
        "antigravity:Gemini 3.1 Pro (High)" -> "antigravity"
        "opencode:opencode/deepseek-v4"     -> "opencode"
        "cursor:composer-2.5"               -> "cursor"
        "unknown:whatever"                  -> <default workhorse provider>
    """
    s = (spec or _default_spec()).strip()
    # strip @effort suffix
    if "@" in s:
        s = s.rsplit("@", 1)[0].strip()
    # take the part before the first ':'
    if ":" in s:
        name = s.split(":", 1)[0].strip().lower()
    else:
        name = s.lower()
    return name if name in KNOWN_EXECUTORS else _default_provider()


def _available_ids_for(provider: str) -> list:
    """Return available model ids for the given provider executor name.

    Delegates to the registered provider's list_models callable.
    All exceptions are caught and [] is returned so failures degrade gracefully.
    """
    try:
        p = get_provider(provider)
        # Use a default subprocess runner for providers that need one
        if provider == "opencode":
            from cld_providers.opencode.provider import _default_runner
            return p.list_models(_default_runner)
        if provider == "cursor":
            from cld_providers.cursor.provider import _default_runner as _cursor_runner
            # list_models for cursor returns plain ids (not (id, label) tuples)
            return p.list_models(_cursor_runner)
        return p.list_models(lambda args, cwd: (0, ""))
    except Exception:
        return []


def build_rung_planner(default_spec: str, *, evidence=None, max_retries: int = 2):
    """Build a rung_planner callable from the build's provider, evidence, and available ids.

    The returned planner(task) calls cld.models.plan_rungs with the resolved provider,
    evidence dict, and available model ids, returning the escalation ladder for that slice.

    evidence=None resolves via EvidenceStore().statuses() at call time (i.e. when
    build_rung_planner is called, not when each slice is planned). Pass evidence={}
    to skip the store lookup (e.g. in tests).
    """
    provider = _provider_of_spec(default_spec)
    # An EXPLICIT --executor model (e.g. opencode:opencode/kimi-k2.7-code) is a deliberate
    # choice: honor it as the entry rung instead of letting complexity-routing swap in a
    # catalogued workhorse (the silent-fallback bug). A bare-provider --executor names no
    # model -> entry_spec stays None -> full tier-routing as before.
    _name, _kw = parse_executor_spec(default_spec)
    entry_spec = default_spec if _kw.get("model") else None
    if evidence is None:
        from cld.evidence import EvidenceStore
        evidence = EvidenceStore().statuses()
    available = _available_ids_for(provider)

    def planner(task):
        from cld.models import plan_rungs
        return plan_rungs(task, provider=provider, evidence=evidence,
                          available_ids=available, max_retries=max_retries, entry_spec=entry_spec)

    return planner


def prepare_dispatch(args, slices, ledger):
    """Freeze all selected rungs, preflight all providers, then admit all models."""
    from cld.admission import Admission, AdmissionBlocked, validation_context, writable_directory
    from cld.evidence import EvidenceStore
    from cld.models import resolve_spec
    from cld.validate import validate_model
    from cld.worktree import managed_location
    from cld.orchestrator import next_pending_layer
    from cld.recovery import atomic_write
    import json

    selected = [s for s in slices if not ledger.is_done(s.id) and
                not (ledger.get(s.id) and ledger.get(s.id).status == "needs_repair")]
    if args.step:
        layer = next_pending_layer(slices, ledger)
        selected = [s for s in selected if layer and s.id in layer[1]]
    if not selected:
        return None, None
    default, _, _ = resolve_spec(args.executor or _default_spec())
    # Preflight entry providers before asking a provider to list available models.
    entries = [resolve_spec(s.executor or default)[0] for s in selected]
    for spec in dict.fromkeys(entries):
        problem = _preflight_executor(spec)
        if problem:
            raise AdmissionBlocked(problem)
    directory = run_directory(args.repo, ledger.build["run_id"]) / "validation"
    _, root, _ = managed_location(args.repo, args.worktree_root,
        ledger.build["run_id"], "preflight", "0" * 32)
    for path in (root, directory):
        writable_directory(path)
    store = EvidenceStore()
    store.statuses()  # Detect corrupt evidence before discovery or validation spend.
    writable_directory(store._path.parent)
    if store._path.exists():
        with store._path.open("r+b"):
            pass
    # Preserve bare-provider tier selection; an explicit model stays pinned at entry.
    planner = build_rung_planner(args.executor or _default_spec(), evidence={})
    rungs = {s.id: [(rung, resolve_spec(spec)[0], budget) for rung, spec, budget in planner(s)] for s in selected}
    specs = list(dict.fromkeys(spec for values in rungs.values() for _, spec, _ in values))
    for spec in specs:
        problem = _preflight_executor(spec)
        if problem:
            raise AdmissionBlocked(problem)
    config_paths = [Path(args.repo) / p for p in
        ("opencode.json", "opencode.jsonc", ".opencode/opencode.json", ".cursor/cli.json", ".gemini/settings.json")]
    config_paths += [Path.home() / p for p in
        (".config/opencode/opencode.json", ".config/opencode/opencode.jsonc", ".cursor/cli-config.json", ".gemini/settings.json")]
    config_paths += [Path(p).resolve() for p in args.validation_config]
    if os.environ.get("OPENCODE_CONFIG"):
        config_paths.append(Path(os.environ["OPENCODE_CONFIG"]).resolve())

    def context_of(spec):
        _, provider, _ = resolve_spec(spec)
        invocation = get_provider(provider).cli_invocation()
        command = _resolve_cli(invocation[0])
        if not command:
            raise AdmissionBlocked(f"CLI disappeared for {provider}")
        return validation_context(spec, cli_paths=[command, *invocation[1:]],
            config_paths=config_paths, extra=args.validation_context, repo=args.repo)

    def validate(spec):
        _, provider, kwargs = resolve_spec(spec)
        executor = get_executor(provider, **kwargs)
        if getattr(args, "accounting", None):
            executor = args.accounting.wrap(executor, spec, kind="validation", identity=context_of(spec))
        return validate_model(spec, executor=executor,
            git_runner=git_runner, base_dir=str(directory))

    report = directory / "admission.json"
    contexts = {spec: context_of(spec) for spec in specs}
    gate = Admission(store=store, validate_fn=validate, context_of=context_of,
        policy=args.validation_policy, force=args.revalidate_models,
        max_age_seconds=args.validation_max_age, report_path=report)
    # Save policy and check the report path before the first possible dispatch.
    atomic_write(report, json.dumps(dict(schema_version=1, validation_policy=args.validation_policy,
        force_revalidate=args.revalidate_models, selected_specs=specs, models=[])).encode("utf-8"))
    previews = [gate.check(spec, execute=False) for spec in specs]
    blocked = [result for result in previews if not result.proceeded]
    if blocked:
        raise AdmissionBlocked(f"{blocked[0].spec}: {blocked[0].note}; evidence: {report}")
    admitted = {}
    for spec in specs:
        result = gate.check(spec)
        if not result.proceeded:
            raise AdmissionBlocked(f"{spec}: {result.note}; evidence: {report}")
        if context_of(spec) != contexts[spec]:
            raise AdmissionBlocked(f"{spec}: CLI/configuration changed during validation; rerun preflight")
        admitted[spec] = contexts[spec]

    def factory(value):
        spec, provider, kwargs = resolve_spec(value)
        if spec not in admitted or context_of(spec) != admitted[spec]:
            raise AdmissionBlocked("Model/CLI/configuration changed after admission; rerun preflight")
        executor = get_executor(provider, **kwargs)
        if getattr(args, "accounting", None):
            executor = args.accounting.wrap(executor, spec, identity=admitted[spec])
        return executor

    return factory, lambda task: list(rungs[task.id])


def prompt_for_executor() -> str:
    """Interactive model picker (the CLI surface). Lists available OpenCode models,
    builds the recommended shortlist, and prompts the user to choose. The proven
    Gemini workhorse is always offered as the default. Returns an --executor spec.

    Degrades gracefully: if OpenCode isn't installed, `list_models` returns [] and
    the shortlist falls back to just the Gemini default."""
    from cld.models import pick_executor, recommend

    try:
        from cld_providers.opencode.provider import _default_runner
        p = get_provider("opencode")
        available = p.list_models(_default_runner)
    except Exception:
        available = []

    recs = recommend(available_ids=available)
    if not recs:
        return _default_spec()
    return pick_executor(recs)



def _main(argv=None) -> int:
    # BUG A fix: Windows consoles default to cp1252, which can't encode some glyphs
    # the renderers emit -> print() of the layer summary/gate would die with
    # UnicodeEncodeError AFTER slices ran but BEFORE the exit-code gate, losing the
    # whole step's result. Force UTF-8 on stdout/stderr so output never crashes the
    # run. Best-effort (no-op on streams that can't reconfigure).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(description="Run a cross-llm-delivery plan.")
    p.add_argument("plan", nargs="?", default=None, help="Path to the plan markdown file")
    p.add_argument("--repo", default=".", help="Repo dir for worktree isolation")
    p.add_argument("--worktree-root", help="Writable worktree root (relative to --repo); default .cld/worktrees")
    p.add_argument("--ledger", default=None, help="Ledger path; default <repo>/.cld-ledger.json; explicit relative paths use invocation cwd")
    p.add_argument("--migrate-ledger", action="store_true", help="Back up and migrate legacy state with this plan; no dispatch")
    p.add_argument("--reconcile-plan", action="store_true", help="Back up state and invalidate changed slices/dependents; no dispatch")
    p.add_argument("--new-build", action="store_true", help="Back up state and start a fresh run; no dispatch")
    p.add_argument("--integrate", action="store_true", help="Verify and integrate accepted commits; no provider dispatch")
    p.add_argument("--integration-tests", help="Explicit committed pytest selector for integration (required for whole multi-layer runs)")
    p.add_argument("--manual-integration", help="With --integrate, verify an existing merge commit/ref")
    p.add_argument("--validation-policy", choices=("deny", "unmetered", "allow"), default="deny",
                   help="Recorded permission for validation probes: deny (default), known unmetered, or all including unknown costs")
    p.add_argument("--revalidate-models", action="store_true", help="Force one fresh probe per selected model/context; still requires validation spend policy")
    p.add_argument("--validation-max-age", type=float, default=30 * 86400, help="Maximum evidence age in seconds")
    p.add_argument("--validation-context", default="", help="Identity of external provider/account configuration not represented by local files")
    p.add_argument("--validation-config", action="append", default=[], help="Additional provider config file to fingerprint; repeatable")
    p.add_argument("--budget-tokens", type=int, help="Cumulative dispatch token admission limit")
    p.add_argument("--budget-cost", type=float, help="Cumulative provider-reported USD admission limit")
    p.add_argument("--budget-attempts", type=int, help="Cumulative dispatch count limit, including probes/retries")
    p.add_argument("--attempt-tokens", type=int, help="Token reservation per dispatch, not a provider hard cap")
    p.add_argument("--attempt-cost", type=float, help="USD reservation per dispatch, not a provider hard cap")
    p.add_argument("--unknown-usage", choices=("deny", "reserve"), help="Unknown completed usage under limits: block (default) or charge recorded allowance")
    p.add_argument("--workers", type=int, default=4, help="Max parallel slices")
    p.add_argument("--executor", default=None,
                   help="Executor to use, e.g. 'antigravity', 'antigravity:<model>', or "
                        "'opencode:<provider/model>'. If omitted and stdin is a TTY, "
                        "an interactive picker prompts you to choose (default: the "
                        "verified workhorse). Non-interactive: defaults to the workhorse.")
    p.add_argument("--dry-run", action="store_true",
                   help="Load + layer the plan and print the schedule; no dispatch")
    p.add_argument("--step", action="store_true",
                   help="Run ONLY the next pending DAG layer, then exit (context-lean "
                        "orchestration). Re-invoke to advance. Exit codes: 0 layer all-passed, "
                        "2 some failed/deferred, 3 build complete, "
                        "4 a slice needs orchestrator repair (lead agent intervenes).")
    p.add_argument("--mark-repaired", default=None, metavar="SLICE_ID",
                   help="Re-test and collect a repaired retained worktree using the original plan; acceptance still requires integration.")
    p.add_argument("--usage", action="store_true",
                   help="Print a combined LLM-usage table (this build's ledger + opencode "
                        "account stats) and exit. No dispatch.")
    p.add_argument("--status", action="store_true",
                   help="Print a compact digest of the current build state from "
                        ".cld/events.jsonl and exit. No plan/dispatch needed (the lead agent "
                        "polls this between turns during a background build).")
    p.add_argument("--watch", action="store_true",
                   help="Repaint --status every --interval seconds (a tiny human terminal view; "
                        "Ctrl-C to stop). Equivalent to `tail -f` on the digest.")
    p.add_argument("--interval", type=int, default=5,
                   help="Seconds between repaints for --watch (default 5).")
    args = p.parse_args(argv)
    if args.manual_integration and not args.integrate:
        raise StateError("--manual-integration requires --integrate")
    if sum(bool(v) for v in (args.integrate, args.step, args.mark_repaired, args.migrate_ledger, args.reconcile_plan, args.new_build)) > 1:
        raise StateError("Choose one delivery/state action")
    if args.integrate and args.step:
        raise StateError("Choose --integrate or --step")
    if args.workers < 1 or args.interval < 1:
        raise StateError("Workers and interval must be positive")
    args.repo = os.path.realpath(args.repo)
    args.ledger = resolve_ledger(args.repo, args.ledger)

    if args.usage:
        from cld.usage import render_usage_table
        ledger = Ledger.load(args.ledger)
        print(render_usage_table(ledger))
        return 0

    if args.status:
        from cld.status import render_status
        print(_render_build_status(args.repo, Ledger.load(args.ledger)))
        return 0

    if args.watch:
        import time as _time
        from cld.status import render_status
        try:
            while True:
                print(_render_build_status(args.repo, Ledger.load(args.ledger)))
                print("-" * 48)
                _time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0

    if args.plan is None:
        print("A plan file is required for dispatch (or use --status/--usage/--mark-repaired).",
              file=sys.stderr)
        return 5

    try:
        plan_md = Path(args.plan).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PlanError(f"Cannot read plan {args.plan}: {exc}") from exc
    slices = load_slices(plan_md)
    if not slices:
        print("No slices found in plan.", file=sys.stderr)
        return 5

    if args.dry_run:
        from cld.dag import parallel_batches
        deps = {s.id: list(s.deps) for s in slices}
        print(f"{len(slices)} slices. Execution layers (parallel batches):")
        for i, layer in enumerate(parallel_batches(deps)):
            print(f"  layer {i}: {', '.join(layer)}")
        return 0

    git_err = _preflight_git(args.repo)
    if git_err:
        print(git_err)
        return 5
    ledger = Ledger(args.ledger)
    print(f"state: repo={args.repo}; ledger={args.ledger}")
    with ledger.writer(refresh=True):
        ledger.bind(args.repo, slices, git_runner, plan_path=args.plan, plan_text=plan_md,
                    migrate=args.migrate_ledger, reconcile=args.reconcile_plan, new_build=args.new_build)
        if args.migrate_ledger or args.reconcile_plan or args.new_build:
            print(f"state prepared: run={ledger.build['run_id']}; backup={ledger.build.get('backup')}")
            pending = [sid for sid, entry in ledger.entries.items() if entry.status == "needs_repair"]
            if pending:
                print(f"reconciliation required: {', '.join(pending)}")
            return 0
        if args.mark_repaired:
            from cld.repair import verify_repair
            gate = verify_repair(slices, ledger, args.mark_repaired, repo_dir=args.repo,
                git_runner=git_runner, test_runner=pytest_test_runner, worktree_root=args.worktree_root)
            if not gate.passed:
                print(f"Repair required: {gate.error}; evidence: {gate.evidence}")
                _record_operation(args, ledger, "repair", 4)
                return 4
            print(f"Repair accepted: {args.mark_repaired}; commit={gate.commit}; integration required; evidence={gate.evidence}")
            _record_operation(args, ledger, "repair", 6)
            return 6
        if args.integrate:
            from cld.integration import integrate
            gate = integrate(slices, ledger, repo_dir=args.repo, git_runner=git_runner,
                test_runner=pytest_test_runner, selector=args.integration_tests or ledger.build.get("integration_selector"),
                worktree_root=args.worktree_root, manual_ref=args.manual_integration)
            if not gate.passed:
                print(f"Integration repair required: {gate.error}; evidence: {gate.evidence}")
                _record_operation(args, ledger, "integrate", 4)
                return 4
            print(f"Integrated: {list(gate.integrated)}; commit={gate.commit}; evidence={gate.evidence}")
            code = 3 if all(e.status == "integrated" for e in ledger.entries.values()) else 0
            _record_operation(args, ledger, "integrate", code)
            return code
        if not args.step:
            from cld.dag import parallel_batches
            if len(parallel_batches({s.id: s.deps for s in slices})) > 1 and not args.integration_tests:
                raise StateError("Whole-plan multi-layer delivery requires --integration-tests; use --step then --integrate")
        if args.step and ledger.build.get("integration_failure"):
            failure = ledger.build["integration_failure"]
            print(f"Integration repair required: {failure['error']}; evidence: {failure['evidence']}")
            return 4
        from cld.accounting import Accounting
        args.accounting = Accounting(ledger, dict(tokens=args.budget_tokens, cost=args.budget_cost,
            attempts=args.budget_attempts, attempt_tokens=args.attempt_tokens,
            attempt_cost=args.attempt_cost, unknown=args.unknown_usage))
        dispatch_needed = _dispatch_needed(slices, ledger)
        if dispatch_needed:
            if args.executor is None and sys.stdin.isatty():
                try:
                    args.executor = prompt_for_executor()
                except EOFError:
                    args.executor = _default_spec()
            try:
                args.admitted_factory, args.admitted_planner = prepare_dispatch(args, slices, ledger)
            except (ValueError, OSError, EvidenceError) as exc:
                import json
                from cld.recovery import atomic_write
                blocked = dict(schema_version=1, gate="blocked", gate_code=5,
                    reason=str(exc)[:4000], validation_policy=args.validation_policy,
                    next_action="Correct preflight or select an explicit validation policy, then retry")
                try:
                    atomic_write(run_directory(args.repo, ledger.build["run_id"]) / "validation-blocked.json",
                                 json.dumps(blocked, indent=2).encode("utf-8"))
                except OSError:
                    pass  # A denied artifact root must still return a structured block.
                print(json.dumps(blocked))
                _record_operation(args, ledger, "validation", 5)
                return 5
        from cld import telemetry
        try:
            return _execute(args, slices, ledger)
        finally:
            telemetry.set_sink(None)
            telemetry.set_run_id(None)


def _execute(args, slices, ledger):
    # Install the local telemetry stream (zero-config) + emit run_start on a fresh build.
    events_path = _install_telemetry(args.repo, ledger, args.plan, args.executor or _default_spec())
    print(f"telemetry: {os.path.relpath(events_path, os.path.abspath(args.repo))} (local)")
    print(_otel_status_line())

    if args.step:
        from cld.orchestrator import next_pending_layer
        from cld.summary import classify_gate, summarize_layer, write_artifacts
        from cld import telemetry
        sel = next_pending_layer(slices, ledger)
        if sel is None:
            from cld.integration import pending_integration, verified_base
            verified_base(ledger, git_runner)
            if pending_integration(ledger):
                print("INTEGRATION REQUIRED — run --integrate --integration-tests <selector>.")
                return 6
            print("BUILD COMPLETE — all slices integrated and verified.")
            return 3
        idx, layer_ids, total = sel
        layer_slices = [s for s in slices if s.id in layer_ids]
        telemetry.emit("layer_start", layer=idx, slice_ids=list(layer_ids), total=total)
        judge_fn = make_judge_fn(args.repo)
        result = run_plan_parallel(
            layer_slices, ledger,
            plan_slices=slices,
            accounting=getattr(args, "accounting", None),
            executor_factory=getattr(args, "admitted_factory", None),
            default_spec=args.executor or _default_spec(),
            rung_planner=getattr(args, "admitted_planner", None),
            judge_fn=judge_fn,
            max_workers=args.workers,
            repo_dir=args.repo, git_runner=git_runner, worktree_root=args.worktree_root,
            test_runner=pytest_test_runner,
        )
        write_artifacts(result, repo_dir=args.repo, run_id=ledger.build["run_id"])
        nxt = next_pending_layer(slices, ledger)
        from cld.integration import pending_integration
        result.integration_required = pending_integration(ledger)
        result.build_complete = bool(ledger.entries) and all(e.status == "integrated" for e in ledger.entries.values())
        telemetry.emit("layer_done", layer=idx, gate=_layer_gate(result))
        if result.build_complete:
            telemetry.emit("run_done", gate=_layer_gate(result))
        next_layer = nxt[1] if nxt else []
        print(summarize_layer(result, layer_index=idx, total_layers=total,
                              next_layer=next_layer))
        code = classify_gate(result, more_layers=bool(nxt))
        telemetry.emit("operation_done", operation="step", gate=_layer_gate(result), gate_code=code)
        return code

    judge_fn = make_judge_fn(args.repo)

    result = run_plan_parallel(
        slices, ledger,
        plan_slices=slices,
        accounting=getattr(args, "accounting", None),
        executor_factory=getattr(args, "admitted_factory", None),
        default_spec=args.executor or _default_spec(),
        rung_planner=getattr(args, "admitted_planner", None),
        judge_fn=judge_fn,
        max_workers=args.workers,
        repo_dir=args.repo, git_runner=git_runner, worktree_root=args.worktree_root,
        test_runner=pytest_test_runner,  # REAL pytest in the worktree = the judge signal
        integration_test_path=args.integration_tests,
    )
    from cld import telemetry as _tel
    if result.build_complete:
        _tel.emit("run_done", gate=_layer_gate(result))

    print(f"completed: {result.completed}")
    print(f"failed:    {result.failed}")
    print(f"skipped:   {result.skipped}")
    print(f"deferred:  {result.deferred}")
    print(f"needs repair: {result.needs_repair}")
    from cld.summary import recovery_lines, write_artifacts
    write_artifacts(result, repo_dir=args.repo, run_id=ledger.build["run_id"])
    for sid, detail in getattr(result, "details", {}).items():
        for line in recovery_lines(sid, detail):
            print(line)
    if result.integration_error:
        print(f"Integration failed: {result.integration_error}")
    elif result.integration_required:
        print("INTEGRATION REQUIRED — run --integrate --integration-tests <selector>.")
    from cld.summary import classify_gate
    code = classify_gate(result, more_layers=False)
    _tel.emit("operation_done", operation="plan", gate=_layer_gate(result), gate_code=code)
    return code


def main(argv=None) -> int:
    try:
        return _main(argv)
    except (StateError, OwnerBusy, CaptureError, PlanError, EvidenceError, ValueError) as exc:
        print(f"State blocked: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
