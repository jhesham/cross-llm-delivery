"""cld.cli — host-neutral command handling for the cross-llm-delivery driver.

All reusable CLI handling lives here in the engine. Entrypoints:
  * ``python -m cld`` (engine/cld/__main__.py), and
  * ``skill/scripts/run_delivery.py`` — a thin backward-compatible shim that
    re-exports these names. Importlib-based tests monkeypatch the shim module's
    attributes; the :func:`hooks_from` context manager binds that module
    namespace so the patches are visible at this module's call sites.

Default (human) behavior is unchanged. ``--json`` switches to machine mode:
prompts are disabled even on a TTY and exactly one schema-version-1 JSON object
is written to stdout; progress goes to stderr/artifacts. All CLI failures —
including argparse errors — are structured in JSON mode. ``--host NAME`` is
optional telemetry provenance only.

Gate exit codes: 0 pending / 2 failed / 3 passed / 4 needs_repair /
5 blocked / 6 integration_required. Exit 3 means verified integration is
complete; 6 means accepted work awaits integration.
"""

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from contextvars import ContextVar
from pathlib import Path

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
from cld import telemetry
from cld import cli_response

# Load all providers at startup so the registry is populated before any
# call to get_executor / get_provider / KNOWN_EXECUTORS.
load_providers()

# ---------------------------------------------------------------------------
# KNOWN_EXECUTORS: dynamic shim (registry-backed) for backward-compat callers
# within this module (e.g. _parse_name_model, _provider_of_spec).
# ---------------------------------------------------------------------------
KNOWN_EXECUTORS = tuple(p.name for p in all_providers())


# ---------------------------------------------------------------------------
# Monkeypatch hooks: the run_delivery shim re-exports this module's names and
# binds its own module namespace via hooks_from() while delegating, so tests
# that monkeypatch the shim keep working. _hook() consults the bound namespace
# first and falls back to this module's globals.
# ---------------------------------------------------------------------------
_hook_ns = ContextVar("cld_cli_hook_ns", default=None)


@contextlib.contextmanager
def hooks_from(namespace):
    """Bind an override namespace (the shim's globals) for patchable seams."""
    token = _hook_ns.set(namespace)
    try:
        yield
    finally:
        _hook_ns.reset(token)


def _hook(name):
    ns = _hook_ns.get()
    if ns is not None and name in ns:
        return ns[name]
    return globals()[name]


def _default_spec() -> str:
    """The default executor SPEC when the user names none — the engine's current default
    workhorse (provider-blind)."""
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


def _record_operation(args, ledger, operation, code, reason=None):
    labels = {0: "pending", 2: "failed", 3: "passed", 4: "needs_repair", 5: "blocked", 6: "integration_required"}
    ledger.build["last_operation"] = dict(operation=operation, gate_code=code, reason=reason)
    ledger.save()
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
    events = _hook("_read_event_stream")(repo, ledger)
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
    Langfuse keys-convenience. Pure (env in -> target out) so it's unit-testable."""
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
    work lands on `slice-<id>` branches that the CALLER must merge before dependents run.
    Best-effort; never blocks the build."""
    git_runner = _hook("git_runner")
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

    This is the authoritative judge signal: the verdict comes from REALLY running
    the test in the worktree, never from the executor's self-reported stdout.
    `acceptance_test_path` may carry a pytest selector beyond a bare file — a
    `::node` id or a `-k "expr"`. Paths containing spaces stay one argument.
    """
    target = acceptance_args(acceptance_test_path or "")

    # When the project lives in a SUBDIR of the repo/worktree, the test's imports need
    # that subdir on sys.path: add the worktree root AND every ancestor dir of each
    # target test file (up to the worktree root) onto PYTHONPATH.
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
    # Concurrency hardening: no __pycache__/.pytest_cache contention between judges.
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    proc = _hook("run_process")(
        # Keep complete assertion reasons even with a project's quiet addopts.
        # Candidate preflight classifies failures from the real pytest summary.
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *target, "-vvv", "--tb=short"],
        workdir, env=env, timeout=600)
    return TestRun(proc.returncode, proc.output, log_path=proc.stdout_path,
                   timed_out=proc.error == "timeout", error=None if proc.error == "nonzero_exit" else proc.error)


