"""Tests for the run_delivery.py driver's --executor parsing (BUG 2 fix).

The user picks the LLM at invocation via --executor "name" or "name:model".
parse_executor_spec is pure, so we test it directly without invoking the CLI.
"""

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "skill" / "scripts" / "run_delivery.py"
_spec = importlib.util.spec_from_file_location("run_delivery", _SCRIPT)
run_delivery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_delivery)
parse_executor_spec = run_delivery.parse_executor_spec


def test_bare_name():
    assert parse_executor_spec("gemini") == ("gemini", {})


def test_name_with_model():
    assert parse_executor_spec("gemini:gemini-3-pro-preview") == (
        "gemini", {"model": "gemini-3-pro-preview"})


def test_default_when_empty():
    assert parse_executor_spec("") == ("gemini", {})


def test_strips_whitespace():
    assert parse_executor_spec("  gemini : model-x ") == ("gemini", {"model": "model-x"})


def test_other_executor_name():
    # forward-compatible with the future opencode executor
    assert parse_executor_spec("opencode:anthropic/claude") == (
        "opencode", {"model": "anthropic/claude"})


def test_colon_with_no_model_is_no_kwargs():
    assert parse_executor_spec("gemini:") == ("gemini", {})


def test_slash_form_from_picker_is_accepted():
    # The picker's display/catalog id uses a slash (opencode/<model>), but --executor
    # wants a colon (opencode:<model>). Be liberal: accept the slash form too, so a
    # copy-pasted catalog id doesn't error with "Unknown executor". (User-reported trap.)
    assert parse_executor_spec("opencode/deepseek-v4-pro") == (
        "opencode", {"model": "deepseek-v4-pro"})
    # the canonical colon form still works identically
    assert parse_executor_spec("opencode:deepseek-v4-pro") == (
        "opencode", {"model": "deepseek-v4-pro"})
    # a slash for an UNKNOWN prefix stays a bare name (don't over-eagerly split)
    assert parse_executor_spec("anthropic/claude") == ("anthropic/claude", {})


# ---- Bug B: pytest_test_runner scopes to the slice's acceptance test ----

def test_pytest_test_runner_scopes_to_acceptance_path(monkeypatch):
    captured = {}

    class _Proc:
        returncode = 0
        stdout = "1 passed in 0.0s"
        stderr = ""

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["cwd"] = kwargs.get("cwd")
        captured["timeout"] = kwargs.get("timeout")
        return _Proc()

    monkeypatch.setattr(run_delivery.subprocess, "run", fake_run)
    out = run_delivery.pytest_test_runner("/wt", "tests/test_merge.py")
    assert "1 passed" in out
    # the acceptance path is in the argv; it is NOT a bare whole-suite run
    assert "tests/test_merge.py" in captured["argv"]
    assert captured["cwd"] == "/wt"
    assert captured["timeout"]  # a timeout guard is set


def test_pytest_test_runner_splits_test_selector(monkeypatch):
    # Shared accumulating test files need per-slice scoping: an acceptance_test_path
    # like "tests/test_x.py::test_one" (or with -k) must be split into SEPARATE argv
    # tokens so pytest applies the node id / -k expr — not passed as one malformed arg.
    captured = {}

    class _Proc:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    monkeypatch.setattr(run_delivery.subprocess, "run",
                        lambda argv, **kw: captured.update(argv=argv) or _Proc())

    run_delivery.pytest_test_runner("/wt", "tests/test_advisor_graph.py::test_merge_dict_reducer")
    assert "tests/test_advisor_graph.py::test_merge_dict_reducer" in captured["argv"]

    run_delivery.pytest_test_runner("/wt", 'tests/test_advisor_graph.py -k "merge"')
    argv = captured["argv"]
    # the path, the -k flag, and the expression are three distinct argv tokens
    assert "tests/test_advisor_graph.py" in argv
    assert "-k" in argv
    assert "merge" in argv  # quotes stripped by shlex, expression is its own token


def test_pytest_test_runner_without_path_runs_default(monkeypatch):
    # backward-compatible: no path -> runs pytest with no explicit target (still scoped
    # by cwd), and must not crash.
    class _Proc:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    monkeypatch.setattr(run_delivery.subprocess, "run", lambda argv, **kw: _Proc())
    assert "passed" in run_delivery.pytest_test_runner("/wt")


def test_build_executor_factory_resolves_specs():
    factory = run_delivery.build_executor_factory()
    from cld_providers.antigravity.provider import AntigravityExecutor
    from cld.executors.opencode import OpenCodeExecutor
    assert isinstance(factory("antigravity"), AntigravityExecutor)
    assert isinstance(factory("opencode:opencode/claude-sonnet-4-6"), OpenCodeExecutor)
    # tolerant slash form also resolves (no Unknown executor)
    assert isinstance(factory("opencode/deepseek-v4-pro"), OpenCodeExecutor)


