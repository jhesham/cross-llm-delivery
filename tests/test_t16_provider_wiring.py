"""T16 provider selection, recursion, and isolated bundle contracts (offline)."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from cld import cli
from cld.models import model_policy, resolve_spec
from cld.providers_api import all_providers, load_providers
from generator.build_skill import build_one


def test_codex_registration_requires_exact_model_without_substitution():
    load_providers()
    assert {p.name for p in all_providers()} >= {"antigravity", "cursor", "opencode", "codex"}
    assert resolve_spec("codex:gpt-6-luna@max") == (
        "codex:gpt-6-luna@max", "codex", {"model": "gpt-6-luna", "effort": "max"})
    with pytest.raises(ValueError, match="explicit model ID"):
        resolve_spec("codex")
    policy = model_policy("codex:gpt-6-luna@max")
    assert policy == ("untested", "metered-unknown")


def test_ambient_executor_cannot_recursively_dispatch_any_provider(monkeypatch):
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    with pytest.raises(Exception, match="Recursive CLD dispatch blocked"):
        cli.prepare_dispatch(None, None, None)


@pytest.mark.parametrize("host", ["claude-code", "codex"])
def test_isolated_codex_bundle_has_no_guessed_default(tmp_path, host):
    bundle = build_one("codex", out_root=tmp_path / "output with spaces", host=host)
    skill = (bundle / "SKILL.md").read_text(encoding="utf-8")
    assert "codex:<model-id>@<effort>" in skill
    assert "no default" in skill.lower()
    script = (
        "from cld.providers_api import load_providers,all_providers; "
        "from cld.models import resolve_spec,build_model_index; "
        "load_providers(); assert [p.name for p in all_providers()]==['codex']; "
        "assert build_model_index(opencode_ids=[],cursor_models=[],evidence={})==[]; "
        "\ntry: resolve_spec('')\nexcept ValueError as exc: "
        "assert 'explicit' in str(exc) or 'No executor model default' in str(exc)\n"
        "else: raise AssertionError('unexpected default')"
    )
    env = {**os.environ, "PYTHONPATH": str(bundle / "scripts")}
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path,
                            env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
