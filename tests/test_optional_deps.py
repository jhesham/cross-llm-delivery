"""The engine must import + run on a fresh machine WITHOUT the optional third-party
deps (deepeval for behavioral judging, opentelemetry for dashboards). Both "degrade to a
no-op when absent" — this pins that contract by importing the engine in a subprocess where
those packages are un-importable (simulating a clean install with only stdlib + an executor CLI).
"""
import os
import subprocess
import sys
from pathlib import Path

ENGINE = str((Path(__file__).resolve().parents[1] / "engine"))


def _run_blocked(probe: str):
    blocker = (
        "import sys\n"
        "class _Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in ('langfuse', 'deepeval', 'opentelemetry'):\n"
        "            raise ImportError('blocked for test: ' + name)\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Block())\n"
        "for m in [x for x in sys.modules if x.split('.')[0] in ('langfuse','deepeval')]:\n"
        "    del sys.modules[m]\n"
    )
    return subprocess.run(
        [sys.executable, "-c", blocker + probe],
        env={**os.environ, "PYTHONPATH": ENGINE},
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_orchestrator_imports_without_optional_deps():
    # the engine must import cleanly with no third-party packages present
    r = _run_blocked("import cld.orchestrator; print('OK')\n")
    assert "OK" in r.stdout, (r.stdout + r.stderr)


def test_telemetry_otel_sink_is_noop_without_opentelemetry():
    # OtelSink must degrade to a no-op when opentelemetry isn't installed (guarded).
    probe = (
        "from cld.telemetry import OtelSink\n"
        "OtelSink(tracer=None).emit({'type': 'dispatch_start', 'slice_id': 'T'})\n"  # must not raise
        "print('OK')\n"
    )
    r = _run_blocked(probe)
    assert "OK" in r.stdout, (r.stdout + r.stderr)


def test_behavioral_module_imports_without_deepeval():
    # importing cld.behavioral must not crash when deepeval is absent; using it without
    # deepeval should fail loudly only when actually called.
    probe = (
        "import cld.behavioral as b\n"
        "try:\n"
        "    b.make_compliance_metric()\n"
        "    print('NO_RAISE')\n"
        "except ImportError:\n"
        "    print('OK')\n"
    )
    r = _run_blocked(probe)
    assert "OK" in r.stdout, (r.stdout + r.stderr)


def test_run_delivery_help_without_optional_deps():
    # the real entry point a fresh install runs first
    driver = str(Path(__file__).resolve().parents[1] / "skill" / "scripts" / "run_delivery.py")
    r = _run_blocked(f"import runpy, sys; sys.argv=['run_delivery.py','--help'];"
                     f"\ntry:\n runpy.run_path(r'{driver}', run_name='__main__')\nexcept SystemExit:\n pass\nprint('OK')\n")
    assert "OK" in r.stdout, (r.stdout + r.stderr)
