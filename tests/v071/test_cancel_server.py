"""v0.7.1 MCPCANCEL (layer 2): the cld_cancel tool."""
import re

from tests.v070._stubs import by_id, call, init, req, serve, structured, tool
from tests.v071.conftest import ACTIVE, TERMINAL

NINE = {"cld_preview", "cld_status", "cld_list_models", "cld_new_build", "cld_step",
        "cld_integrate", "cld_mark_repaired", "cld_job", "cld_cancel"}


def _is_error(reply):
    assert "result" in reply, reply
    return reply["result"].get("isError") is True


def _step(stub_env, repo):
    path, plan = (str(p) for p in repo)
    data = structured(tool("cld_step", {"plan": plan, "repo": path, "executor": "codex:stub@high",
                                        "validation_policy": "deny", "budget_attempts": 1},
                           stub_env.scripts))
    assert re.fullmatch(r"[0-9a-f]{32}", data.get("job_id", "")), data
    return data["job_id"]


def test_tools_list_has_nine_tools(stub_env):
    reply = by_id(serve(init(), req(1, "tools/list"), scripts_dir=stub_env.scripts), 1)
    assert {t["name"] for t in reply["result"]["tools"]} == NINE


def test_cancel_tool_stops_a_running_step(stub_env, repo, monkeypatch):
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "120")
    job_id = _step(stub_env, repo)
    reply = structured(tool("cld_cancel", {"job_id": job_id}, stub_env.scripts))
    assert reply.get("requested") is True and reply.get("state") in ACTIVE, reply
    for _ in range(30):
        data = structured(tool("cld_job", {"job_id": job_id, "wait_seconds": 5}, stub_env.scripts))
        if data["state"] in TERMINAL:
            break
    assert data["state"] == "cancelled", data


def test_cancel_tool_errors(stub_env):
    assert _is_error(tool("cld_cancel", {"job_id": "0" * 32}, stub_env.scripts))
    reply = tool("cld_cancel", {"job_id": "../x"}, stub_env.scripts)
    assert reply.get("error", {}).get("code") == -32602, reply


def test_executor_guard_refuses_cancel(stub_env, monkeypatch):
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    assert _is_error(tool("cld_cancel", {"job_id": "0" * 32}, stub_env.scripts))
