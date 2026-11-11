"""v0.7.0 MCPTOOLS (layer 2): job tools over the cld.mcp_jobs runner.

Job-starting tools return structuredContent with ``job_id``; ``cld_job`` returns
``job_status`` (DESIGN.md "Pinned return and record keys").
"""
import os
import re
import shutil
import sys
import time
from pathlib import Path

import pytest

from tests.v070 import _stubs
from tests.v070._stubs import TERMINAL, McpProcess, by_id, call, driver_json, init, req, serve, \
    structured, tool

ROOT = Path(__file__).resolve().parents[2]
EIGHT = {"cld_preview", "cld_status", "cld_list_models", "cld_new_build", "cld_step",
         "cld_integrate", "cld_mark_repaired", "cld_job"}
OVERRIDES = ("AGY_CMD", "OPENCODE_CLI_CMD", "CURSOR_AGENT_CMD", "CODEX_CLI_CMD", "CLAUDE_CLI_CMD")


def _is_error(reply):
    assert "result" in reply, reply
    return reply["result"].get("isError") is True


def _text(reply):
    return reply["result"]["content"][0]["text"]


def _job_dirs(root):
    root = Path(root)
    return [p for p in root.iterdir() if re.fullmatch(r"[0-9a-f]{32}", p.name)] if root.is_dir() else []


def _start(stub_env, name, arguments):
    reply = tool(name, arguments, stub_env.scripts)
    assert not _is_error(reply), reply
    data = structured(reply)
    assert re.fullmatch(r"[0-9a-f]{32}", data.get("job_id", "")), data
    return data["job_id"]


def _poll(stub_env, job_id, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = structured(tool("cld_job", {"job_id": job_id, "wait_seconds": 5}, stub_env.scripts))
        if data.get("state") in TERMINAL:
            return data
    raise AssertionError(f"job {job_id} did not finish")


def _step_args(repo, **over):
    path, plan = (str(p) for p in repo)
    args = {"plan": plan, "repo": path, "executor": "codex:stub-model@high",
            "validation_policy": "deny", "budget_attempts": 3}
    args.update(over)
    return {k: v for k, v in args.items() if v is not None}


def test_tools_list_has_the_v070_tools(stub_env):
    # v0.7.1 adds cld_cancel; its exact nine-tool list is tests/v071/test_cancel_server.py.
    reply = by_id(serve(init(), req(1, "tools/list"), scripts_dir=stub_env.scripts), 1)
    names = {t["name"] for t in reply["result"]["tools"]}
    assert EIGHT <= names <= EIGHT | {"cld_cancel"}, sorted(names)


@pytest.mark.parametrize("workers", [None, 3])
def test_step_runs_as_a_job_with_exact_argv(stub_env, repo, workers):
    path, plan = (str(p) for p in repo)
    job_id = _start(stub_env, "cld_step", _step_args(repo, workers=workers))
    data = _poll(stub_env, job_id)
    assert data["state"] == "finished", data
    assert driver_json(data)["argv"] == [
        plan, "--repo", path, "--step", "--workers", str(workers or 1),
        "--executor", "codex:stub-model@high", "--validation-policy", "deny",
        "--budget-attempts", "3", "--json", "--host", stub_env.host]


@pytest.mark.parametrize("over", [{"executor": None}, {"validation_policy": None},
                                  {"budget_attempts": None}, {"validation_policy": "maybe"},
                                  {"workers": 0}, {"workers": 5}, {"budget_attempts": 0}])
def test_step_argument_errors_start_no_job(stub_env, repo, over):
    reply = tool("cld_step", _step_args(repo, **over), stub_env.scripts)
    assert reply.get("error", {}).get("code") == -32602, reply
    assert _job_dirs(stub_env.jobs) == []


def test_integrate_and_mark_repaired_argv(stub_env, repo):
    path, plan = (str(p) for p in repo)
    selector = 'tests/v070 -k "not slow"'
    job_id = _start(stub_env, "cld_integrate", {"plan": plan, "repo": path,
                                                "integration_tests": selector})
    assert driver_json(_poll(stub_env, job_id))["argv"] == [
        plan, "--repo", path, "--integrate", "--integration-tests", selector, "--json",
        "--host", stub_env.host]
    job_id = _start(stub_env, "cld_mark_repaired", {"plan": plan, "repo": path, "slice_id": "A"})
    assert driver_json(_poll(stub_env, job_id))["argv"] == [
        plan, "--repo", path, "--mark-repaired", "A", "--json", "--host", stub_env.host]
    reply = tool("cld_integrate", {"plan": plan, "repo": path}, stub_env.scripts)
    assert reply.get("error", {}).get("code") == -32602, reply


def test_job_poll_errors(stub_env):
    assert _is_error(tool("cld_job", {"job_id": "0" * 32}, stub_env.scripts))
    for bad in ({"job_id": "../etc"}, {"job_id": "A" * 32}, {"job_id": "0" * 32, "wait_seconds": 46}):
        reply = tool("cld_job", bad, stub_env.scripts)
        assert reply.get("error", {}).get("code") == -32602, (bad, reply)


def test_second_step_on_same_repo_names_running_job(stub_env, repo, monkeypatch):
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "60")
    first = _start(stub_env, "cld_step", _step_args(repo))
    reply = tool("cld_step", _step_args(repo), stub_env.scripts)
    assert _is_error(reply) and first in _text(reply), reply


