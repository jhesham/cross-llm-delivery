"""v0.7.0 MCPPROTO: JSON-RPC server, negotiation, errors, sync tools, executor guard.

``cld.mcp_server.main(stdin=None, stdout=None, scripts_dir=None)`` reads
newline-delimited JSON-RPC from a text stream until EOF. These tests must keep
passing after MCPTOOLS moves ``cld_new_build`` onto the job runner.
"""
import ast
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.v070 import _stubs
from tests.v070._stubs import by_id, call, driver_json, init, read_json, req, serve, structured, tool

ROOT = Path(__file__).resolve().parents[2]
SYNC_TOOLS = {"cld_preview": {"plan", "repo"}, "cld_status": {"repo"},
              "cld_list_models": set(), "cld_new_build": {"plan", "repo"}}


def _error(reply, code):
    assert "error" in reply, reply
    assert reply["error"].get("code") == code, reply


def _is_error(reply):
    assert "result" in reply, reply
    return reply["result"].get("isError") is True


@pytest.mark.parametrize("asked,expected", [("2025-03-26", "2025-03-26"),
                                            ("2024-11-05", "2024-11-05"),
                                            ("2025-06-18", "2025-06-18"),
                                            ("9999-01-01", "2025-06-18")])
def test_initialize_negotiates_version(stub_env, asked, expected):
    result = by_id(serve(init(7, asked), scripts_dir=stub_env.scripts), 7)["result"]
    assert result["protocolVersion"] == expected
    assert result["serverInfo"]["name"] == "cld"
    assert isinstance(result["serverInfo"].get("version"), str)
    assert "tools" in result["capabilities"]


def test_notifications_get_no_reply_and_ping_is_empty(stub_env):
    replies = serve(init(), {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    req(2, "ping"), scripts_dir=stub_env.scripts)
    assert [r["id"] for r in replies] == [0, 2]
    assert by_id(replies, 2)["result"] == {}


def test_protocol_errors_do_not_stop_the_server(stub_env):
    replies = serve(init(), "{not json", req(3, "ping"), "[1, 2]", req(4, "no/such/method"),
                    call(5, "cld_nope"), call(6, "cld_status", {"repo": 42}),
                    call(7, "cld_preview", {"repo": str(stub_env.scripts)}), req(8, "ping"),
                    scripts_dir=stub_env.scripts)
    parse = [r for r in replies if r.get("id") is None]
    assert any(r.get("error", {}).get("code") == -32700 for r in parse), replies
    assert any(r.get("error", {}).get("code") == -32600 for r in parse), replies
    assert by_id(replies, 3)["result"] == {}
    _error(by_id(replies, 4), -32601)
    for id_ in (5, 6, 7):
        _error(by_id(replies, id_), -32602)
    assert by_id(replies, 8)["result"] == {}


def test_tools_list_has_sync_tools_with_schemas(stub_env):
    tools = by_id(serve(init(), req(1, "tools/list"), scripts_dir=stub_env.scripts), 1)
    listed = {t["name"]: t for t in tools["result"]["tools"]}
    for name, required in SYNC_TOOLS.items():
        assert name in listed, sorted(listed)
        schema = listed[name].get("inputSchema", {})
        assert schema.get("type") == "object", (name, schema)
        assert set(schema.get("required", [])) == required, (name, schema)


def test_server_version_comes_from_bundle_banner(tmp_path, stub_env):
    bundle = tmp_path / "bundle"
    (bundle / "scripts").mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        "---\nname: cross-llm-delivery\ndescription: t\n---\n"
        "<!-- GENERATED from cross-llm-delivery@abc1234 (provider: unified, v9.8.7) - do not edit "
        "here; edit the monorepo source. -->\n# t\n", encoding="utf-8")
    result = by_id(serve(init(), scripts_dir=bundle / "scripts"), 0)["result"]
    assert result["serverInfo"]["version"] == "9.8.7"


