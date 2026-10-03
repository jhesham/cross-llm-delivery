"""N08 native cwd acceptance: local subprocesses/fake runners, no inference."""
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
from types import SimpleNamespace

import pytest

from cld.executors.base import SliceTask
from cld.process import run_process
from cld_providers.antigravity import provider


@pytest.fixture(autouse=True)
def lead(monkeypatch):
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)


def task():
    return SliceTask("N08", "offline cwd check", ["x.py"], "test_x.py")


@pytest.mark.parametrize("home,system_drive", [
    ("/home/cld-review", None), ("/Users/cld-review", "C:"),
    ("/tmp/native home Ω", "Z:"),
])
def test_posix_home_is_not_transformed(home, system_drive, monkeypatch):
    class NativePath(PurePosixPath):
        @classmethod
        def home(cls):
            return cls(home)
    env = {} if system_drive is None else {"SystemDrive": system_drive}
    monkeypatch.setattr(provider, "Path", NativePath)
    monkeypatch.setattr(provider, "os", SimpleNamespace(name="posix", environ=env, sep="/"))
    assert provider._dispatch_cwd() == home
    assert PurePosixPath(provider._dispatch_cwd()).is_absolute()


@pytest.mark.parametrize("home,system_drive,expected", [
    (r"D:\Users\cld-review", "C:", r"C:\Users\cld-review"),
    (r"C:\Users\cld-review", "c:", r"C:\Users\cld-review"),
    (r"C:\Users\cld-review", "E:", r"E:\Users\cld-review"),
])
def test_windows_transcript_drive_workaround_is_retained(home, system_drive, expected, monkeypatch):
    class NativePath(PureWindowsPath):
        @classmethod
        def home(cls):
            return cls(home)
    monkeypatch.setattr(provider, "Path", NativePath)
    monkeypatch.setattr(provider, "os", SimpleNamespace(name="nt", environ={"SystemDrive": system_drive}, sep="\\"))
    assert provider._dispatch_cwd() == expected


def local_child(monkeypatch, expected_home, workdir):
    """Exercise the production dispatch helper and real child at its selected cwd."""
    calls = []
    code = ("import json,os,sys;print(json.dumps({'cwd':os.getcwd(),"
            "'depth':os.getenv('CLD_EXECUTOR_DEPTH')}));sys.exit(1)")
    def local(argv, cwd, **options):
        assert argv[argv.index("--add-dir") + 1] == str(workdir)
        assert argv[argv.index("--model") + 1] == "exact-offline-model"
        result = run_process([sys.executable, "-I", "-S", "-c", code], cwd, **options)
        assert result.returncode == 1, result.output
        observed = json.loads(result.stdout)
        assert Path(observed["cwd"]).resolve() == expected_home.resolve()
        assert observed["depth"] == "1"
        calls.append((cwd, options))
        return result
    monkeypatch.setattr(provider, "run_process", local)
    monkeypatch.setattr(provider, "capture_diff", lambda *args: pytest.fail("Failed child must not capture a diff"))
    ex = provider.AntigravityExecutor(model="exact-offline-model", timeout=20,
                                     artifact_dir=workdir / "artifacts")
    assert ex._home == str(expected_home)
    result = ex.run(task(), workdir)
    assert not result.ok and not result.diff and len(calls) == 1
    assert calls[0][1]["timeout"] == 20
    assert calls[0][1]["artifact_dir"] == workdir / "artifacts"
    assert "CLD_EXECUTOR_DEPTH" not in os.environ


def test_posix_branch_default_dispatch_runs_real_local_child(tmp_path, monkeypatch):
    monkeypatch.setattr(provider.Path, "home", classmethod(lambda cls: tmp_path))
    # Replace only the provider's os binding, never global os.name/Path semantics.
    monkeypatch.setattr(provider, "os", SimpleNamespace(name="posix", environ={"SystemDrive": "Z:"},
        sep=os.sep, path=os.path))
    local_child(monkeypatch, tmp_path, tmp_path / "worktree")


@pytest.mark.skipif(os.name == "nt", reason="Real native POSIX default home is verified by Ubuntu CI")
def test_native_posix_default_home_runs_real_local_child(tmp_path, monkeypatch):
    local_child(monkeypatch, Path.home(), tmp_path / "worktree")


def test_explicit_home_preserves_injected_runner_cwd(tmp_path):
    calls = []
    def runner(argv, cwd):
        calls.append(cwd)
        return 1, "synthetic failure"
    result = provider.AntigravityExecutor(runner=runner, home=str(tmp_path)).run(task(), tmp_path)
    assert not result.ok and calls == [str(tmp_path)]


def test_posix_missing_transcript_hint_does_not_require_windows_drive(tmp_path, monkeypatch):
    monkeypatch.setattr(provider, "os", SimpleNamespace(name="posix", environ={}, sep=os.sep, path=os.path))
    result = provider.AntigravityExecutor(runner=lambda argv, cwd: (0, ""),
        home=str(tmp_path)).run(task(), tmp_path)
    assert not result.ok and result.process["error"] == "malformed_output"
    assert "transcript" in result.raw_log.lower()
    assert "C: drive" not in result.raw_log
