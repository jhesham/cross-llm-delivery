"""v0.5 second review (REDACT): more credential forms, failed stdout, and cleanup failure."""
import sys

from tests.evidence._fixtures import FakeResult, FakeRunner, environment
from tests.evidence._lazy import resolve

M = "cld.evidence_mode.sqlrun"


def _stored(tmp_path):
    return "".join(p.read_text(encoding="utf-8", errors="replace")
                   for p in tmp_path.rglob("*") if p.is_file())


def _run(tmp_path, runner, env=None):
    return resolve(M, "run_sql")(tmp_path, env or environment(), "SELECT 1",
                                 out_dir=tmp_path / "out", runner=runner)


def test_basic_auth_and_quoted_passwords_redacted(tmp_path):
    stderr = ('Authorization: Basic dXNlcjpwYXNzd29yZA==\n'
              'password="correct horse battery"\npwd=\'two words\'')
    rec = _run(tmp_path, FakeRunner(FakeResult(returncode=1, stderr=stderr, error="nonzero_exit")))
    stored = _stored(tmp_path)
    for secret in ("dXNlcjpwYXNzd29yZA==", "horse battery", "two words"):
        assert secret not in rec["stderr_tail"] and secret not in stored, secret


def test_failed_command_stdout_is_redacted(tmp_path):
    rec = _run(tmp_path, FakeRunner(FakeResult(returncode=1, stdout="error: password=s3cr3t-out",
                                               error="nonzero_exit")))
    assert rec["status"] == "failed"
    assert "s3cr3t-out" not in _stored(tmp_path)


def test_raw_output_cleanup_failure_fails_the_run_and_scrubs(tmp_path, monkeypatch):
    module = __import__(M, fromlist=["_remove_raw_output"])
    assert hasattr(module, "_remove_raw_output"), "sqlrun._remove_raw_output(path) is missing"
    monkeypatch.setattr(module, "_remove_raw_output", lambda path: None)  # deletion silently fails
    env = environment(command=(sys.executable, "-c",
                               "import sys; sys.stdin.read(); sys.stderr.write('password=hunter2-secret'); "
                               "print('[]')"))
    rec = _run(tmp_path, resolve("cld.process", "run_process"), env=env)
    assert rec["status"] == "failed" and "raw output" in (rec["error"] or "").lower(), rec
    assert "hunter2-secret" not in _stored(tmp_path)
