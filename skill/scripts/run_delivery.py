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

Exit code 0 if all slices accepted (or already done), 1 otherwise.
"""

import argparse
import os
import shlex
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
from cld.ledger import Ledger, DONE
from cld.orchestrator import run_plan_parallel
from cld.plan.slice import load_slices

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


def _events_path(repo_dir: str) -> str:
    """The build's local event stream: <repo>/.cld/events.jsonl (gitignored scratch)."""
    return os.path.join(os.path.abspath(repo_dir), ".cld", "events.jsonl")


def _read_event_stream(repo_dir: str) -> "list":
    """Load .cld/events.jsonl into a list of records (skips blank/torn lines). [] if absent."""
    import json
    events = []
    try:
        with open(_events_path(repo_dir), "r", encoding="utf-8") as f:
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
    """Install the JSONL telemetry sink + run_id for this build and emit run_start on a
    fresh build. A build spans many --step invocations (each a fresh process) that all
    APPEND to one stream; a brand-new build (ledger with no recorded slices) truncates the
    prior stream first. Best-effort: never blocks the build. Returns the events.jsonl path.
    """
    import uuid
    from cld import telemetry
    events_path = _events_path(repo_dir)
    try:
        os.makedirs(os.path.dirname(events_path), exist_ok=True)
        fresh = not ledger.entries  # no recorded slices yet => brand-new build
        if fresh:
            open(events_path, "w", encoding="utf-8").close()  # new build = fresh stream
            run_id = uuid.uuid4().hex[:8]
        else:
            run_id = _run_id_from_stream(events_path) or uuid.uuid4().hex[:8]
        telemetry.set_run_id(run_id)
        jsonl = telemetry.JsonlSink(events_path)
        otel = _maybe_otel_sink()  # +OTLP export when configured (else None -> JSONL only)
        telemetry.set_sink(telemetry.MultiSink([jsonl, otel]) if otel is not None else jsonl)
        if fresh:
            telemetry.emit("run_start", run_id=run_id,
                           plan=os.path.basename(plan_path), executor_default=default_spec)
    except Exception:
        pass
    return events_path


def _layer_gate(result) -> str:
    """Coarse gate label for a layer/run result, ASCII-safe."""
    if getattr(result, "needs_repair", None):
        return "needs_repair"
    if getattr(result, "failed", None):
        return "failed"
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
        return OtelSink(tracer=provider.get_tracer("cld"))
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
            br = f"slice-{dep}"
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
            print("   " + " && ".join(f"git merge slice-{d}" for d in unmerged))
            print(bar)
    except Exception:
        pass


def git_runner(args: list[str], cwd: str) -> tuple[int, str]:
    """Run a git command; return (returncode, combined output)."""
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return (proc.returncode, (proc.stdout or "") + (proc.stderr or ""))


def make_judge_fn(repo_dir: str):
    """Judge wrapper — delegates to cld.judge.judge with the run_tests deliver_slice
    supplies. The TRUSTWORTHY test output comes from `pytest_test_runner` (below),
    which deliver_slice invokes in the worktree; this just forwards it."""

    def judge_fn(*, files_changed, allowed, run_tests):
        return judge(files_changed=files_changed, allowed=allowed, run_tests=run_tests)

    return judge_fn


