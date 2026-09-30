"""v0.3.1 fixes 4 and 7c: resolve the native Codex binary without a shell.

CLD slice CODEX_LAUNCHER. Red by AssertionError only: modules resolved lazily.
"""
import importlib
import json
from pathlib import Path

import pytest

from cld.executors.base import SliceTask

TRIPLE = "x86_64-pc-windows-msvc"


def _module(name):
    try:
        module = importlib.import_module(name)
    except ImportError:
        module = None
    assert module is not None, f"{name} not implemented"
    return module


def _launcher():
    return _module("cld_providers.codex.launcher")


def _file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ")
    return path


def _resolve(**kw):
    return _launcher().resolve_codex_command(**kw)


def test_override_must_be_absolute_existing_file(tmp_path):
    exe = _file(tmp_path / "codex.exe")
    assert _resolve(env={"CODEX_CLI_CMD": str(exe)}, which=lambda n: None, os_name="nt").path == str(exe)
    with pytest.raises(_launcher().CodexLauncherError):
        _resolve(env={"CODEX_CLI_CMD": "codex.exe"}, which=lambda n: None, os_name="nt")


def test_windows_prefers_exe_on_path(tmp_path):
    exe = _file(tmp_path / "bin" / "codex.exe")
    command = _resolve(env={}, which=lambda n: str(exe) if n == "codex.exe" else None, os_name="nt")
    assert command.path == str(exe) and command.env == {}


@pytest.mark.parametrize("layout", [
    "node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/{t}/bin/codex.exe",
    "node_modules/@openai/codex-win32-x64/vendor/{t}/bin/codex.exe",
    "node_modules/@openai/codex/vendor/{t}/bin/codex.exe",
], ids=["nested", "hoisted", "legacy"])
def test_windows_npm_native_behind_shim(tmp_path, layout):
    shim = _file(tmp_path / "codex.cmd")
    native = _file(tmp_path / layout.format(t=TRIPLE))
    command = _resolve(env={}, which=lambda n: str(shim) if n == "codex.cmd" else None,
                       os_name="nt", machine="AMD64")
    assert Path(command.path) == native
    assert command.env["CODEX_MANAGED_BY_NPM"] == "1"
    assert Path(command.env["CODEX_MANAGED_PACKAGE_ROOT"]) == tmp_path / "node_modules/@openai/codex"


def test_windows_arm64_triple(tmp_path):
    shim = _file(tmp_path / "codex.cmd")
    native = _file(tmp_path / "node_modules/@openai/codex-win32-arm64/vendor/aarch64-pc-windows-msvc/bin/codex.exe")
    command = _resolve(env={}, which=lambda n: str(shim) if n == "codex.cmd" else None,
                       os_name="nt", machine="ARM64")
    assert Path(command.path) == native


def test_shim_only_names_override(tmp_path):
    shim = _file(tmp_path / "codex.cmd")
    with pytest.raises(_launcher().CodexLauncherError, match="CODEX_CLI_CMD") as info:
        _resolve(env={}, which=lambda n: str(shim) if n == "codex.cmd" else None, os_name="nt")
    assert str(shim) in str(info.value)


def test_nothing_found(tmp_path):
    with pytest.raises(_launcher().CodexLauncherError, match="CODEX_CLI_CMD"):
        _resolve(env={}, which=lambda n: None, os_name="nt")


def test_posix_uses_path(tmp_path):
    exe = _file(tmp_path / "codex")
    assert _resolve(env={}, which=lambda n: str(exe) if n == "codex" else None, os_name="posix").path == str(exe)


def test_resolved_runner_substitutes_binary_and_env():
    provider = _module("cld_providers.codex.provider")
    resolved_runner = getattr(provider, "resolved_runner", None)
    assert resolved_runner is not None, "resolved_runner not implemented"
    command = _launcher().CodexCommand("/abs/codex", {"CODEX_MANAGED_BY_NPM": "1", "CLD_EXECUTOR_DEPTH": "9"})
    calls = []

    def fake(argv, cwd, **kwargs):
        calls.append((argv, cwd, kwargs))
        return "ok"

    run = resolved_runner(fake, resolve=lambda: command)
    assert run(["codex", "exec", "-"], "/w", env={"CLD_EXECUTOR_DEPTH": "1"}, stdin="p") == "ok"
    argv, cwd, kwargs = calls[0]
    assert argv == ["/abs/codex", "exec", "-"] and cwd == "/w"
    assert kwargs["env"] == {"CODEX_MANAGED_BY_NPM": "1", "CLD_EXECUTOR_DEPTH": "1"}
    assert kwargs["stdin"] == "p"


def test_executor_reports_unresolvable_cli_before_any_process(tmp_path, monkeypatch):
    provider = _module("cld_providers.codex.provider")
    launcher = _launcher()
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)

    def boom():
        raise launcher.CodexLauncherError("Only the npm shim was found; set CODEX_CLI_CMD")

    monkeypatch.setattr(provider, "resolve_codex_command", boom, raising=False)
    (tmp_path / ".git").mkdir()
    result = provider.CodexExecutor(model="gpt-x", effort="low").run(
        SliceTask("s", "b", ["a.py"], "test_a.py"), tmp_path)
    assert result.ok is False
    assert result.process.get("error") == "missing_binary"
    assert "CODEX_CLI_CMD" in result.raw_log


def test_provider_launch_problem_and_invocation(monkeypatch):
    provider = _module("cld_providers.codex.provider")
    launcher = _launcher()
    launch_problem = getattr(provider.PROVIDER, "launch_problem", None)
    assert launch_problem is not None, "PROVIDER.launch_problem not implemented"
    monkeypatch.setattr(provider, "resolve_codex_command",
                        lambda: launcher.CodexCommand("/abs/codex", {}), raising=False)
    assert launch_problem() is None
    assert provider.PROVIDER.cli_invocation() == ["/abs/codex"]

    def boom():
        raise launcher.CodexLauncherError("shim only; set CODEX_CLI_CMD")

    monkeypatch.setattr(provider, "resolve_codex_command", boom, raising=False)
    assert "CODEX_CLI_CMD" in launch_problem()
    assert provider.PROVIDER.cli_invocation() == ["codex"]


def test_catalog_keeps_unicode_labels():
    from cld_providers.codex.catalog import list_codex_models
    raw = json.dumps({"models": [{"slug": "gpt-x", "visibility": "list", "display_name": "GPT-X ✦",
                                  "supported_reasoning_levels": [{"effort": "low"}]}]})
    models = list_codex_models(runner=lambda argv, cwd: (0, raw))
    assert models[0].label == "GPT-X ✦"


def test_default_discovery_without_resolvable_cli_still_uses_process_runner(monkeypatch):
    """CI has no Codex CLI: an unresolvable binary must not hide an injected process runner."""
    from cld_providers.codex import catalog as module
    launcher = _launcher()
    raw = json.dumps({"models": [{"slug": "gpt-x", "visibility": "list", "display_name": "GPT-X",
                                  "supported_reasoning_levels": [{"effort": "low"}]}]})
    calls = []

    class Result:
        returncode, stdout, error = 0, raw, None

    def process(argv, cwd, **kwargs):
        calls.append((argv, kwargs))
        return Result()

    def boom():
        raise launcher.CodexLauncherError("not installed; set CODEX_CLI_CMD")

    monkeypatch.setattr(module, "resolve_codex_command", boom)
    monkeypatch.setattr(module, "run_process", process)
    assert [m.id for m in module.list_codex_models()] == ["gpt-x"]
    assert calls[0][0][0] == "codex" and "env" not in calls[0][1]
