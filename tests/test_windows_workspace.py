"""Owned Windows workspace permissions: exact account, bounded, fail closed."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from cld import _windows_workspace as permissions
from cld.executors._capture import CaptureError
from cld.validate import validate_model
from cld.worktree import worktree
from tests.integration.harness import init_repo, real_git_runner


SID = "S-1-5-21-123-456-789-1001"


@pytest.fixture
def owned_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(permissions, "_ON_WINDOWS", True)
    monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))
    monkeypatch.delenv("CLD_PROBE_TIMEOUT", raising=False)
    root = tmp_path.resolve()
    workspace = root / "workspace"
    workspace.mkdir()
    return workspace, root


def output(stdout="", *, error=None, returncode=0):
    return SimpleNamespace(stdout=stdout, error=error, returncode=returncode)


def test_grants_only_current_account_modify_on_owned_child(owned_workspace, monkeypatch):
    workspace, root = owned_workspace
    calls = []
    def run(args, cwd, **kwargs):
        calls.append((args, cwd, kwargs))
        return output(f'"server\\account","{SID}"\r\n') if len(calls) == 1 else output()
    monkeypatch.setattr(permissions, "run_process", run)
    permissions.prepare_windows_workspace(workspace, parent=root)
    grant, cwd, limits = calls[1]
    assert Path(grant[0]).name == "icacls.exe"
    assert grant[1:] == [str(workspace), "/grant", f"*{SID}:(OI)(CI)(M)", "/L", "/Q"]
    assert cwd == str(root) and limits["timeout"] == 30


@pytest.mark.parametrize("identity", ["", '"user","Everyone"',
                                      f'"user","{SID}"\n"second","{SID}"',
                                      f'"user","{SID} /T"'])
def test_invalid_account_output_never_runs_acl_command(owned_workspace, monkeypatch, identity):
    workspace, root = owned_workspace
    calls = []
    def run(args, cwd, **kwargs):
        calls.append(args)
        return output(identity)
    monkeypatch.setattr(permissions, "run_process", run)
    with pytest.raises(CaptureError, match="account SID"):
        permissions.prepare_windows_workspace(workspace, parent=root)
    assert len(calls) == 1


@pytest.mark.parametrize("failure_at", [1, 2])
@pytest.mark.parametrize("failure", [output(error="timeout"), output(returncode=1)])
def test_process_failure_is_not_silently_ignored(owned_workspace, monkeypatch, failure_at, failure):
    workspace, root = owned_workspace
    calls = []
    def run(args, cwd, **kwargs):
        calls.append(args)
        return failure if len(calls) == failure_at else output(f'"user","{SID}"')
    monkeypatch.setattr(permissions, "run_process", run)
    with pytest.raises(CaptureError, match="no dispatch"):
        permissions.prepare_windows_workspace(workspace, parent=root)
    assert len(calls) == failure_at


def test_rejects_parent_or_other_location_before_running_commands(owned_workspace, monkeypatch):
    workspace, root = owned_workspace
    monkeypatch.setattr(permissions, "run_process", lambda *a, **k: pytest.fail("unexpected command"))
    for path in [root, root / "missing", Path("relative")]:
        with pytest.raises(CaptureError, match="owned child"):
            permissions.prepare_windows_workspace(path, parent=root)
    with pytest.raises(CaptureError, match="owned child"):
        permissions.prepare_windows_workspace(workspace, parent=root / "wrong")


def test_non_windows_does_not_touch_permissions(monkeypatch):
    monkeypatch.setattr(permissions, "_ON_WINDOWS", False)
    monkeypatch.setattr(permissions, "run_process", lambda *a, **k: pytest.fail("unexpected command"))
    permissions.prepare_windows_workspace("not-a-path", parent="not-a-path")


def test_linked_workspace_is_rejected_before_acl_changes(owned_workspace, monkeypatch):
    workspace, root = owned_workspace
    link = root / "linked-workspace"
    try:
        link.symlink_to(workspace, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks unavailable")
    monkeypatch.setattr(permissions, "run_process", lambda *a, **k: pytest.fail("unexpected command"))
    with pytest.raises(CaptureError, match="owned child"):
        permissions.prepare_windows_workspace(link, parent=root)


def test_workspace_commands_respect_configured_probe_timeout(owned_workspace, monkeypatch):
    workspace, root = owned_workspace
    monkeypatch.setenv("CLD_PROBE_TIMEOUT", "7")
    limits = []
    def run(args, cwd, **kwargs):
        limits.append(kwargs["timeout"])
        return output(f'"user","{SID}"')
    monkeypatch.setattr(permissions, "run_process", run)
    permissions.prepare_windows_workspace(workspace, parent=root)
    assert limits == [7, 7]


def test_validation_permission_failure_preserves_evidence_without_dispatch(tmp_path, monkeypatch):
    def fail(*a, **k):
        raise CaptureError("workspace permissions failed")
    monkeypatch.setattr("cld.validate.prepare_windows_workspace", fail)
    executor = SimpleNamespace(run=lambda *a, **k: pytest.fail("must not dispatch"))
    result = validate_model("fixture", executor=executor, git_runner=real_git_runner,
                            base_dir=str(tmp_path))
    assert result.status == "untested" and not result.passed
    assert result.attempts == 0 and result.usage == {}
    assert result.error == "infrastructure_error"
    assert Path(result.artifact_path, "validation.json").is_file()


def test_worktree_permission_failure_retains_owned_candidate(tmp_path, monkeypatch):
    repo = init_repo(tmp_path / "source")
    root = (tmp_path / "worktrees").resolve()
    root.mkdir()
    path = root / "candidate"
    def fail(*a, **k):
        raise CaptureError("workspace permissions failed")
    monkeypatch.setattr("cld.worktree.prepare_windows_workspace", fail)
    with pytest.raises(CaptureError, match="permissions failed") as error:
        with worktree(repo, "permission-failure", runner=real_git_runner,
                      path=str(path), root=str(root)):
            pytest.fail("must not enter dispatch body")
    assert path.is_dir() and (path / ".git").is_file()
    assert any(str(path) in note for note in error.value.__notes__)