def pytest_test_runner(workdir: str, acceptance_test_path: str | None = None) -> str:
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
    until later slices land). We shlex.split it so the selector tokens reach pytest
    as separate args. Use forward slashes in paths (POSIX split); a bare path with
    no spaces/`::`/`-k` is unaffected.
    """
    target = shlex.split(acceptance_test_path) if acceptance_test_path else []

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

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *target, "-q"],
            cwd=workdir, env=env, capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return "__CLD_PYTEST_RC__=1\n1 failed in 600s (timeout — acceptance test did not complete)"
    # Prepend the pytest EXIT CODE as the authoritative pass/fail signal. The `-q` text
    # summary ("N passed") is unreliable on Windows capture (it can be omitted even when
    # pytest exits 0 — a real, deterministic case), so the judge must trust the rc, not
    # scrape the summary. (0=passed, 1=failed, 2=usage, 5=no tests collected.)
    return f"__CLD_PYTEST_RC__={proc.returncode}\n" + (proc.stdout or "") + (proc.stderr or "")


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
        return cmd
    found = shutil.which(cmd)
    return found if found else None


def _executor_cli_status() -> dict[str, str | None]:
    """Machine-independent contract: resolved CLI command per provider, or None if absent."""
    from cld_providers.antigravity.provider import _agy_cmd
    from cld_providers.cursor.provider import _cursor_invocation
    from cld_providers.opencode.provider import _oc_cmd

    status: dict[str, str | None] = {}
    status["antigravity"] = _resolve_cli(_agy_cmd())
    status["opencode"] = _resolve_cli(_oc_cmd())

    inv = _cursor_invocation()
    if len(inv) == 1:
        status["cursor"] = _resolve_cli(inv[0])
    else:
        node, script = inv[0], inv[1]
        node_ok = _resolve_cli(node) if not os.path.isabs(node) else (node if os.path.isfile(node) else None)
        status["cursor"] = script if node_ok and os.path.isfile(script) else None

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



def main(argv=None) -> int:
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
    p.add_argument("--ledger", default=".cld-ledger.json", help="Ledger file path")
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
                   help="Mark a needs_repair slice as repaired by the orchestrator (status=done, intervened) and exit. Use after fixing a gate-4 slice, before re-running --step.")
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

    # Handle --mark-repaired early, before reading the plan (it must not require the plan to exist)
    if args.mark_repaired:
        led = Ledger.load(args.ledger)
        led.set(args.mark_repaired, status=DONE, intervened=True, final_rung="orchestrator")
        led.save()
        print(f"marked {args.mark_repaired} repaired (done).")
        return 0

    if args.usage:
        from cld.usage import render_usage_table
        ledger = Ledger.load(args.ledger)
        print(render_usage_table(ledger))
        return 0

    if args.status:
        from cld.status import render_status
        print(render_status(_read_event_stream(args.repo)))
        return 0

    if args.watch:
        import time as _time
        from cld.status import render_status
        try:
            while True:
                print(render_status(_read_event_stream(args.repo)))
                print("-" * 48)
                _time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0

    if args.plan is None:
        print("A plan file is required for dispatch (or use --status/--usage/--mark-repaired).",
              file=sys.stderr)
        return 2

    plan_md = Path(args.plan).read_text(encoding="utf-8")
    slices = load_slices(plan_md)
    if not slices:
        print("No slices found in plan.", file=sys.stderr)
        return 1

    # Resolve the executor. If the user didn't pass --executor and we're attached to
    # an interactive terminal, show the model picker. Otherwise default to the engine's
    # default workhorse so automation / --step loops never block on a prompt (and never
    # resolve to a removed provider).
    if args.executor is None:
        if not args.dry_run and sys.stdin.isatty():
            try:
                args.executor = prompt_for_executor()
            except EOFError:
                # non-interactive stdin that still reports isatty (e.g. a backgrounded
                # run): fall back to the default instead of crashing the build.
                args.executor = _default_spec()
        else:
            args.executor = _default_spec()

    if args.dry_run:
        from cld.dag import parallel_batches
        deps = {s.id: list(s.deps) for s in slices}
        print(f"{len(slices)} slices. Execution layers (parallel batches):")
        for i, layer in enumerate(parallel_batches(deps)):
            print(f"  layer {i}: {', '.join(layer)}")
        return 0

    preflight_err = _preflight_executor(args.executor or _default_spec())
    if preflight_err:
        print(preflight_err)
        return 2

    git_err = _preflight_git(args.repo)
    if git_err:
        print(git_err)
        return 2

    # Install the local telemetry stream (zero-config) + emit run_start on a fresh build.
    ledger = Ledger.load(args.ledger)
    events_path = _install_telemetry(args.repo, ledger, args.plan, args.executor or _default_spec())
    print(f"telemetry: {os.path.relpath(events_path, os.path.abspath(args.repo))} (local)")
    print(_otel_status_line())

    if args.step:
        from cld.orchestrator import next_pending_layer
        from cld.summary import classify_gate, summarize_layer, write_artifacts
        from cld import telemetry
        sel = next_pending_layer(slices, ledger)
        if sel is None:
            print("BUILD COMPLETE — no pending layers.")
            return 3
        idx, layer_ids, total = sel
        layer_slices = [s for s in slices if s.id in layer_ids]
        _warn_unmerged_deps(args.repo, slices, ledger, layer_ids)  # caller-merge preflight
        telemetry.emit("layer_start", layer=idx, slice_ids=list(layer_ids), total=total)
        judge_fn = make_judge_fn(args.repo)
        result = run_plan_parallel(
            layer_slices, ledger,
            executor_factory=build_executor_factory(),
            default_spec=args.executor or _default_spec(),
            rung_planner=build_rung_planner(args.executor or _default_spec()),
            judge_fn=judge_fn,
            max_workers=args.workers,
            repo_dir=args.repo, git_runner=git_runner,
            test_runner=pytest_test_runner,
        )
        write_artifacts(result, repo_dir=args.repo)
        nxt = next_pending_layer(slices, ledger)
        telemetry.emit("layer_done", layer=idx, gate=_layer_gate(result))
        if nxt is None:
            telemetry.emit("run_done", gate=_layer_gate(result))
        next_layer = nxt[1] if nxt else []
        print(summarize_layer(result, layer_index=idx, total_layers=total,
                              next_layer=next_layer))
        return classify_gate(result, more_layers=bool(nxt))

    judge_fn = make_judge_fn(args.repo)

    result = run_plan_parallel(
        slices, ledger,
        executor_factory=build_executor_factory(),
        default_spec=args.executor or _default_spec(),
        rung_planner=build_rung_planner(args.executor or _default_spec()),
        judge_fn=judge_fn,
        max_workers=args.workers,
        repo_dir=args.repo, git_runner=git_runner,
        test_runner=pytest_test_runner,  # REAL pytest in the worktree = the judge signal
    )
    from cld import telemetry as _tel
    _tel.emit("run_done", gate=_layer_gate(result))

    print(f"completed: {result.completed}")
    print(f"failed:    {result.failed}")
    print(f"skipped:   {result.skipped}")
    print(f"deferred:  {result.deferred}")
    return 0 if not result.failed and not result.deferred else 1


if __name__ == "__main__":
    raise SystemExit(main())