def _parse_name_model(spec: str) -> tuple[str, dict]:
    """Parse the name:model (or slash) portion of an executor spec.

    TOLERANT: the picker's catalog id uses a SLASH (opencode/<model>) while the
    canonical form uses a COLON (opencode:<model>); the slash form splits on the
    first slash when the head is a known executor name.
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
    ("gemini", {"model": "gemini-3-pro-preview"}). An optional @<effort> suffix
    (e.g. "cursor:claude-opus-4-8@low") is returned as kwargs["effort"].
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
        return _hook("get_executor")(name, **kwargs)
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
    resolve = _hook("_resolve_cli")
    status = {}
    for provider in all_providers():
        invocation = provider.cli_invocation() if provider.cli_invocation else []
        executable = resolve(invocation[0]) if invocation else None
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
    rc, _ = _hook("git_runner")(["git", "rev-parse", "--is-inside-work-tree"], repo)
    return rc == 0


def _preflight_git(repo: str) -> str | None:
    """Return None if git is on PATH and repo is a git repository; else an actionable message."""
    if not shutil.which("git"):
        return ("Git is not installed or not on PATH. Install git to use worktree isolation "
                "(https://git-scm.com/downloads).")
    if not _hook("_is_git_repo")(repo):
        return (f"Not a git repository: {os.path.abspath(repo)}. "
                "Run `git init` in the target --repo directory first.")
    return None


def _preflight_executor(spec: str) -> str | None:
    """Return None if the spec's provider CLI is present; else a human-readable error message."""
    provider = _provider_of_spec(spec)
    status = _hook("_executor_cli_status")()
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
    Falls back to the default workhorse's provider for unknown names.
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
            return p.list_models(_cursor_runner)
        return p.list_models(lambda args, cwd: (0, ""))
    except Exception:
        return []


def build_rung_planner(default_spec: str, *, evidence=None, max_retries: int = 2):
    """Build a rung_planner callable from the build's provider, evidence, and available ids.

    evidence=None resolves via EvidenceStore().statuses() at call time. Pass evidence={}
    to skip the store lookup (e.g. in tests).
    """
    provider = _provider_of_spec(default_spec)
    # An EXPLICIT --executor model is a deliberate choice: honor it as the entry rung
    # instead of letting complexity-routing swap in a catalogued workhorse.
    _name, _kw = parse_executor_spec(default_spec)
    entry_spec = default_spec if _kw.get("model") else None
    if evidence is None:
        from cld.evidence import EvidenceStore
        evidence = EvidenceStore().statuses()
    available = _hook("_available_ids_for")(provider)

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
        problem = _hook("_preflight_executor")(spec)
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
    planner = _hook("build_rung_planner")(args.executor or _default_spec(), evidence={})
    rungs = {s.id: [(rung, resolve_spec(spec)[0], budget) for rung, spec, budget in planner(s)] for s in selected}
    specs = list(dict.fromkeys(spec for values in rungs.values() for _, spec, _ in values))
    for spec in specs:
        problem = _hook("_preflight_executor")(spec)
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
        command = _hook("_resolve_cli")(invocation[0])
        if not command:
            raise AdmissionBlocked(f"CLI disappeared for {provider}")
        return validation_context(spec, cli_paths=[command, *invocation[1:]],
            config_paths=config_paths, extra=args.validation_context, repo=args.repo)

    def validate(spec):
        _, provider, kwargs = resolve_spec(spec)
        executor = _hook("get_executor")(provider, **kwargs)
        if getattr(args, "accounting", None):
            executor = args.accounting.wrap(executor, spec, kind="validation", identity=context_of(spec))
        return validate_model(spec, executor=executor,
            git_runner=_hook("git_runner"), base_dir=str(directory))

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
        executor = _hook("get_executor")(provider, **kwargs)
        if getattr(args, "accounting", None):
            executor = args.accounting.wrap(executor, spec, identity=admitted[spec])
        return executor

    return factory, lambda task: list(rungs[task.id])


