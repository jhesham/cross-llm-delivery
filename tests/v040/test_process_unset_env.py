"""v0.4.0: executor children can have credentials removed from their environment."""
import sys

from cld.process import run_process

PRINT = "import os; print(os.environ.get('ANTHROPIC_API_KEY', '<unset>'), os.environ.get('KEEP_ME', '<unset>'))"


def test_run_process_unsets_env_case_insensitively(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("KEEP_ME", "kept")
    result = run_process([sys.executable, "-c", PRINT], str(tmp_path), timeout=60,
                         unset_env=("anthropic_api_key",))
    assert result.returncode == 0
    assert result.stdout.split() == ["<unset>", "kept"]


def test_unset_env_applies_after_explicit_env(tmp_path):
    result = run_process([sys.executable, "-c", PRINT], str(tmp_path), timeout=60,
                         env={"ANTHROPIC_API_KEY": "explicit", "KEEP_ME": "x"},
                         unset_env=("ANTHROPIC_API_KEY",))
    assert result.stdout.split() == ["<unset>", "x"]
