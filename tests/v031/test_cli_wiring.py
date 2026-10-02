"""v0.3.1 CLI wiring: gc command, network gate, launch preflight, chosen source label."""
import dataclasses
import json
import subprocess

import pytest

from cld import cli
from cld.admission import AdmissionBlocked
from cld.providers_api import get_provider, load_providers
from tests.integration.harness import init_repo

RUN = "a" * 32


def _json(argv, capsys):
    code = cli.main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _worktree(repo, slug="A", n=1, run=RUN):
    root = repo / ".cld" / "worktrees"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{slug}-{run[:8]}-{n:032x}"
    subprocess.run(["git", "worktree", "add", "-q", "-b", f"cld/{run}/{slug}/{n:032x}", str(path)],
                   cwd=repo, check=True)
    return path


def test_gc_preview_is_default_and_read_only(tmp_path, capsys):
    repo = tmp_path / "repo"
    init_repo(repo)
    path = _worktree(repo)
    code, payload = _json(["--gc", "--repo", str(repo)], capsys)
    assert code == 0 and payload["command"] == "gc"
    rows = payload["details"]["worktrees"]
    assert [row["action"] for row in rows] == ["keep"] and rows[0]["reason"]
    assert payload["details"]["applied"] is False
    assert path.exists()


def test_gc_apply_with_include_previous_removes_clean_earlier_build(tmp_path, capsys):
    repo = tmp_path / "repo"
    init_repo(repo)
    path = _worktree(repo)
    # v0.4.0 R01: removal needs recovery evidence proving the worktree's slice.
    evidence = repo / ".cld" / "runs" / RUN / "A" / f"{1:032x}"
    evidence.mkdir(parents=True)
    (evidence / "outcome.json").write_text(json.dumps(dict(
        session_id=f"{1:032x}", slice_id="A", worktree=str(path.resolve()), state="failed")))
    code, payload = _json(["--gc", "--apply", "--include-previous", "--repo", str(repo)], capsys)
    assert code == 0
    assert [r["action"] for r in payload["details"]["results"]] == ["removed"]
    assert not path.exists()


@pytest.mark.parametrize("flag", ["--apply", "--include-previous"])
def test_gc_modifiers_require_gc(tmp_path, capsys, flag):
    repo = tmp_path / "repo"
    init_repo(repo)
    code, payload = _json([flag, "--repo", str(repo)], capsys)
    assert code == 5 and "--gc" in json.dumps(payload)


def test_network_disabled_sandbox_blocks_before_dispatch(monkeypatch):
    monkeypatch.delenv("CLD_EXECUTOR_DEPTH", raising=False)
    monkeypatch.setenv("CODEX_SANDBOX_NETWORK_DISABLED", "1")
    stub = type("Args", (), {"step": False, "executor": "codex:gpt-x@low"})()
    with pytest.raises(AdmissionBlocked, match="network"):
        cli.prepare_dispatch(stub, [], None)


def test_launch_problem_blocks_preflight(monkeypatch):
    load_providers()
    blocked = dataclasses.replace(get_provider("codex"),
                                  launch_problem=lambda: "shim only; set CODEX_CLI_CMD")
    monkeypatch.setattr(cli, "_executor_cli_status", lambda: {"codex": "/abs/codex"})
    monkeypatch.setattr(cli, "get_provider", lambda name: blocked)
    assert "CODEX_CLI_CMD" in cli._preflight_executor("codex:gpt-x@low")


def test_launch_problem_absent_passes_preflight(monkeypatch):
    load_providers()
    fine = dataclasses.replace(get_provider("codex"), launch_problem=lambda: None)
    monkeypatch.setattr(cli, "_executor_cli_status", lambda: {"codex": "/abs/codex"})
    monkeypatch.setattr(cli, "get_provider", lambda name: fine)
    assert cli._preflight_executor("codex:gpt-x@low") is None


@pytest.mark.parametrize("executor,expected", [("codex:gpt-x@low", "chosen"), (None, "default")])
def test_execute_passes_default_source(monkeypatch, executor, expected):
    seen = {}

    def fake_run(slices, ledger, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop after capture")

    monkeypatch.setattr(cli, "run_plan_parallel", fake_run)
    monkeypatch.setattr(cli, "_install_telemetry", lambda *a, **k: "events.jsonl")
    args = type("Args", (), dict(step=False, executor=executor, plan="p.md", repo=".", workers=1,
                                 worktree_root=None, integration_tests=None))()
    with pytest.raises(RuntimeError, match="stop after capture"):
        cli._execute(args, [], object())
    assert seen["default_source"] == expected
