"""Offline admission, evidence and CLI routing contracts."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from cld.admission import Admission, AdmissionBlocked, validation_context
from cld.evidence import EvidenceStore, EvidenceError
from cld.executors.base import SliceTask
from cld.models import resolve_spec
from cld.process import run_process
from cld.validate import ValidationResult
from cld.providers_api import load_providers

load_providers()
SPEC = "opencode:opencode/test-model"


def gate(tmp_path, *, status="untested", cost="flat", policy="allow", force=False,
         context=None, verdict=None, store=None, max_age=86400):
    calls = []
    def validate(spec):
        calls.append(spec)
        return verdict or ValidationResult(spec, True, "verified", 1, usage={"input": 17})
    instance = Admission(store=store or EvidenceStore(tmp_path / "evidence.json"),
        validate_fn=validate, context_of=lambda _: context if context is not None else {"version": 1},
        policy=policy, force=force, max_age_seconds=max_age,
        policy_of=lambda _: (status, cost), report_path=tmp_path / "admission.json")
    return instance, calls


@pytest.mark.parametrize("status", ["verified", "likely", "untested"])
def test_static_catalog_cannot_bypass_context_validation(tmp_path, status):
    admission, calls = gate(tmp_path, status=status, policy="deny")
    result = admission.check(SPEC)
    assert not result.proceeded and result.status == "blocked" and not calls
    assert json.loads((tmp_path / "admission.json").read_text())["validation_policy"] == "deny"


@pytest.mark.parametrize("cost,allowed", [("flat", True), ("free", True), ("metered-unknown", False), ("premium-metered", False)])
def test_unmetered_policy_never_authorizes_unknown_cost(tmp_path, cost, allowed):
    admission, calls = gate(tmp_path, cost=cost, policy="unmetered")
    assert admission.check(SPEC).proceeded is allowed
    assert bool(calls) is allowed


def test_cache_deduplicates_and_context_change_requires_new_probe(tmp_path):
    context = {"version": 1}
    admission, calls = gate(tmp_path, context=context)
    assert admission.check(SPEC).proceeded
    assert admission.check(SPEC).proceeded and len(calls) == 1
    context["version"] = 2
    assert admission.check(SPEC).proceeded and len(calls) == 2
    record = admission.store.get("opencode/test-model")
    assert record["usage"] == {"input": 17}
    resumed, resumed_calls = gate(tmp_path, context={"version": 2}, policy="deny")
    assert resumed.check(SPEC).proceeded and not resumed_calls
    expired, expired_calls = gate(tmp_path, context={"version": 2}, policy="deny", max_age=0)
    assert not expired.check(SPEC).proceeded and not expired_calls


@pytest.mark.parametrize("status", ["verified", "likely", "revalidate"])
def test_force_ignores_catalog_and_durable_failure_then_deduplicates(tmp_path, status):
    store = EvidenceStore(tmp_path / "evidence.json")
    store.record("opencode/test-model", "revalidate", context={"version": 1})
    admission, calls = gate(tmp_path, force=True, status=status, store=store)
    assert admission.check(SPEC).proceeded
    assert admission.check(SPEC).proceeded and len(calls) == 1
    assert store.get("opencode/test-model")["status"] == "verified"


def test_failed_and_inconclusive_probes_never_admit(tmp_path):
    admission, calls = gate(tmp_path, verdict=ValidationResult(SPEC, False, "untested", 1,
        "authentication failed", usage={"output": 3}, error="authentication"))
    assert not admission.check(SPEC).proceeded
    assert admission.store.get("opencode/test-model") is None
    assert admission.records[-1]["usage"] == {"output": 3}
    admission.store.record("opencode/test-model", "revalidate")
    new, calls = gate(tmp_path)
    assert not new.check(SPEC).proceeded and not calls


def test_current_verified_evidence_overrides_older_catalog_failure(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.json")
    store.record("opencode/test-model", "verified", context={"version": 1})
    admission, calls = gate(tmp_path, store=store, status="revalidate", policy="deny")
    assert admission.check(SPEC).proceeded and not calls


def test_corrupt_evidence_blocks_even_force(tmp_path):
    (tmp_path / "evidence.json").write_text("broken", encoding="utf-8")
    admission, calls = gate(tmp_path, force=True)
    assert not admission.check(SPEC).proceeded and not calls


def test_context_changes_with_cli_config_environment_and_effort(tmp_path, monkeypatch):
    cli, config = tmp_path / "cli", tmp_path / "config"
    cli.write_text("v1"); config.write_text("setting1")
    def context(spec=SPEC):
        return validation_context(spec, cli_paths=[cli], config_paths=[config], repo=tmp_path)
    values = [context()]
    cli.write_text("v2"); values.append(context())
    config.write_text("setting2"); values.append(context())
    monkeypatch.setenv("CLD_FIXTURE_SECRET", "never-serialize-this-value"); values.append(context())
    values.append(context(SPEC + "@high"))
    assert len({v["fingerprint"] for v in values}) == 5
    assert "never-serialize" not in json.dumps(values)


def test_concurrent_processes_preserve_all_evidence(tmp_path):
    path = tmp_path / "evidence.json"
    code = ("from cld.evidence import EvidenceStore; import sys; "
            "s=EvidenceStore(sys.argv[1]); "
            "[s.record(sys.argv[2]+str(i),'verified') for i in range(8)]")
    def writer(prefix):
        return run_process([sys.executable, "-c", code, str(path), prefix], tmp_path,
            env={"PYTHONPATH": str(Path("engine").resolve())}, timeout=20)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(writer, ["a", "b"]))
    assert all(r.returncode == 0 for r in results), [r.output for r in results]
    assert len(EvidenceStore(path).statuses()) == 16


@pytest.fixture
def cli_setup(tmp_path, monkeypatch):
    import skill.scripts.run_delivery as rd
    import cld.admission as admission
    import cld.evidence as evidence
    import cld.validate as validation
    monkeypatch.setattr(evidence, "DEFAULT_PATH", tmp_path / "store.json")
    monkeypatch.setattr(admission, "validation_context", lambda spec, **kw: {"spec": spec})
    monkeypatch.setattr(rd, "_resolve_cli", lambda cmd: sys.executable)
    monkeypatch.setattr(rd, "_available_ids_for", lambda *args: [])
    monkeypatch.setattr(rd, "_preflight_executor", lambda spec: None)
    monkeypatch.setattr(rd, "get_executor", lambda *a, **kw: object())
    calls = []
    def validate(spec, **kwargs):
        calls.append(spec)
        return ValidationResult(spec, True, "verified", 1, usage={"input": 5})
    monkeypatch.setattr(validation, "validate_model", validate)
    args = SimpleNamespace(repo=str(tmp_path), worktree_root=None, step=False,
        executor=SPEC, validation_policy="allow", validation_max_age=86400,
        revalidate_models=False, validation_config=[], validation_context="")
    ledger = SimpleNamespace(build={"run_id": "a" * 32}, is_done=lambda sid: False, get=lambda sid: None)
    return rd, args, ledger, calls


def test_default_tag_and_escalation_all_use_same_gate(cli_setup, monkeypatch):
    rd, args, ledger, calls = cli_setup
    tasks = [SliceTask("A", "brief", ["x"], "t.py"), SliceTask("B", "brief", ["y"], "t.py", executor="cursor:custom")]
    monkeypatch.setattr(rd, "build_rung_planner", lambda *a, **kw: lambda task:
        [("entry", task.executor or SPEC, 1), ("fallback", "antigravity:custom", 1)])
    factory, planner = rd.prepare_dispatch(args, tasks, ledger)
    assert set(calls) == {SPEC, "cursor:custom", "antigravity:custom"}
    assert len(calls) == 3
    factory(SPEC); factory("cursor:custom")
    assert len(calls) == 3
    assert planner(tasks[1])[0][1] == "cursor:custom"
    with pytest.raises(AdmissionBlocked):
        factory("cursor:not-admitted")


@pytest.mark.parametrize("failure", ["policy", "provider", "filesystem", "corrupt"])
def test_no_probe_when_any_preflight_or_policy_blocks(cli_setup, monkeypatch, tmp_path, failure):
    rd, args, ledger, calls = cli_setup
    tasks = [SliceTask("A", "brief", ["x"], "t.py"), SliceTask("B", "brief", ["y"], "t.py", executor="cursor:custom")]
    if failure == "policy":
        args.validation_policy = "deny"
    elif failure == "provider":
        monkeypatch.setattr(rd, "_preflight_executor", lambda spec: "missing cursor" if spec.startswith("cursor:") else None)
    elif failure == "filesystem":
        import cld.admission as admission
        def denied(*args):
            raise PermissionError("fixture: denied")
        monkeypatch.setattr(admission, "writable_directory", denied)
    else:
        (tmp_path / "store.json").write_text("broken")
    monkeypatch.setattr("builtins.input", lambda *args: pytest.fail("must not prompt"))
    with pytest.raises((AdmissionBlocked, PermissionError, EvidenceError)):
        rd.prepare_dispatch(args, tasks, ledger)
    assert not calls


def test_unknown_provider_does_not_fall_back(cli_setup):
    rd, args, ledger, calls = cli_setup
    args.executor = "absent:model"
    with pytest.raises(ValueError, match="Unknown provider"):
        rd.prepare_dispatch(args, [SliceTask("A", "brief", ["x"], "t.py")], ledger)
    assert not calls


def test_atomic_failure_keeps_previous_evidence(tmp_path, monkeypatch):
    import cld.recovery as recovery
    store = EvidenceStore(tmp_path / "evidence.json")
    store.record("before", "verified")
    original = store._path.read_bytes()
    def fail(*args):
        raise PermissionError("fixture: replace denied")
    monkeypatch.setattr(recovery.os, "replace", fail)
    with pytest.raises(PermissionError):
        store.record("after", "verified")
    assert store._path.read_bytes() == original


def test_unreadable_evidence_is_not_missing(tmp_path, monkeypatch):
    store = EvidenceStore(tmp_path / "evidence.json")
    def denied(*args, **kwargs):
        raise PermissionError("fixture")
    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(EvidenceError):
        store.get("m")


@pytest.mark.parametrize("status", ["verified", "likely", "revalidate"])
def test_legacy_force_bypasses_session_and_static_shortcuts(status):
    from cld.validate import resolve_and_validate
    calls = []
    def validate(spec):
        calls.append(spec)
        return ValidationResult(spec, True, "verified", 1)
    result = resolve_and_validate(SPEC, headless_status_of=lambda _: status,
        cost_class_of=lambda _: "free", validate_fn=validate, confirm_fn=lambda _: True,
        output_fn=lambda _: None, session_known_bad={SPEC}, force_revalidate=True)
    assert result.proceeded and result.validated and calls == [SPEC]


@pytest.mark.parametrize("allow", [False, True])
def test_real_cli_admits_before_production_and_returns_blocked_gate(cli_setup, monkeypatch, tmp_path, capsys, allow):
    rd, args, _, calls = cli_setup
    from tests.integration.harness import init_repo
    from cld.orchestrator import PlanResult
    repo = init_repo(tmp_path / "project")
    plan = tmp_path / "plan.md"
    plan.write_text("## SLICE: A\nbrief: b\nfiles: x.py\nacceptance_test_path: t.py\ndeps:\n", encoding="utf-8")
    produced = []
    def production(tasks, ledger, **kwargs):
        assert calls == [SPEC]
        produced.append(True)
        assert kwargs["executor_factory"](SPEC) is not None
        ledger.set("A", status="done"); ledger.save()
        return PlanResult(completed=["A"])
    monkeypatch.setattr(rd, "run_plan_parallel", production)
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("noninteractive admission must not prompt"))
    command = [str(plan), "--repo", repo, "--executor", SPEC, "--step"]
    if allow:
        command += ["--validation-policy", "allow"]
    code = rd.main(command)
    assert code == (6 if allow else 5)
    assert bool(calls) is allow and bool(produced) is allow
    if not allow:
        records = list(Path(repo, ".cld").rglob("validation-blocked.json"))
        assert json.loads(records[0].read_text())["gate_code"] == 5
