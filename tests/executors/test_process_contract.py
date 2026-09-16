"""Production provider wiring with a synthetic process, never a provider CLI."""
import importlib
import sys
import threading
from pathlib import Path

import pytest

from cld.executors.base import SliceTask
from cld.process import run_process


@pytest.mark.parametrize("name,cls", [("opencode", "OpenCodeExecutor"), ("cursor", "CursorExecutor"),
                                      ("antigravity", "AntigravityExecutor")])
@pytest.mark.parametrize("mode", ["timeout", "cancelled", "authentication", "malformed_output"])
def test_provider_default_runner_lifecycle(tmp_path, monkeypatch, name, cls, mode):
    provider = importlib.import_module(f"cld_providers.{name}.provider")
    seen = []
    code = "import sys,time; print('partial',flush=True); print('diagnostic',file=sys.stderr,flush=True); "
    if mode in ("timeout", "cancelled"):
        code += "time.sleep(60)"
    elif mode == "authentication":
        code += "print('authentication failed',file=sys.stderr); sys.exit(1)"
    else:
        code += "print('not a completion')"

    def local(argv, cwd, **kwargs):
        seen.append((argv, cwd, kwargs))
        return run_process([sys.executable, "-c", code], cwd, **kwargs)

    monkeypatch.setattr(provider, "run_process", local)
    event = threading.Event()
    timer = threading.Timer(.5, event.set) if mode == "cancelled" else None
    options = dict(timeout=.8, cancel=event, artifact_dir=tmp_path / "artifacts")
    if name == "antigravity":
        options["home"] = str(tmp_path)
    executor = getattr(provider, cls)(**options)
    if timer:
        timer.start()
    try:
        result = executor.run(SliceTask("T", "do work", ["x"], "test_x.py"), tmp_path)
    finally:
        if timer:
            timer.cancel()
    assert not result.ok and result.process["error"] == mode
    assert len(seen) == 1  # Never capture a diff on a failed dispatch.
    assert seen[0][2]["timeout"] == .8
    assert len(result.raw_log) <= 4000
    assert "partial" in Path(result.process["stdout_path"]).read_text()
    assert "diagnostic" in Path(result.process["stderr_path"]).read_text()
    if name == "antigravity":
        assert Path(result.process["provider_log_path"]).exists()


def test_dispatch_and_probe_environment_deadlines(tmp_path, monkeypatch):
    from cld_providers.opencode import provider
    monkeypatch.setenv("CLD_PROBE_TIMEOUT", "0.15")
    monkeypatch.setenv("CLD_DISPATCH_TIMEOUT", "0.2")
    actual = run_process
    seen = []

    def local(argv, cwd, **kwargs):
        result = actual([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, **kwargs)
        seen.append(result)
        return result

    monkeypatch.setattr(provider, "run_process", local)
    assert provider.list_models(provider._default_runner) == []
    result = provider.OpenCodeExecutor().run(SliceTask("T", "brief", ["x"], "test_x.py"), tmp_path)
    assert result.process["error"] == "timeout"
    assert len(seen) == 2 and all(p.error == "timeout" and p.elapsed < 3 for p in seen)
