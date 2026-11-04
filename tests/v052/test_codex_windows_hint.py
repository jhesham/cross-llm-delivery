"""v0.5.2 CODEXHINT: drop the cmd /c advice (Codex wraps commands in PowerShell anyway); advise
redirecting output to a file when a command's output cannot be read."""
from tests.evidence._lazy import resolve

C = "cld_providers.codex.contract"


def _stdin(tmp_path, **kw):
    (tmp_path / ".git").mkdir(exist_ok=True)
    return resolve(C, "build_invocation")("gpt-example", tmp_path, "p", **kw).stdin


def test_role_no_longer_recommends_cmd(tmp_path):
    assert "cmd /c" not in _stdin(tmp_path)


def test_role_advises_redirecting_output_to_a_file(tmp_path):
    text = _stdin(tmp_path).lower()
    assert "redirect" in text and "file" in text


def test_evidence_role_matches(tmp_path):
    text = _stdin(tmp_path, evidence=True)
    assert "cmd /c" not in text and "redirect" in text.lower()