def test_parse_executor_spec_splits_effort_marker():
    assert parse_executor_spec("cursor:claude-opus-4-8@low") == (
        "cursor", {"model": "claude-opus-4-8", "effort": "low"})
    assert parse_executor_spec("opencode:opencode/gpt-5@high") == (
        "opencode", {"model": "opencode/gpt-5", "effort": "high"})
    # no @ -> unchanged behavior (back-compat)
    assert parse_executor_spec("gemini:gemini-3.1-pro-preview") == (
        "gemini", {"model": "gemini-3.1-pro-preview"})


def test_usage_flag_renders_from_ledger_and_stats(monkeypatch, tmp_path, capsys):
    """--usage flag renders the usage table; provider account sections are self-sourced.

    The ledger has an opencode slice.  We register a fake opencode provider with a
    controlled account_section so the test doesn't shell out and is deterministic.
    """
    import json
    from cld.providers_api import _REGISTRY, register_provider, Provider

    p = str(tmp_path / ".cld-ledger.json")
    json.dump({"T1": {"status": "done", "commit": "a", "attempts": 1,
                      "model": "opencode/deepseek-v4-pro",
                      "token_usage": {"total": 100}, "cost": None}}, open(p, "w"))

    # Fake opencode provider with a fixed account_section
    def _noop_exec(**k): raise NotImplementedError
    fake_oc = Provider(
        name="opencode",
        make_executor=_noop_exec,
        catalog=(),
        default_workhorse="opencode:default",
        list_models=lambda r: [],
        account_stats=None,
        account_block=None,
        account_section=lambda: ["## OpenCode account", "Total cost: $5.64"],
        skill_fragment="",
        setup_notes="",
    )

    snap = dict(_REGISTRY)
    _REGISTRY.clear()
    register_provider(fake_oc)

    # Prevent load_providers from re-registering real providers during render
    from unittest.mock import patch
    with patch("cld.providers_api.load_providers"):
        rc = run_delivery.main(["dummy-plan.md", "--ledger", p, "--usage"])

    _REGISTRY.clear()
    _REGISTRY.update(snap)

    out = capsys.readouterr().out
    assert rc == 0
    assert "T1" in out and "5.64" in out


def test_per_slice_pick_removed():
    import skill.scripts.run_delivery as rd
    assert not hasattr(rd, "make_slice_pick_fn")
    # --per-slice-pick no longer a recognised flag
    import pytest
    with pytest.raises(SystemExit):
        rd.main(["plan.md", "--per-slice-pick"])


def test_step_help_documents_gate_4(capsys):
    """--step help text must mention exit code 4 (needs orchestrator repair)."""
    import pytest
    with pytest.raises(SystemExit):
        run_delivery.main(["--help"])
    out = capsys.readouterr().out
    assert "4" in out


def test_provider_of_spec():
    import skill.scripts.run_delivery as rd
    assert rd._provider_of_spec("gemini") == "gemini"
    assert rd._provider_of_spec("gemini:gemini-3.1-pro-preview") == "gemini"
    assert rd._provider_of_spec("opencode:opencode/deepseek-v4-pro") == "opencode"
    assert rd._provider_of_spec("cursor:composer-2.5") == "cursor"


def test_build_rung_planner_untagged_uses_provider_workhorse():
    import skill.scripts.run_delivery as rd
    from cld.executors.base import SliceTask
    planner = rd.build_rung_planner("antigravity", evidence={})
    rungs = planner(SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py",
                              complexity="standard"))
    assert rungs == [("workhorse", "antigravity:Gemini 3.1 Pro (High)", 2)]


def test_build_rung_planner_tagged_pins():
    import skill.scripts.run_delivery as rd
    from cld.executors.base import SliceTask
    planner = rd.build_rung_planner("gemini", evidence={})
    rungs = planner(SliceTask(id="S", brief="b", files=["x"], acceptance_test_path="t.py",
                              executor="opencode:opencode/claude-opus-4-8"))
    assert rungs == [("workhorse", "opencode:opencode/claude-opus-4-8", 2)]


def test_mark_repaired_marks_slice_done(tmp_path):
    import skill.scripts.run_delivery as rd
    from cld.ledger import Ledger
    p = str(tmp_path / "l.json")
    led = Ledger(p); led.set("T1", status="needs_repair", complexity="complex"); led.save()
    rc = rd.main(["dummy-plan.md", "--ledger", p, "--mark-repaired", "T1"])
    assert rc == 0
    e = Ledger.load(p).get("T1")
    assert e.status == "done" and e.intervened is True and e.final_rung == "orchestrator"
