"""Lead review regressions beyond the immutable T11 dogfood acceptance input."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cld import cli, cli_response, telemetry
from cld.build_state import run_directory
from cld.ledger import Ledger, StateError
from cld.executors.base import SliceTask
from tests.integration.harness import init_repo, real_git_runner


@pytest.mark.parametrize("flags", [
    ["--status", "--integrate"], ["--usage", "--step"],
    ["--dry-run", "--integrate"], ["--status", "--dry-run"],
])
def test_conflicting_actions_rejected(flags):
    with pytest.raises(StateError):
        cli._validate(cli.build_parser().parse_args(flags))


def test_relative_default_ledger_resolves(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    repo, ledger = cli._paths_from(".", None)
    assert repo == str(tmp_path.resolve())
    assert ledger == str(tmp_path / ".cld-ledger.json")


def test_blocked_operation_without_accounting_is_not_pending():
    ledger = SimpleNamespace(build={"last_operation": {"gate_code": 5}}, entries={})
    assert cli._status_gate(ledger) == "blocked"


@pytest.fixture
def bound(tmp_path):
    repo = Path(init_repo(tmp_path / "repo"))
    ledger = Ledger(str(repo / ".cld-ledger.json"))
    with ledger.writer():
        ledger.bind(str(repo), [SliceTask("A", "work", ["a.py"], "test_a.py")], real_git_runner)
        ledger.save()
    return repo, ledger


def test_attempt_must_match_selected_slice(bound):
    repo, ledger = bound
    usage = run_directory(str(repo), ledger.build["run_id"]) / "usage"
    usage.mkdir(parents=True)
    ident = "a" * 32
    (usage / f"attempt-{ident}.json").write_text(json.dumps({
        "id": ident, "slice_id": "B", "kind": "production", "usage": {},
    }), encoding="utf-8")
    record, error = cli._attempt_record(SimpleNamespace(repo=str(repo), slice="A", attempt=ident), ledger)
    assert record is None and error


def test_status_rejects_wrong_repository(bound, tmp_path, capsys):
    repo, ledger = bound
    other = tmp_path / "other"
    other.mkdir()
    rc = cli.main(["--json", "--status", "--repo", str(other), "--ledger", ledger.path])
    data = json.loads(capsys.readouterr().out)
    assert rc == 5 and data["errors"]


def test_large_response_preserves_collection_types_and_exact_refs():
    refs = [{"slice": str(i), "ref": "refs/cld/accepted/" + "x" * 180,
             "commit": "a" * 40} for i in range(1000)]
    response = cli_response.build(command="status", gate="integration_required", accepted_refs=refs)
    raw = cli_response.dumps(response)
    data = json.loads(raw)
    assert len(raw.encode("utf-8")) < 32768
    assert isinstance(data["accepted_refs"], list)
    assert data["accepted_refs"] and data["accepted_refs"][0] == refs[0]
    assert data["accepted_refs_truncated"] and data["accepted_refs_count"] == 1000


def test_host_cleared_after_structured_error(capsys):
    assert cli.main(["--json", "--host", "codex", "--invalid"]) == 5
    assert json.loads(capsys.readouterr().out)["errors"]
    assert telemetry.get_host() is None


def test_json_step_on_tty_never_prompts(monkeypatch, capsys, tmp_path):
    repo = Path(init_repo(tmp_path / "repo"))
    plan = tmp_path / "plan.md"
    plan.write_text("## SLICE: A\nbrief: work\nfiles: a.py\nacceptance_test_path: test_a.py\ndeps:\n", encoding="utf-8")
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    def prompt():
        pytest.fail("JSON command prompted on a TTY")
    def admission(*args):
        raise cli.EvidenceError("Provider credentials unavailable")
    monkeypatch.setattr(cli, "prompt_for_executor", prompt)
    monkeypatch.setattr(cli, "prepare_dispatch", admission)
    assert cli.main([str(plan), "--repo", str(repo), "--step", "--json"]) == 5
    data = json.loads(capsys.readouterr().out)
    assert data["run_id"] == Ledger.load(str(repo / ".cld-ledger.json")).build["run_id"]
    assert "credentials" in data["errors"][0]["reason"]


def test_real_pytest_long_failure_summary_retains_assertion(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    name = "test_" + "long_assertion_baseline_" * 8
    (tmp_path / "test_baseline.py").write_text(f"def {name}():\n    assert False\n", encoding="utf-8")
    result = cli.pytest_test_runner(str(tmp_path), "test_baseline.py")
    failures = [line for line in result.output.splitlines() if line.startswith("FAILED ")]
    assert result.returncode == 1 and failures
    assert all(" - assert" in line or " - AssertionError" in line for line in failures)


@pytest.mark.parametrize("flags,code", [(["--step"], 6), ([], 2), (["--integrate"], 3), (["--mark-repaired", "A"], 4), (["--reconcile-plan"], 4)])
def test_json_action_transports_gate_without_progress_on_stdout(bound, monkeypatch, capsys, flags, code):
    repo, ledger = bound
    def action(args):
        print("diagnostic progress")
        return code
    monkeypatch.setattr(cli, "_run", action)
    rc = cli.main(["--json", "plan.md", "--repo", str(repo), *flags])
    out = capsys.readouterr()
    data = json.loads(out.out)
    assert rc == code == data["gate_code"]
    assert "diagnostic progress" in out.err
