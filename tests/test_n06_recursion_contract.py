"""Five-provider recursion acceptance: synthetic/local children only, no inference."""
from dataclasses import dataclass
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from cld.admission import AdmissionBlocked
from cld.executors.base import SliceTask
from cld.process import run_process


PROVIDERS = ("opencode", "cursor", "antigravity", "codex", "claude")
LEGACY = PROVIDERS[:3]
CLASSES = dict(zip(PROVIDERS, ("OpenCodeExecutor", "CursorExecutor",
                             "AntigravityExecutor", "CodexExecutor", "ClaudeExecutor")))
CODEX_HELP = ("Usage: codex exec [PROMPT] --json --ephemeral --sandbox --cd --model --config\n"
              "Initial instructions are read from stdin if '-' is used.")
CLAUDE_HELP = "Usage: claude\n" + "\n".join(f"  {flag} <x>" for flag in (
    "-p", "--output-format", "--model", "--effort", "--safe-mode", "--restricted",
    "--strict-mcp-config", "--mcp-config", "--tools", "--permission-mode",
    "--allowed-tools", "--settings", "--no-session-persistence"))


@dataclass
class Probe:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    error: str | None = None

    def metadata(self):
        return {"returncode": self.returncode, "error": self.error}


@pytest.fixture(autouse=True)
def lead_environment(monkeypatch):
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)


def task():
    return SliceTask("N06", "Implement only this slice", ["target.py"], "test_target.py")


def executor(name, root, **kwargs):
    module = importlib.import_module(f"cld_providers.{name}.provider")
    if name == "antigravity":
        kwargs["home"] = str(root)
    if name in ("codex", "claude"):
        kwargs["model"] = "claude-offline-1" if name == "claude" else "exact-offline-model"
        kwargs["effort"] = "low"
    return module, getattr(module, CLASSES[name])(**kwargs)


@pytest.mark.parametrize("name", PROVIDERS)
@pytest.mark.parametrize("depth", ["1", "-1", "invalid", "", "00"])
def test_direct_entrypoint_blocks_before_runner_or_diff(tmp_path, monkeypatch, name, depth):
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", depth)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("A recursive provider reached a process or diff capture")

    module, instance = executor(name, tmp_path, runner=forbidden)
    monkeypatch.setattr(module, "capture_diff", forbidden)
    if name == "antigravity":
        monkeypatch.setattr(module, "artifact_file", forbidden)
    result = instance.run(task(), tmp_path)
    assert not result.ok and result.process["error"] == "recursive_dispatch"
    assert result.diff == "" and result.files_changed == [] and calls == []


