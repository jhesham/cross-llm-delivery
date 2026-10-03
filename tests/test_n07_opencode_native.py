"""N07 native OpenCode launch acceptance; local Python or fake processes only."""
from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import sys

import pytest

from cld import cli
from cld.executors.base import SliceTask
from cld.native_cli import NativeCliError, NativeCommand, resolve_native
from cld_providers.opencode import provider


@pytest.fixture(autouse=True)
def lead(monkeypatch):
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)
    monkeypatch.delenv("OPENCODE_CLI_CMD", raising=False)


def resolver():
    try:
        module = importlib.import_module("cld_providers.opencode.launcher")
    except ModuleNotFoundError:
        raise AssertionError("Add the shared native OpenCode resolver") from None
    function = getattr(module, "resolve_opencode_command", None)
    assert callable(function), "Add resolve_opencode_command"
    return function


def binary(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ")
    return path.resolve()


def blocked(call):
    try:
        call()
    except NativeCliError as exc:
        assert "OPENCODE_CLI_CMD" in str(exc)
        return str(exc)
    raise AssertionError("Unusable OpenCode launch must fail closed")


def test_windows_native_only_path_without_npm(tmp_path):
    native = binary(tmp_path / "standalone tool/opencode.exe")
    seen = []
    def which(name):
        seen.append(name)
        return str(native) if name == "opencode.exe" else None
    command = resolver()(env={}, which=which, os_name="nt")
    assert command.path == str(native) and command.env == {}
    assert seen == ["opencode.exe"]


def test_override_wins_without_path_lookup(tmp_path):
    native = binary(tmp_path / "custom tool/opencode.exe")
    def forbidden(name):
        raise AssertionError("Override must precede PATH")
    assert resolver()(env={"OPENCODE_CLI_CMD": str(native)}, which=forbidden,
                      os_name="nt").path == str(native)


def test_native_path_wins_over_shim(tmp_path):
    native = binary(tmp_path / "native/opencode.exe")
    shim = binary(tmp_path / "npm/opencode.cmd")
    paths = {"opencode.exe": str(native), "opencode.cmd": str(shim)}
    assert resolver()(env={}, which=paths.get, os_name="nt").path == str(native)


def test_verified_npm_postinstall_target(tmp_path):
    shim = binary(tmp_path / "npm prefix/opencode.cmd")
    native = binary(shim.parent / "node_modules/opencode-ai/bin/opencode.exe")
    command = resolver()(env={}, which=lambda name: str(shim) if name == "opencode.cmd" else None,
                         os_name="nt")
    assert command.path == str(native) and command.env == {}


@pytest.mark.parametrize("layout", ["missing", "shim-only", "directory-target"])
def test_incomplete_install_fails_with_native_override_guidance(tmp_path, layout):
    shim = binary(tmp_path / "opencode.cmd")
    if layout == "directory-target":
        (tmp_path / "node_modules/opencode-ai/bin/opencode.exe").mkdir(parents=True)
    which = (lambda name: str(shim) if name == "opencode.cmd" else None) if layout != "missing" else lambda name: None
    message = blocked(lambda: resolver()(env={}, which=which, os_name="nt"))
    if layout != "missing":
        assert str(shim) in message


@pytest.mark.parametrize("override", ["", "opencode", "./relative/opencode.exe"])
def test_bad_override_is_not_silently_replaced(override):
    blocked(lambda: resolver()(env={"OPENCODE_CLI_CMD": override}, which=lambda name: None, os_name="nt"))


@pytest.mark.parametrize("suffix", [".cmd", ".bat"])
def test_shared_windows_resolver_rejects_explicit_shell_shims(tmp_path, suffix):
    shim = binary(tmp_path / ("opencode" + suffix))
    blocked(lambda: resolve_native(logical="opencode", override_var="OPENCODE_CLI_CMD",
        npm_candidates=lambda directory: (), env={"OPENCODE_CLI_CMD": str(shim)},
        which=lambda name: None, os_name="nt"))


def test_posix_path_is_resolved_without_windows_rules(tmp_path):
    native = binary(tmp_path / "opencode")
    command = resolver()(env={}, which=lambda name: str(native) if name == "opencode" else None,
                         os_name="posix")
    assert command.path == str(native)


@dataclass
class Proc:
    stdout: str = ""
    returncode: int = 0
    error: str | None = None
    def __iter__(self):
        return iter((self.returncode, self.stdout))


def install_resolver(monkeypatch, value):
    resolver()  # Baseline must fail before any real OpenCode launch.
    assert callable(getattr(provider, "resolve_opencode_command", None))
    monkeypatch.setattr(provider, "resolve_opencode_command", value)


def test_same_native_selection_for_preflight_discovery_stats_and_dispatch(tmp_path, monkeypatch):
    native = binary(tmp_path / "native tool/opencode.exe")
    install_resolver(monkeypatch, lambda: NativeCommand(str(native), {"N07_LAUNCH_ENV": "kept"}))
    calls = []
    def process(argv, cwd, **options):
        calls.append((argv, cwd, options))
        if argv[1:] == ["models"]:
            return Proc("vendor/exact-model\n")
        if argv[1:] == ["stats"]:
            return Proc("synthetic stats")
        return Proc('{"type":"step_finish","part":{"tokens":{"input":3,"output":2}}}')
    monkeypatch.setattr(provider, "run_process", process)
    monkeypatch.setattr(provider, "capture_diff", lambda runner, cwd: ("DIFF", ["target.py"]))
    assert provider._oc_cmd() == str(native)
    assert provider.PROVIDER.cli_invocation() == [str(native)]
    assert callable(provider.PROVIDER.launch_problem) and provider.PROVIDER.launch_problem() is None
    monkeypatch.setattr(cli, "_executor_cli_status", lambda: {"opencode": str(native)})
    assert cli._preflight_executor("opencode:vendor/exact-model") is None
    assert provider.list_models(provider._default_runner) == ["vendor/exact-model"]
    assert provider.account_stats() == "synthetic stats"
    payload = 'line Ω café "quotes" $HOME & | < > ^\n' * 260
    cancel = object()
    task = SliceTask("N07", payload, ["target.py"], "test_target.py")
    result = provider.OpenCodeExecutor(model="vendor/exact-model", effort="high", timeout=43,
        cancel=cancel, artifact_dir=tmp_path / "artifacts").run(task, tmp_path)
    assert result.ok and result.diff == "DIFF" and result.files_changed == ["target.py"]
    assert len(calls) == 3 and all(argv[0] == str(native) for argv, _, _ in calls)
    argv, cwd, options = calls[-1]
    assert payload in argv[2] and argv[argv.index("-m") + 1] == "vendor/exact-model"
    assert argv[argv.index("--variant") + 1] == "high" and argv[-1] == "--port"
    assert argv[argv.index("--dir") + 1] == str(tmp_path) and cwd == str(tmp_path)
    assert options["env"]["CLD_EXECUTOR_DEPTH"] == "1"
    assert options["env"]["N07_LAUNCH_ENV"] == "kept"
    assert options["timeout"] == 43 and options["cancel"] is cancel
    assert options["artifact_dir"] == tmp_path / "artifacts"


def test_native_failure_blocks_process_diff_and_discovery(tmp_path, monkeypatch):
    def missing():
        raise NativeCliError("Only npm shim found; set OPENCODE_CLI_CMD to a native executable")
    install_resolver(monkeypatch, missing)
    def forbidden(*args, **kwargs):
        raise AssertionError("An unusable native launch reached a process or diff")
    monkeypatch.setattr(provider, "run_process", forbidden)
    monkeypatch.setattr(provider, "capture_diff", forbidden)
    result = provider.OpenCodeExecutor().run(SliceTask("N07", "brief", ["x.py"], "test_x.py"), tmp_path)
    assert not result.ok and result.process["error"] == "missing_binary" and not result.diff
    assert "OPENCODE_CLI_CMD" in result.raw_log
    assert provider.list_models(provider._default_runner) == []
    assert provider.account_stats() == ""
    monkeypatch.setattr(cli, "_executor_cli_status", lambda: {"opencode": "opencode.cmd"})
    assert "OPENCODE_CLI_CMD" in cli._preflight_executor("opencode:vendor/exact-model")


def test_real_native_local_child_preserves_long_multiline_unicode_argv(tmp_path, monkeypatch):
    resolver()
    monkeypatch.setenv("OPENCODE_CLI_CMD", str(Path(sys.executable).resolve()))
    payload = 'line Ω café "quotes" $HOME & | < > ^\n' * 260
    argv = ["opencode", "-I", "-S", "-c", "import json,sys;print(json.dumps(sys.argv[1:]))", payload]
    result = provider._default_runner(argv, str(tmp_path), timeout=30)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout) == [payload]
    assert argv[0] == "opencode", "The caller's argv must not be mutated"


def test_unrelated_commands_and_two_argument_injected_runners_do_not_resolve(tmp_path, monkeypatch):
    def forbidden():
        raise AssertionError("Unrelated or injected runner must not require an installed OpenCode")
    install_resolver(monkeypatch, forbidden)
    calls = []
    monkeypatch.setattr(provider, "run_process", lambda argv, cwd, **kwargs: calls.append(argv) or Proc("ok"))
    assert tuple(provider._default_runner(["git", "status"], str(tmp_path))) == (0, "ok")
    def legacy(argv, cwd):
        calls.append(argv)
        return 1, "synthetic failure"
    result = provider.OpenCodeExecutor(runner=legacy).run(
        SliceTask("N07", "brief", ["x.py"], "test_x.py"), tmp_path)
    assert not result.ok and len(calls) == 2 and calls[-1][0] == "opencode"
