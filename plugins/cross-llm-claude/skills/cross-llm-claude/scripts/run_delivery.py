#!/usr/bin/env python
"""Drive a cross-llm-delivery run from a plan file.

Thin backward-compatible entrypoint: all reusable command handling lives in the
engine (`cld.cli`; also runnable as `python -m cld`). This module re-exports the
driver's names so importlib-based callers and tests can keep monkeypatching its
attributes; `cld.cli.hooks_from` binds this module's namespace while delegating,
so those patches stay visible at the engine's call sites.

Usage:
    python run_delivery.py <plan.md> [--repo <dir>] [--ledger <path>]
                           [--workers N] [--dry-run] [--json] [--host NAME]

The plan is markdown with one block per slice (see cld.plan.slice.load_slices):

    ## SLICE: T1
    brief: <natural-language task / spec>
    files: src/a.py, tests/test_a.py
    acceptance_test_path: tests/test_a.py
    deps:

Exit 3 means verified integration is complete; 6 means accepted work awaits integration.
Exit 0 means more work remains; 2 is failure/defer, 4 repair, and 5 invalid state.
"""

import functools
import os
import shutil  # noqa: F401  (re-exported; tests monkeypatch shutil.which here)
import sys

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

from cld import cli as _cli

# --- Plain re-exports: names callers read or monkeypatch on this module. ------
Ledger = _cli.Ledger
DONE = _cli.DONE
StateError = _cli.StateError
resolve_ledger = _cli.resolve_ledger
OwnerBusy = _cli.OwnerBusy
run_directory = _cli.run_directory
PlanError = _cli.PlanError
EvidenceError = _cli.EvidenceError
CaptureError = _cli.CaptureError
TestRun = _cli.TestRun
KNOWN_EXECUTORS = tuple(provider.name for provider in _cli.all_providers())
load_providers = _cli.load_providers
get_provider = _cli.get_provider
all_providers = _cli.all_providers
default_workhorse = _cli.default_workhorse
get_executor = _cli.get_executor
judge = _cli.judge
acceptance_args = _cli.acceptance_args
run_process = _cli.run_process
run_plan_parallel = _cli.run_plan_parallel
load_slices = _cli.load_slices
git_runner = _cli.git_runner
make_judge_fn = _cli.make_judge_fn
parse_executor_spec = _cli.parse_executor_spec
prompt_for_executor = _cli.prompt_for_executor
hooks_from = _cli.hooks_from
_default_spec = _cli._default_spec
_default_provider = _cli._default_provider
_parse_name_model = _cli._parse_name_model
_provider_of_spec = _cli._provider_of_spec
_install_hint = _cli._install_hint
_is_git_repo = _cli._is_git_repo
_available_ids_for = _cli._available_ids_for
_resolve_cli = _cli._resolve_cli
_events_path = _cli._events_path
_read_event_stream = _cli._read_event_stream
_run_id_from_stream = _cli._run_id_from_stream
_install_telemetry = _cli._install_telemetry
_dispatch_needed = _cli._dispatch_needed
_record_operation = _cli._record_operation
_layer_gate = _cli._layer_gate
_otel_target_from_env = _cli._otel_target_from_env
_maybe_otel_sink = _cli._maybe_otel_sink
_otel_status_line = _cli._otel_status_line


def _wrap(fn):
    """Delegate to an engine function with THIS module's namespace hook-bound,
    so monkeypatches of the re-exported names above take effect inside cld.cli."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _cli.hooks_from(globals()):
            result = fn(*args, **kwargs)
        # Admission returns deferred factories/planners that may be called
        # later by legacy import-based clients, after the initial hook scope.
        if callable(result):
            return _wrap(result)
        if isinstance(result, tuple):
            return tuple(_wrap(value) if callable(value) else value for value in result)
        return result
    return wrapper


# --- Bound delegates: engine functions that consult monkeypatchable seams. ----
main = _wrap(_cli.main)
_main = _wrap(_cli._main)
_run = _wrap(_cli._run)
_execute = _wrap(_cli._execute)
prepare_dispatch = _wrap(_cli.prepare_dispatch)
pytest_test_runner = _wrap(_cli.pytest_test_runner)
build_executor_factory = _wrap(_cli.build_executor_factory)
build_rung_planner = _wrap(_cli.build_rung_planner)
_preflight_git = _wrap(_cli._preflight_git)
_preflight_executor = _wrap(_cli._preflight_executor)
_executor_cli_status = _wrap(_cli._executor_cli_status)
_render_build_status = _wrap(_cli._render_build_status)
_warn_unmerged_deps = _wrap(_cli._warn_unmerged_deps)

if __name__ == "__main__":
    raise SystemExit(main())