@pytest.mark.parametrize("name", PROVIDERS)
@pytest.mark.parametrize("depth", [None, "0"], ids=["unset", "lead-zero"])
def test_production_child_marks_depth_and_blocks_nested_cli(tmp_path, monkeypatch, name, depth):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if name == "opencode":
        # A local child stands in for the CLI; no installed provider is required.
        monkeypatch.setenv("OPENCODE_CLI_CMD", str(Path(sys.executable).resolve()))
    if depth is not None:
        monkeypatch.setenv("CLD_EXECUTOR_DEPTH", depth)
    monkeypatch.setenv("N06_PRESERVED_ENV", "sentinel")
    monkeypatch.setenv("NODE_OPTIONS", "--existing-option")
    engine = Path(__file__).resolve().parents[1] / "engine"
    code = (
        "import json,os,sys; sys.path.insert(0," + repr(str(engine)) + "); "
        "from cld import cli; from cld.admission import AdmissionBlocked; "
        "blocked=False\n"
        "try: cli.prepare_dispatch(None,None,None)\n"
        "except AdmissionBlocked: blocked=True\n"
        "except Exception: pass\n"
        "print(json.dumps({'depth':os.getenv('CLD_EXECUTOR_DEPTH'),"
        "'preserved':os.getenv('N06_PRESERVED_ENV'),'blocked':blocked,"
        "'cursor':os.getenv('CURSOR_INVOKED_AS'),'node':os.getenv('NODE_OPTIONS')}))"
    )
    observed = []

    def local(argv, cwd, **kwargs):
        if argv[1:] == ["--version"]:
            return Probe(stdout="codex-cli 0.159.3" if name == "codex" else "2.1.286 (Claude Code)")
        if "--help" in argv:
            return Probe(stdout=CODEX_HELP if name == "codex" else CLAUDE_HELP)
        result = run_process([sys.executable, "-I", "-S", "-c", code], cwd, **kwargs)
        assert result.returncode == 0, result.output
        observed.append(json.loads(result.stdout))
        return result

    if name in LEGACY:
        module, instance = executor(name, tmp_path, timeout=20, artifact_dir=tmp_path / "artifacts")
        monkeypatch.setattr(module, "run_process", local)
        if name == "cursor":
            # Exercise its bundled-Node environment adjustments without launching Node.
            monkeypatch.setattr(module, "_cursor_invocation", lambda: [str(tmp_path / "node.exe")])
    else:
        module, instance = executor(name, tmp_path, runner=local, timeout=20,
                                   artifact_dir=tmp_path / "artifacts")

    def no_capture(*args, **kwargs):
        raise AssertionError("Synthetic child completion must never capture a diff")

    monkeypatch.setattr(module, "capture_diff", no_capture)
    result = instance.run(task(), tmp_path)
    assert len(observed) == 1
    child = observed[0]
    assert child["depth"] == "1" and child["blocked"] is True
    assert child["preserved"] == "sentinel"
    if name == "cursor":
        assert child["cursor"] == "cursor-agent"
        assert "--existing-option" in child["node"] and "--use-system-ca" in child["node"]
    assert not result.ok and result.diff == ""
    assert os.environ.get("CLD_EXECUTOR_DEPTH") == depth
    assert os.environ["NODE_OPTIONS"] == "--existing-option"


@pytest.mark.parametrize("name", LEGACY)
def test_legacy_injected_runner_still_receives_exactly_two_arguments(tmp_path, name):
    calls = []

    def runner(argv, cwd):
        calls.append((argv, cwd))
        return 1, "synthetic provider failure"

    _, instance = executor(name, tmp_path, runner=runner)
    result = instance.run(task(), tmp_path, feedback="Address only this feedback")
    assert not result.ok and len(calls) == 1
    assert calls[0][1] == str(tmp_path)
    assert result.process["error"] == "nonzero_exit"


@pytest.mark.parametrize("name", PROVIDERS)
@pytest.mark.parametrize("feedback", [None, "Fix the previous attempt"])
def test_every_executor_prompt_prohibits_recursive_delegation(tmp_path, name, feedback):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    module, instance = executor(name, tmp_path)
    if name == "claude":
        from cld_providers.claude.contract import build_invocation
        prompt = build_invocation("claude-offline-1", str(tmp_path.resolve()),
                                  instance._prompt(task(), feedback), effort="low").stdin
    elif name == "codex":
        from cld_providers.codex.contract import build_invocation
        prompt = build_invocation("exact-offline-model", str(tmp_path.resolve()),
                                  instance._build_prompt(task(), feedback)).stdin
    else:
        prompt = instance._build_prompt(task(), feedback)
    normalized = " ".join(prompt.lower().split())
    assert "executor for exactly one cld delivery slice" in normalized
    assert "do not invoke cld" in normalized
    assert "any other llm provider" in normalized
    assert "recursive delegation is prohibited" in normalized
    assert task().brief in prompt and task().acceptance_test_path in prompt
    if feedback:
        assert feedback in prompt


@pytest.mark.parametrize("depth", ["1", "-1", "invalid", "", "00"])
def test_nested_cli_blocks_before_discovery_for_every_nonlead_marker(monkeypatch, depth):
    from cld import cli
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", depth)
    blocked = False
    try:
        cli.prepare_dispatch(None, None, None)
    except AdmissionBlocked as exc:
        blocked = "Recursive CLD dispatch blocked" in str(exc)
    assert blocked, "Nested dispatch must fail closed before discovery or inference"
