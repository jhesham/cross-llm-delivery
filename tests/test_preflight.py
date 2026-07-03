"""Acceptance tests for the executor-CLI preflight (ship-plan B1).

Field problem: with no executor CLI installed, the first dispatch failed with a raw
FileNotFoundError traceback. The preflight must catch this at build start and print a
human explanation (which CLI is missing, how to install it, which installed provider
could be used instead) — and must never block the no-dispatch commands.
"""
import pytest

import skill.scripts.run_delivery as rd


def test_executor_cli_status_shape():
    # Machine-independent contract: a dict covering the three providers; each value is
    # either a resolved command string or None. Must not raise on any machine.
    status = rd._executor_cli_status()
    assert {"antigravity", "opencode", "cursor"} <= set(status.keys())
    for v in status.values():
        assert v is None or (isinstance(v, str) and v)


def test_preflight_ok_when_provider_cli_present(monkeypatch):
    monkeypatch.setattr(rd, "_executor_cli_status",
                        lambda: {"antigravity": None, "opencode": "/x/opencode", "cursor": None})
    assert rd._preflight_executor("opencode:opencode/glm-5.2") is None


def test_preflight_message_when_cli_missing_names_provider_and_install(monkeypatch):
    monkeypatch.setattr(rd, "_executor_cli_status",
                        lambda: {"antigravity": None, "opencode": None, "cursor": None})
    msg = rd._preflight_executor("opencode:opencode/glm-5.2")
    assert msg is not None
    assert "opencode" in msg.lower()
    assert "install" in msg.lower()


def test_preflight_suggests_installed_alternative(monkeypatch):
    # opencode missing but cursor IS installed -> the message offers the working alternative.
    monkeypatch.setattr(rd, "_executor_cli_status",
                        lambda: {"antigravity": None, "opencode": None, "cursor": "cursor-agent"})
    msg = rd._preflight_executor("opencode:opencode/glm-5.2")
    assert msg is not None and "--executor" in msg and "cursor" in msg


def test_step_aborts_before_dispatch_when_cli_missing(tmp_path, monkeypatch, capsys):
    plan = tmp_path / "plan.md"
    plan.write_text("## SLICE: A\nbrief: b\nfiles: x.py\nacceptance_test_path: t.py\ndeps:\n",
                    encoding="utf-8")
    monkeypatch.setattr(rd, "_executor_cli_status",
                        lambda: {"antigravity": None, "opencode": None, "cursor": None})

    def boom(*a, **k):
        raise AssertionError("must not dispatch when preflight fails")

    monkeypatch.setattr(rd, "run_plan_parallel", boom)
    rc = rd.main([str(plan), "--repo", str(tmp_path), "--ledger", str(tmp_path / "l.json"),
                  "--executor", "opencode:opencode/glm-5.2", "--step"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "opencode" in out.lower() and "install" in out.lower()


def test_dry_run_and_status_not_blocked_by_missing_cli(tmp_path, monkeypatch, capsys):
    # No-dispatch commands must keep working on a machine with zero CLIs installed.
    plan = tmp_path / "plan.md"
    plan.write_text("## SLICE: A\nbrief: b\nfiles: x.py\nacceptance_test_path: t.py\ndeps:\n",
                    encoding="utf-8")
    monkeypatch.setattr(rd, "_executor_cli_status",
                        lambda: {"antigravity": None, "opencode": None, "cursor": None})
    rc = rd.main([str(plan), "--repo", str(tmp_path), "--executor", "opencode:x", "--dry-run"])
    assert rc == 0
    rc = rd.main(["--status", "--repo", str(tmp_path)])
    assert rc == 0
