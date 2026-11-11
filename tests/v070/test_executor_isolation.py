"""v0.7.0 AGYISOLATE: executor sessions never see the lead's cld MCP tools."""
import json
import subprocess
from pathlib import Path

from cld.executors.base import SliceTask
from cld_providers.antigravity.provider import AntigravityExecutor

DENY = {"permissions": {"deny": ["mcp(cld/*)"]}}


class _Runner:
    def __init__(self, conv_id):
        self.conv_id, self.calls = conv_id, []

    def __call__(self, args, cwd):
        self.calls.append((list(args), cwd))
        if "-p" in args and "--add-dir" in args:
            log = args[args.index("--log-file") + 1]
            Path(log).write_text(f"Stream completed for {self.conv_id}\n", encoding="utf-8")
            return (0, "")
        if "--name-only" in " ".join(args):
            return (0, "src/x.py\0")
        if "diff" in " ".join(args):
            return (0, "--- a\n+++ b\n+x\n")
        return (0, "")


def _dispatch(tmp_path, effort="high"):
    conv = "11111111-1111-1111-1111-111111111111"
    logs = tmp_path / ".gemini" / "antigravity-cli" / "brain" / conv / ".system_generated" / "logs"
    logs.mkdir(parents=True)
    (logs / "transcript.jsonl").write_text(
        '{"source":"MODEL","type":"PLANNER_RESPONSE","content":"READY"}\n', encoding="utf-8")
    runner = _Runner(conv)
    task = SliceTask(id="T", brief="do it", files=["src/x.py"], acceptance_test_path="tests/t.py")
    executor = AntigravityExecutor(runner=runner, model="Gemini 4 Argon (High)", effort=effort,
                                   home=str(tmp_path))
    executor.run(task, str(tmp_path / "wt"))
    return runner.calls[0][0], executor._build_prompt(task)


def test_antigravity_dispatch_denies_cld_tools(tmp_path):
    argv, _ = _dispatch(tmp_path)
    assert argv.count("--settings") == 1, argv
    assert json.loads(argv[argv.index("--settings") + 1]) == DENY


def test_antigravity_dispatch_otherwise_unchanged(tmp_path):
    argv, prompt = _dispatch(tmp_path)
    if "--settings" in argv:
        i = argv.index("--settings")
        argv = argv[:i] + argv[i + 2:]
    log = argv[argv.index("--log-file") + 1]
    assert argv == [argv[0], "-p", prompt, "--model", "Gemini 4 Argon (High)",
                    "--add-dir", str(tmp_path / "wt"), "--dangerously-skip-permissions",
                    "--log-file", log, "--output-format", "json", "--effort", "high"]


def test_antigravity_evidence_stays_unsupported():
    from cld.providers_api import _REGISTRY, get_provider, load_providers
    _REGISTRY.clear()
    load_providers()
    assert get_provider("antigravity").supports_evidence is False


def test_claude_executor_isolates_mcp(tmp_path):
    from cld_providers.claude.contract import build_invocation
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    argv = build_invocation("claude-sonnet-5", str(tmp_path), "do it", effort="high").argv
    assert "--strict-mcp-config" in argv
    assert json.loads(argv[argv.index("--mcp-config") + 1]) == {"mcpServers": {}}


def test_codex_executor_disables_configured_mcp_servers():
    from cld_providers.codex.contract import isolation_args
    args = isolation_args(["cld"])
    assert "mcp_servers.cld.enabled=false" in args
    assert args[args.index("mcp_servers.cld.enabled=false") - 1] == "--config"
