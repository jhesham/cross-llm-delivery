"""v0.7.0 review fixes: concurrent tool calls; non-finite request ids."""
import time

from tests.v070._stubs import by_id, call, init, serve, structured


def test_concurrent_job_polls_do_not_queue(stub_env, repo, monkeypatch):
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "60")
    path, plan = (str(p) for p in repo)
    started = structured(by_id(serve(init(), call(1, "cld_step", {
        "plan": plan, "repo": path, "executor": "codex:stub-model@high",
        "validation_policy": "deny", "budget_attempts": 1}), scripts_dir=stub_env.scripts), 1))
    job_id = started["job_id"]
    t0 = time.monotonic()
    replies = serve(init(), call(1, "cld_job", {"job_id": job_id, "wait_seconds": 4}),
                    call(2, "cld_job", {"job_id": job_id, "wait_seconds": 4}),
                    scripts_dir=stub_env.scripts)
    elapsed = time.monotonic() - t0
    for id_ in (1, 2):
        assert structured(by_id(replies, id_))["state"] == "running"
    assert elapsed < 7, f"two 4 s polls took {elapsed:.1f} s; requests are serialized"


def test_non_finite_request_id_is_refused_without_stopping(stub_env):
    try:
        replies = serve(init(), '{"jsonrpc": "2.0", "id": 1e999, "method": "ping"}',
                        {"jsonrpc": "2.0", "id": 2, "method": "ping"}, scripts_dir=stub_env.scripts)
    except ValueError as exc:
        raise AssertionError(f"server stopped on a non-finite id: {exc}") from None
    refused = [r for r in replies if r.get("id") is None]
    assert refused and refused[0]["error"]["code"] == -32600, replies
    assert by_id(replies, 2)["result"] == {}


def test_saturated_server_refuses_excess_calls_promptly(stub_env, repo, monkeypatch):
    monkeypatch.setenv("CLD_STUB_MODE", "sleep")
    monkeypatch.setenv("CLD_STUB_SECONDS", "60")
    path, plan = (str(p) for p in repo)
    job_id = structured(by_id(serve(init(), call(1, "cld_step", {
        "plan": plan, "repo": path, "executor": "codex:stub-model@high",
        "validation_policy": "deny", "budget_attempts": 1}), scripts_dir=stub_env.scripts), 1))["job_id"]
    count = 40
    t0 = time.monotonic()
    replies = serve(init(), *[call(i, "cld_job", {"job_id": job_id, "wait_seconds": 3})
                              for i in range(1, count + 1)], scripts_dir=stub_env.scripts)
    elapsed = time.monotonic() - t0
    for i in range(1, count + 1):
        reply = by_id(replies, i)
        result = reply.get("result", {})
        assert result.get("isError") or result.get("structuredContent", {}).get("state") == "running", reply
    assert elapsed < 5.5, f"{count} concurrent 3 s polls took {elapsed:.1f} s; excess calls queued"