def prompt_for_executor() -> str:
    """Interactive model picker (the CLI surface). Degrades gracefully: if OpenCode
    isn't installed, the shortlist falls back to just the default workhorse."""
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


# ---------------------------------------------------------------------------
# Argument parsing / validation
# ---------------------------------------------------------------------------

class _UsageError(Exception):
    """An argparse failure captured for structured (JSON) reporting."""


class _JsonArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises instead of printing prose + exiting."""

    def error(self, message):
        raise _UsageError(message)

    def exit(self, status=0, message=None):
        if status:
            raise _UsageError((message or "invalid arguments").strip())
        raise _UsageError("help requested")


def build_parser(json_mode: bool = False) -> argparse.ArgumentParser:
    cls = _JsonArgumentParser if json_mode else argparse.ArgumentParser
    p = cls(description="Run a cross-llm-delivery plan.")
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
    p.add_argument("--json", action="store_true",
                   help="Machine mode: write exactly one schema-1 JSON object to stdout; "
                        "progress goes to stderr. Disables prompts even on a TTY.")
    p.add_argument("--host", default=None, metavar="NAME",
                   help="Optional host provenance (e.g. codex, claude-code) stamped onto "
                        "telemetry events only; never affects judging or admission.")
    p.add_argument("--slice", default=None, metavar="SLICE_ID", dest="slice",
                   help="With --status/--usage: bounded detail for one slice.")
    p.add_argument("--attempt", default=None, metavar="ATTEMPT_ID",
                   help="With --status/--usage: select one retained usage record.")
    return p


def _validate(args) -> None:
    """Reject conflicting/unsupported request combinations (structured in JSON mode)."""
    if getattr(args, "json", False) and args.watch:
        raise StateError("--watch is a human terminal view and is not available with --json")
    if sum(bool(v) for v in (args.usage, args.status, args.watch)) > 1:
        raise StateError("Choose one of --status, --usage or --watch")
    if (getattr(args, "slice", None) or getattr(args, "attempt", None)) and not (args.status or args.usage):
        raise StateError("--slice/--attempt require --status or --usage")
    if args.manual_integration and not args.integrate:
        raise StateError("--manual-integration requires --integrate")
    if sum(bool(v) for v in (args.status, args.usage, args.watch, args.dry_run,
                            args.integrate, args.step, args.mark_repaired,
                            args.migrate_ledger, args.reconcile_plan, args.new_build)) > 1:
        raise StateError("Choose one inspection/delivery/state action")
    if args.workers < 1 or args.interval < 1:
        raise StateError("Workers and interval must be positive")


def _resolve_paths(args) -> None:
    args.repo = os.path.realpath(args.repo)
    args.ledger = resolve_ledger(args.repo, args.ledger)


def _run(args) -> int:
    """The post-parse pipeline (both text and JSON mode route through here)."""
    _validate(args)
    _resolve_paths(args)

    if args.usage:
        from cld.usage import render_usage_table
        ledger = Ledger.load(args.ledger)
        print(render_usage_table(ledger))
        return 0

    if args.status:
        print(_hook("_render_build_status")(args.repo, Ledger.load(args.ledger)))
        return 0

    if args.watch:
        import time as _time
        try:
            while True:
                print(_hook("_render_build_status")(args.repo, Ledger.load(args.ledger)))
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

    git_err = _hook("_preflight_git")(args.repo)
    if git_err:
        print(git_err)
        return 5
    ledger = Ledger(args.ledger)
    print(f"state: repo={args.repo}; ledger={args.ledger}")
    with ledger.writer(refresh=True):
        ledger.bind(args.repo, slices, _hook("git_runner"), plan_path=args.plan, plan_text=plan_md,
                    migrate=args.migrate_ledger, reconcile=args.reconcile_plan, new_build=args.new_build)
        if args.migrate_ledger or args.reconcile_plan or args.new_build:
            print(f"state prepared: run={ledger.build['run_id']}; backup={ledger.build.get('backup')}")
            pending = [sid for sid, entry in ledger.entries.items() if entry.status == "needs_repair"]
            if pending:
                print(f"reconciliation required: {', '.join(pending)}")
                if getattr(args, "json", False):
                    return 4
            return 0
        if args.mark_repaired:
            from cld.repair import verify_repair
            gate = verify_repair(slices, ledger, args.mark_repaired, repo_dir=args.repo,
                git_runner=_hook("git_runner"), test_runner=_hook("pytest_test_runner"), worktree_root=args.worktree_root)
            if not gate.passed:
                print(f"Repair required: {gate.error}; evidence: {gate.evidence}")
                _record_operation(args, ledger, "repair", 4)
                return 4
            print(f"Repair accepted: {args.mark_repaired}; commit={gate.commit}; integration required; evidence={gate.evidence}")
            _record_operation(args, ledger, "repair", 6)
            return 6
        if args.integrate:
            from cld.integration import integrate
            gate = integrate(slices, ledger, repo_dir=args.repo, git_runner=_hook("git_runner"),
                test_runner=_hook("pytest_test_runner"), selector=args.integration_tests or ledger.build.get("integration_selector"),
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
            if args.executor is None and not getattr(args, "json", False) and sys.stdin.isatty():
                try:
                    args.executor = _hook("prompt_for_executor")()
                except EOFError:
                    args.executor = _default_spec()
            try:
                args.admitted_factory, args.admitted_planner = _hook("prepare_dispatch")(args, slices, ledger)
            except (ValueError, OSError, EvidenceError) as exc:
                blocked = dict(schema_version=1, gate="blocked", gate_code=5,
                    reason=str(exc)[:4000], validation_policy=args.validation_policy,
                    next_action="Correct preflight or select an explicit validation policy, then retry")
                try:
                    from cld.recovery import atomic_write
                    atomic_write(run_directory(args.repo, ledger.build["run_id"]) / "validation-blocked.json",
                                 json.dumps(blocked, indent=2).encode("utf-8"))
                except OSError:
                    pass  # A denied artifact root must still return a structured block.
                print(json.dumps(blocked))
                _record_operation(args, ledger, "validation", 5, reason=blocked["reason"])
                return 5
        try:
            code = _hook("_execute")(args, slices, ledger)
            ledger.build["last_operation"] = dict(operation="delivery", gate_code=code)
            ledger.save()
            return code
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
        sel = next_pending_layer(slices, ledger)
        if sel is None:
            from cld.integration import pending_integration, verified_base
            verified_base(ledger, _hook("git_runner"))
            if pending_integration(ledger):
                print("INTEGRATION REQUIRED — run --integrate --integration-tests <selector>.")
                return 6
            print("BUILD COMPLETE — all slices integrated and verified.")
            return 3
        idx, layer_ids, total = sel
        layer_slices = [s for s in slices if s.id in layer_ids]
        telemetry.emit("layer_start", layer=idx, slice_ids=list(layer_ids), total=total)
        judge_fn = make_judge_fn(args.repo)
        result = _hook("run_plan_parallel")(
            layer_slices, ledger,
            plan_slices=slices,
            accounting=getattr(args, "accounting", None),
            executor_factory=getattr(args, "admitted_factory", None),
            default_spec=args.executor or _default_spec(),
            rung_planner=getattr(args, "admitted_planner", None),
            judge_fn=judge_fn,
            max_workers=args.workers,
            repo_dir=args.repo, git_runner=_hook("git_runner"), worktree_root=args.worktree_root,
            test_runner=_hook("pytest_test_runner"),
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

    result = _hook("run_plan_parallel")(
        slices, ledger,
        plan_slices=slices,
        accounting=getattr(args, "accounting", None),
        executor_factory=getattr(args, "admitted_factory", None),
        default_spec=args.executor or _default_spec(),
        rung_planner=getattr(args, "admitted_planner", None),
        judge_fn=judge_fn,
        max_workers=args.workers,
        repo_dir=args.repo, git_runner=_hook("git_runner"), worktree_root=args.worktree_root,
        test_runner=_hook("pytest_test_runner"),  # REAL pytest in the worktree = the judge signal
        integration_test_path=args.integration_tests,
    )
    if result.build_complete:
        telemetry.emit("run_done", gate=_layer_gate(result))

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
    telemetry.emit("operation_done", operation="plan", gate=_layer_gate(result), gate_code=code)
    return code


def _main(argv=None) -> int:
    """Legacy text-mode pipeline: parse with plain argparse (SystemExit on error/help)."""
    return _run(build_parser().parse_args(argv))


# ---------------------------------------------------------------------------
# JSON mode (schema 1): one bounded object on stdout; progress to stderr.
# ---------------------------------------------------------------------------

_ACTION_FLAGS = (
    ("--status", "status"), ("--usage", "usage"), ("--watch", "watch"),
    ("--integrate", "integrate"), ("--mark-repaired", "repair"),
    ("--migrate-ledger", "migrate"), ("--reconcile-plan", "reconcile"),
    ("--new-build", "new-build"), ("--step", "step"), ("--dry-run", "preview"),
)


def _scan_option(argv, name):
    """Best-effort raw scan for --name VALUE (or --name=VALUE) before parsing."""
    for i, token in enumerate(argv):
        if token == name:
            return argv[i + 1] if i + 1 < len(argv) else None
        if token.startswith(name + "="):
            return token.split("=", 1)[1]
    return None


def _guess_command(argv) -> str:
    for flag, command in _ACTION_FLAGS:
        if flag in argv:
            return command
    return "plan" if any(not a.startswith("-") for a in argv) else "unknown"


def _command_of(args) -> str:
    if args.status:
        return "status"
    if args.usage:
        return "usage"
    if args.watch:
        return "watch"
    if args.integrate:
        return "integrate"
    if args.mark_repaired:
        return "repair"
    if args.migrate_ledger:
        return "migrate"
    if args.reconcile_plan:
        return "reconcile"
    if args.new_build:
        return "new-build"
    if args.step:
        return "step"
    if args.dry_run:
        return "preview"
    return "plan"


def _paths_from(raw_repo, raw_ledger):
    """Resolve both fields using the same rules as the actual command."""
    raw_repo = raw_repo or "."
    repository = str(Path(raw_repo).resolve())
    return repository, resolve_ledger(repository, raw_ledger)


def _emit(response) -> int:
    print(cli_response.dumps(response))
    return response["gate_code"]


def _blocked(command, reason, *, raw_repo=None, raw_ledger=None, run_id=None, action="correct_input") -> int:
    repository, ledger = _paths_from(raw_repo, raw_ledger)
    response = cli_response.build(command=command, gate="blocked", run_id=run_id,
        repository=repository, ledger=ledger,
        errors=[cli_response.make_error(reason, action)])
    return _emit(response)


def _status_gate(ledger) -> str:
    """Truthful gate from persisted state; success never hides pending repair/integration."""
    if ledger.build is None:
        return "pending"  # empty state is explicit; no run is invented
    from collections import Counter
    from cld.integration import pending_integration
    build = ledger.build
    usage = build.get("usage")
    operation = build.get("last_operation") or {}
    if (usage or {}).get("blocked") or operation.get("gate_code") == 5:
        return "blocked"
    counts = Counter(e.status for e in ledger.entries.values())
    if counts["needs_repair"] or build.get("integration_failure"):
        return "needs_repair"
    if counts["failed"] or counts["deferred"]:
        return "failed"
    if pending_integration(ledger):
        return "integration_required"
    if ledger.entries and counts["integrated"] == len(ledger.entries) and build.get("integration_proof"):
        return "passed"
    return "pending"


def _usage_field(ledger) -> dict:
    """Local persisted usage only; unknown usage stays null (never invented)."""
    summary = (ledger.build or {}).get("usage")
    if summary:
        return {"attempts": summary.get("attempts", 0), "input": summary.get("input"),
                "output": summary.get("output"), "total": summary.get("total"),
                "cost": summary.get("cost")}
    entries = list(ledger.entries.values())

    def _sum(values):
        values = list(values)
        return None if not values or any(v is None for v in values) else sum(values)

    return {"attempts": sum(e.attempts for e in entries),
            "input": _sum(e.token_usage.get("input") for e in entries),
            "output": _sum(e.token_usage.get("output") for e in entries),
            "total": _sum(e.token_usage.get("total") for e in entries),
            "cost": _sum(e.cost for e in entries)}


def _budget_field(ledger) -> dict:
    policy = ((ledger.build or {}).get("usage") or {}).get("policy") or {}
    budget = cli_response.null_budget()
    budget.update({key: policy.get(key) for key in budget})
    return budget


def _artifacts_field(args, ledger) -> dict:
    if ledger is None or ledger.build is None:
        return {"run_directory": None, "events": None}
    try:
        directory = run_directory(args.repo, ledger.build["run_id"])
    except StateError:
        return {"run_directory": None, "events": None}
    return {"run_directory": str(directory), "events": str(directory / "events.jsonl")}


def _accepted_refs(ledger) -> list:
    """Accepted slice collections with exact commit/ref values retained."""
    refs = []
    for sid, entry in ledger.entries.items():
        if entry.status not in (DONE, "integrated"):
            continue
        collection = entry.collection or {}
        ref = collection.get("ref")
        commit = collection.get("commit") or entry.commit
        if ref is None and commit is None:
            continue
        refs.append({"slice": sid, "ref": ref, "commit": commit})
    return refs


def _ledger_response(command, gate, args, ledger, *, errors=None, extra=None):
    run_id = ledger.build["run_id"] if ledger is not None and ledger.build else None
    repository, ledger_path = _paths_from(args.raw_repo, args.raw_ledger)
    return cli_response.build(command=command, gate=gate, run_id=run_id,
        repository=repository, ledger=ledger_path,
        artifacts=_artifacts_field(args, ledger), usage=_usage_field(ledger),
        budget=_budget_field(ledger), accepted_refs=_accepted_refs(ledger),
        errors=errors, extra=extra)


def _slice_summary(ledger) -> dict:
    entries = list(ledger.entries.values())
    shown = entries[:50]
    extra = {"slice_count": len(entries),
             "slices": [{"slice_id": e.slice_id, "status": e.status, "model": e.model,
                         "attempts": e.attempts, "tokens": e.token_usage.get("total"),
                         "cost": e.cost} for e in shown]}
    if len(entries) > len(shown):
        extra["slices_truncated"] = True
    return extra


def _attempt_record(args, ledger):
    """Select one retained usage record, with containment + identity checks."""
    ident = args.attempt
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._-]{0,63}", ident or ""):
        return None, f"Invalid attempt id: {cli_response.bounded_text(ident, 100)}"
    if ledger.build is None:
        return None, "No run is bound; there are no retained usage records"
    try:
        run_dir = run_directory(args.repo, ledger.build["run_id"])
        usage_dir = run_dir / "usage"
    except StateError as exc:
        return None, str(exc)
    path = usage_dir / f"attempt-{ident}.json"
    try:
        contained = (usage_dir.resolve().is_relative_to(run_dir.resolve())
                     and path.resolve().is_relative_to(usage_dir.resolve()))
    except OSError:
        contained = False
    if not contained:
        return None, "Attempt id escapes the usage journal"
    if not path.is_file():
        return None, f"No retained usage record for attempt {ident}"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"Unreadable usage record: {exc}"
    if not isinstance(record, dict) or record.get("id") != ident:
        return None, "Usage record identity mismatch"
    if args.slice is not None and record.get("slice_id") != args.slice:
        return None, "Usage record does not belong to the selected slice"
    return cli_response.bound(record), None


def _detail(args, ledger):
    """Bounded --slice/--attempt detail. Returns (details, error_reason)."""
    details = {}
    if args.slice is not None:
        entry = ledger.get(args.slice)
        if entry is None:
            return None, f"Unknown slice: {args.slice}"
        details["slice_id"] = entry.slice_id
        details["slice"] = {"status": entry.status, "model": entry.model,
                            "attempts": entry.attempts, "tokens": entry.token_usage.get("total"),
                            "cost": entry.cost, "commit": entry.commit,
                            "complexity": entry.complexity, "final_rung": entry.final_rung,
                            "intervened": entry.intervened, "updated_at": entry.updated_at,
                            "recovery_path": entry.recovery_path, "worktree_path": entry.worktree_path}
    if args.attempt is not None:
        record, error = _attempt_record(args, ledger)
        if error is not None:
            return None, error
        details["attempt"] = record
    return details, None


def _load_ledger_or_blocked(command, args):
    try:
        ledger = Ledger.load(args.ledger)
        if ledger.build and ledger.build["repo"] != os.path.realpath(args.repo):
            raise StateError("Ledger belongs to another repository; use its original --repo")
        return ledger, None
    except (StateError, ValueError, OSError) as exc:
        return None, _blocked(command, str(exc), raw_repo=args.raw_repo, raw_ledger=args.raw_ledger)


def _json_status(args) -> int:
    ledger, blocked_rc = _load_ledger_or_blocked("status", args)
    if ledger is None:
        return blocked_rc
    gate = _status_gate(ledger)
    extra = {"details": {"state": "empty"}} if ledger.build is None else _slice_summary(ledger)
    if args.slice is not None or args.attempt is not None:
        details, error = _detail(args, ledger)
        if error is not None:
            return _emit(_ledger_response("status", "blocked", args, ledger,
                                          errors=[cli_response.make_error(error)]))
        extra["details"] = details
    errors = None
    if gate == "blocked":
        reason = ((ledger.build.get("usage") or {}).get("blocked")
                  or (ledger.build.get("last_operation") or {}).get("reason")
                  or "Build is blocked; inspect the ledger and correct the input")
        errors = [cli_response.make_error(reason)]
    return _emit(_ledger_response("status", gate, args, ledger, errors=errors, extra=extra))


def _json_usage(args) -> int:
    ledger, blocked_rc = _load_ledger_or_blocked("usage", args)
    if ledger is None:
        return blocked_rc
    extra = {}
    if args.slice is not None or args.attempt is not None:
        details, error = _detail(args, ledger)
        if error is not None:
            return _emit(_ledger_response("usage", "blocked", args, ledger,
                                          errors=[cli_response.make_error(error)]))
        extra["details"] = details
    return _emit(_ledger_response("usage", "pending", args, ledger, extra=extra))


def _json_preview(args) -> int:
    """Read-only command preview: layers, gate_code 0, and no state mutation."""
    def blocked(reason):
        return _blocked("preview", reason, raw_repo=args.raw_repo, raw_ledger=args.raw_ledger)
    if args.plan is None:
        return blocked("A plan file is required for preview")
    try:
        plan_md = Path(args.plan).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return blocked(f"Cannot read plan {args.plan}: {exc}")
    try:
        slices = load_slices(plan_md)
    except PlanError as exc:
        return blocked(str(exc))
    if not slices:
        return blocked("No slices found in plan")
    try:
        from cld.dag import parallel_batches
        layers = [list(layer) for layer in parallel_batches({s.id: list(s.deps) for s in slices})]
    except Exception as exc:
        return blocked(f"Cannot layer the plan: {exc}")
    repository, ledger_path = _paths_from(args.raw_repo, args.raw_ledger)
    return _emit(cli_response.build(command="preview", gate="pending", run_id=None,
        repository=repository, ledger=ledger_path,
        extra={"layers": layers, "slice_count": len(slices)}))


class _ProgressTee:
    """Redirect target: forwards progress to the real stderr and keeps a bounded tail."""

    def __init__(self, stream, limit=8000):
        self._stream = stream
        self._limit = limit
        self._tail = ""

    def write(self, text):
        self._stream.write(text)
        self._tail = (self._tail + text[-self._limit:])[-self._limit:]
        return len(text)

    def flush(self):
        self._stream.flush()

    def tail(self, limit=1500):
        return cli_response.bounded_text(self._tail.strip(), limit)


def _json_action(args) -> int:
    """Run a state/delivery action with stdout+stderr captured as progress, then
    emit exactly one JSON response describing the truthful resulting gate."""
    command = _command_of(args)
    tee = _ProgressTee(sys.stderr)
    code, reason = 5, None
    try:
        with contextlib.redirect_stdout(tee), contextlib.redirect_stderr(tee):
            code = _run(args)
    except (StateError, OwnerBusy, CaptureError, PlanError, EvidenceError, ValueError, OSError) as exc:
        code, reason = 5, str(exc)
    gate = cli_response.gate_for_code(code)
    try:
        ledger = Ledger.load(args.ledger)
    except Exception:
        ledger = None
    errors = None
    if code not in (0, 3, 6):
        if not reason and ledger is not None and ledger.build:
            reason = (ledger.build.get("last_operation") or {}).get("reason")
        if not reason:
            reason = tee.tail()
        if not reason:
            reason = {2: "Delivery failed; fix the cause and resume",
                      4: "Repair is required; inspect progress on stderr, repair, then resume",
                      5: "Request blocked; correct the input and retry"}.get(
                code, "Command did not complete; inspect progress on stderr")
        errors = [cli_response.make_error(reason, cli_response.next_action(gate))]
    if ledger is None:
        return _blocked(command, reason or "Ledger state is unavailable",
                        raw_repo=args.raw_repo, raw_ledger=args.raw_ledger)
    return _emit(_ledger_response(command, gate, args, ledger, errors=errors))


def _main_json(argv) -> int:
    if "--help" in argv or "-h" in argv:
        raw_repo, raw_ledger = _scan_option(argv, "--repo"), _scan_option(argv, "--ledger")
        repository, ledger_path = _paths_from(raw_repo, raw_ledger)
        return _emit(cli_response.build(command="help", gate="passed",
            repository=repository, ledger=ledger_path,
            extra={"details": {"usage": cli_response.bounded_text(build_parser().format_help(), 6000)}}))
    try:
        args = build_parser(json_mode=True).parse_args(argv)
    except _UsageError as exc:
        return _blocked(_guess_command(argv), str(exc),
                        raw_repo=_scan_option(argv, "--repo"), raw_ledger=_scan_option(argv, "--ledger"))
    args.json = True
    args.raw_repo = args.repo
    args.raw_ledger = args.ledger
    try:
        _validate(args)
    except (StateError, ValueError) as exc:
        return _blocked(_command_of(args), str(exc), raw_repo=args.raw_repo, raw_ledger=args.raw_ledger)
    _resolve_paths(args)
    if args.status:
        return _json_status(args)
    if args.usage:
        return _json_usage(args)
    if args.dry_run:
        return _json_preview(args)
    return _json_action(args)


def main(argv=None) -> int:
    # Windows consoles default to cp1252; force UTF-8 so output never crashes the run.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    argv = [str(a) for a in (sys.argv[1:] if argv is None else argv)]
    host = _scan_option(argv, "--host")
    if host:
        telemetry.set_host(host)
    try:
        if "--json" in argv:
            try:
                return _main_json(argv)
            except Exception as exc:
                # Machine callers must also receive structured diagnostics for
                # malformed optional state or an unexpected provider failure.
                return _blocked(_guess_command(argv), str(exc),
                    raw_repo=_scan_option(argv, "--repo"), raw_ledger=_scan_option(argv, "--ledger"))
        try:
            return _main(argv)
        except (StateError, OwnerBusy, CaptureError, PlanError, EvidenceError, ValueError) as exc:
            print(f"State blocked: {exc}", file=sys.stderr)
            return 5
    finally:
        telemetry.set_host(None)


if __name__ == "__main__":
    raise SystemExit(main())
