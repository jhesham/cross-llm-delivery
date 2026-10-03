"""v0.4.1 N01: the selected effort is authoritative over an inherited CLAUDE_CODE_EFFORT_LEVEL.

Claude Code gives CLAUDE_CODE_EFFORT_LEVEL precedence over --effort, so a lead
session's ambient value must never reach the executor child.
"""
import sys

import pytest

from cld.admission import validation_context
from cld.process import run_process
from cld_providers.claude.contract import EFFORTS, build_invocation

READ = "import os; print(os.environ.get('CLAUDE_CODE_EFFORT_LEVEL', '<unset>'))"


def _invocation(tmp_path, effort):
    (tmp_path / ".git").mkdir(exist_ok=True)
    return build_invocation("claude-sonnet-5", str(tmp_path), "do the slice", effort=effort)


@pytest.mark.parametrize("effort", EFFORTS)
def test_invocation_pins_selected_effort(tmp_path, effort):
    inv = _invocation(tmp_path, effort)
    assert inv.env.get("CLAUDE_CODE_EFFORT_LEVEL") == effort
    assert inv.argv[inv.argv.index("--effort") + 1] == effort


@pytest.mark.parametrize("ambient,selected", [("max", "low"), ("low", "max"), ("high", "high")])
def test_child_sees_selected_not_inherited_effort(tmp_path, monkeypatch, ambient, selected):
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", ambient)
    inv = _invocation(tmp_path, selected)
    result = run_process([sys.executable, "-c", READ], inv.cwd, env=inv.env,
                         unset_env=inv.unset_env, timeout=60)
    assert result.returncode == 0
    assert result.stdout.strip() == selected


def test_evidence_follows_selected_effort_not_ambient(monkeypatch):
    """Ambient effort cannot change the child, so it must not key evidence; the spec's effort does."""
    def fingerprint(spec):
        return validation_context(spec, cli_paths=[], repo=".",
                                  env_patterns=("CLAUDE_CLI_CMD", "CLAUDE_CONFIG_DIR", "ANTHROPIC_*"))["fingerprint"]
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", "low")
    low_ambient = fingerprint("claude:claude-sonnet-5@low")
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", "max")
    assert fingerprint("claude:claude-sonnet-5@low") == low_ambient
    assert fingerprint("claude:claude-sonnet-5@max") != low_ambient
