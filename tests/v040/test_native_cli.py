"""v0.4.0: one shared native-CLI launcher; R07; Claude resolution."""
from pathlib import Path

import pytest

from cld.native_cli import NativeCliError, NativeCommand, resolve_native, resolved_runner  # noqa: F401
from cld_providers.claude.launcher import resolve_claude_command


def _file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ")
    return path


def test_resolved_runner_rewrites_logical_name_and_merges_env():
    calls = []
    run = resolved_runner(lambda argv, cwd, **kw: calls.append((argv, kw)) or "ok",
                          lambda: NativeCommand("/abs/tool", {"A": "1", "B": "2"}), logical="tool")
    run(["tool", "x"], "/w", env={"B": "caller"}, unset_env=("K",))
    assert calls == [(["/abs/tool", "x"], {"env": {"A": "1", "B": "caller"}, "unset_env": ("K",)})]


def test_claude_override_and_exe(tmp_path):
    exe = _file(tmp_path / "claude.exe")
    assert resolve_claude_command(env={"CLAUDE_CLI_CMD": str(exe)}, which=lambda n: None, os_name="nt").path == str(exe)
    assert resolve_claude_command(env={}, which=lambda n: str(exe) if n == "claude.exe" else None, os_name="nt").path == str(exe)


def test_claude_native_behind_npm_shim(tmp_path):
    shim = _file(tmp_path / "claude.cmd")
    native = _file(tmp_path / "node_modules/@anthropic-ai/claude-code/bin/claude.exe")
    command = resolve_claude_command(env={}, which=lambda n: str(shim) if n == "claude.cmd" else None, os_name="nt")
    assert Path(command.path) == native and command.env == {}


def test_claude_shim_only_names_override(tmp_path):
    shim = _file(tmp_path / "claude.cmd")
    with pytest.raises(NativeCliError, match="CLAUDE_CLI_CMD") as info:
        resolve_claude_command(env={}, which=lambda n: str(shim) if n == "claude.cmd" else None, os_name="nt")
    assert str(shim) in str(info.value)


def test_claude_posix_and_relative_override(tmp_path):
    exe = _file(tmp_path / "claude")
    assert resolve_claude_command(env={}, which=lambda n: str(exe) if n == "claude" else None, os_name="posix").path == str(exe)
    with pytest.raises(NativeCliError):
        resolve_claude_command(env={"CLAUDE_CLI_CMD": "claude"}, which=lambda n: None, os_name="nt")


def test_codex_aliases_preserved():
    from cld_providers.codex import launcher
    assert launcher.CodexCommand is NativeCommand and launcher.CodexLauncherError is NativeCliError


def test_r07_custom_git_runner_keeps_native_resolution(tmp_path, monkeypatch):
    import sys
    from cld.executors.base import SliceTask
    from cld_providers.codex import provider
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)
    calls = []
    monkeypatch.setattr(provider, "resolve_codex_command",
                        lambda: calls.append(1) or NativeCommand(sys.executable, {}))
    (tmp_path / ".git").mkdir()
    result = provider.CodexExecutor(model="gpt-x", effort="low",
                                    git_runner=lambda argv, cwd: (0, "")).run(
        SliceTask("s", "b", ["a.py"], "test_a.py"), tmp_path)
    assert calls == [1]  # native resolution ran despite the injected Git runner
    # The stand-in binary (python) passes --version but fails `exec --help`.
    assert result.ok is False and result.process.get("error") in ("nonzero_exit", "missing_capability")