def test_sync_tool_argv(stub_env, repo):
    path, plan = (str(p) for p in repo)
    host = stub_env.host
    preview = driver_json(structured(tool("cld_preview", {"plan": plan, "repo": path},
                                          stub_env.scripts)))
    assert preview["argv"] == [plan, "--repo", path, "--dry-run", "--json", "--host", host]
    status = driver_json(structured(tool("cld_status", {"repo": path}, stub_env.scripts)))
    assert status["argv"] == ["--status", "--repo", path, "--json", "--host", host]
    reply = tool("cld_new_build", {"plan": plan, "repo": path}, stub_env.scripts)
    assert not _is_error(reply), reply
    built = driver_json(structured(reply))
    assert built["argv"] == [plan, "--repo", path, "--new-build", "--json", "--host", host]


def test_list_models_returns_picker_json_unchanged(stub_env):
    data = structured(tool("cld_list_models", {}, stub_env.scripts))
    assert data == {"models": [{"spec": "stub:model-a"}], "advisory": "stub picker",
                    "argv": ["--json"]}


@pytest.mark.parametrize("arguments,named", [({"plan": "plan.md", "repo": "ABS"}, "plan"),
                                             ({"plan": "ABS", "repo": "repo"}, "repo")])
def test_relative_paths_are_refused_before_running(stub_env, repo, monkeypatch, arguments, named):
    monkeypatch.setenv("CLD_STUB_MARKER", str(stub_env.marker))
    arguments = {k: (str(repo[1]) if v == "ABS" else v) for k, v in arguments.items()}
    reply = tool("cld_preview", arguments, stub_env.scripts)
    assert _is_error(reply), reply
    assert named in reply["result"]["content"][0]["text"]
    assert not stub_env.marker.exists(), "the driver ran for a relative path"


def test_sync_timeout_kills_driver_and_keeps_serving(stub_env, repo, monkeypatch):
    monkeypatch.setenv("CLD_STUB_MARKER", str(stub_env.marker))
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "60")
    monkeypatch.setenv("CLD_MCP_SYNC_TIMEOUT", "2")
    t0 = time.monotonic()
    replies = serve(init(), call(1, "cld_status", {"repo": str(repo[0])}), req(2, "ping"),
                    scripts_dir=stub_env.scripts)
    assert time.monotonic() - t0 < 20
    assert _is_error(by_id(replies, 1))
    assert by_id(replies, 2)["result"] == {}
    seen = read_json(stub_env.marker)
    assert seen, "stub never started"
    assert _stubs.wait_for(lambda: not _stubs.pid_alive(seen["pid"]), 5), "driver survived timeout"


def test_executor_guard_refuses_mutating_tools(stub_env, repo, monkeypatch):
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    monkeypatch.setenv("CLD_STUB_MARKER", str(stub_env.marker))
    path, plan = (str(p) for p in repo)
    assert _is_error(tool("cld_new_build", {"plan": plan, "repo": path}, stub_env.scripts))
    assert not stub_env.marker.exists()
    status = tool("cld_status", {"repo": path}, stub_env.scripts)
    assert not _is_error(status), status


def test_stdout_carries_only_jsonrpc(tmp_path, stub_env, repo):
    shim = tmp_path / "server_shim.py"
    shim.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'engine')!r})\n"
        "from cld.mcp_server import main\n"
        f"main(scripts_dir={str(stub_env.scripts)!r})\n", encoding="utf-8")
    lines = [init(), {"jsonrpc": "2.0", "method": "notifications/initialized"},
             req(1, "tools/list"), call(2, "cld_status", {"repo": str(repo[0])}), "{bad",
             req(3, "ping")]
    proc = subprocess.run([sys.executable, str(shim)], capture_output=True, text=True,
                          input="\n".join(l if isinstance(l, str) else json.dumps(l)
                                          for l in lines) + "\n", timeout=60)
    out = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(out) == 5, (proc.stdout, proc.stderr)
    for line in out:
        assert json.loads(line).get("jsonrpc") == "2.0", line


def test_server_imports_only_stdlib_and_cld():
    path = ROOT / "engine" / "cld" / "mcp_server.py"
    assert path.is_file(), "engine/cld/mcp_server.py not implemented"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level
                 else [])
        for name in names:
            top = name.split(".")[0]
            assert top == "cld" or top in sys.stdlib_module_names, f"third-party import: {name}"