def test_executor_guard_covers_every_mutating_tool(stub_env, repo, monkeypatch):
    monkeypatch.setenv("CLD_EXECUTOR_DEPTH", "1")
    path, plan = (str(p) for p in repo)
    for name, arguments in (("cld_step", _step_args(repo)),
                            ("cld_integrate", {"plan": plan, "repo": path, "integration_tests": "t"}),
                            ("cld_mark_repaired", {"plan": plan, "repo": path, "slice_id": "A"}),
                            ("cld_new_build", {"plan": plan, "repo": path})):
        assert _is_error(tool(name, arguments, stub_env.scripts)), name
    assert _job_dirs(stub_env.jobs) == []


@pytest.fixture(scope="module")
def unified_bundle(tmp_path_factory):
    from generator.build_skill import build_unified
    return Path(build_unified(out_root=tmp_path_factory.mktemp("bundle"), smoke=False))


def _bundle_env(jobs_root, **extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLD_DRIVER", "CLD_MODELS", "PYTHONPATH", "CLD_EXECUTOR_DEPTH", "CLD_HOST")}
    env["CLD_MCP_JOBS"] = str(jobs_root)
    env.update(extra)
    return env


def test_generated_bundle_runs_real_paths_and_detached_jobs(tmp_path, jobs_root, unified_bundle):
    bundle = tmp_path / "cross-llm-delivery"
    shutil.copytree(unified_bundle, bundle)
    entry = bundle / "scripts" / "cld_mcp.py"
    assert entry.is_file(), "bundle has no scripts/cld_mcp.py"
    path, plan = (str(p) for p in _stubs.git_repo(tmp_path / "repo"))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    server = McpProcess([sys.executable, str(entry)], env=_bundle_env(jobs_root), cwd=elsewhere)
    try:
        assert server.initialize()["result"]["serverInfo"]["name"] == "cld"
        preview = structured(server.call("cld_preview", {"plan": plan, "repo": path}))
        assert preview.get("schema_version") == 1 and preview.get("gate_code") == 0, preview
    finally:
        server.close()
    _stubs.write_wrapper(bundle / "scripts" / "run_delivery.py", "driver_main")
    server = McpProcess([sys.executable, str(entry)], env=_bundle_env(jobs_root), cwd=elsewhere)
    try:
        server.initialize()
        started = structured(server.call("cld_step", {
            "plan": plan, "repo": path, "executor": "codex:stub-model@high",
            "validation_policy": "deny", "budget_attempts": 1}))
        job_id = started.get("job_id")
        assert job_id, started
        data = {}
        for _ in range(20):
            data = structured(server.call("cld_job", {"job_id": job_id, "wait_seconds": 5}))
            if data.get("state") in TERMINAL:
                break
        assert data.get("state") == "finished", data
        assert "--step" in driver_json(data)["argv"]
    finally:
        server.close()


def test_generated_bundle_lists_models_hermetically(tmp_path, jobs_root, unified_bundle):
    entry = unified_bundle / "scripts" / "cld_mcp.py"
    assert entry.is_file(), "bundle has no scripts/cld_mcp.py"
    fakes = tmp_path / "fake-bin"
    _stubs.make_fake_cli(fakes, "opencode", {("models",): "opencode/fake-model-xyz\n"})
    env = _bundle_env(jobs_root, PATH=str(fakes))
    for name in OVERRIDES:
        env.pop(name, None)
    server = McpProcess([sys.executable, str(entry)], env=env, cwd=tmp_path)
    try:
        server.initialize()
        data = structured(server.call("cld_list_models", {}, timeout=90))
    finally:
        server.close()
    specs = [m.get("spec", "") for m in data.get("models", [])]
    assert any("fake-model-xyz" in spec for spec in specs), specs
