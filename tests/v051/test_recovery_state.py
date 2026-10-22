"""v0.5.1 OUTCOME: a recovery session always reaches a terminal state, even if evidence capture fails."""
import json
import subprocess

from cld.executors.base import SliceTask
from tests.evidence._lazy import resolve


def _git(argv, cwd):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def _session(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    (repo / "a.py").write_text("x = 0\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    RecoverySession = resolve("cld.recovery", "RecoverySession")
    session = RecoverySession(str(repo), str(repo), SliceTask("A", "b", ["a.py"], "t.py"),
                              str(tmp_path / "ledger.json"), _git, artifact_root=tmp_path / "artifacts")
    session.save(state="running")
    return session


def _state(session):
    return json.loads((session.directory / "outcome.json").read_text(encoding="utf-8"))["state"]


def test_failure_is_terminal_even_when_checkpoint_capture_fails(tmp_path, monkeypatch):
    session = _session(tmp_path)
    CaptureError = resolve("cld.executors._capture", "CaptureError")

    def broken_checkpoint(phase):
        raise CaptureError("Incomplete NUL-delimited Git output")

    monkeypatch.setattr(session, "checkpoint", broken_checkpoint)
    try:
        session.failure(RuntimeError("collection failed"))
    except Exception:
        pass
    assert _state(session) == "failed"


def test_failure_records_the_checkpoint_problem(tmp_path, monkeypatch):
    session = _session(tmp_path)
    CaptureError = resolve("cld.executors._capture", "CaptureError")
    monkeypatch.setattr(session, "checkpoint",
                        lambda phase: (_ for _ in ()).throw(CaptureError("Incomplete NUL-delimited Git output")))
    try:
        session.failure(RuntimeError("collection failed"))
    except Exception:
        pass
    record = json.loads((session.directory / "outcome.json").read_text(encoding="utf-8"))
    assert "collection failed" in record.get("error", "") and "NUL" in json.dumps(record)
