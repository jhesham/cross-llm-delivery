import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from cld.accounting import Accounting, aggregate, dispatch_context, normalize
from cld.admission import AdmissionBlocked
from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.status import render_accounting_status
from tests.integration.harness import init_repo, real_git_runner


@pytest.fixture
def bound(tmp_path):
    repo = init_repo(tmp_path / "repo")
    ledger = Ledger(str(Path(repo) / ".cld-ledger.json"))
    task = SliceTask("A", "brief", ["a.py"], "test_a.py")
    with ledger.writer():
        ledger.bind(repo, [task], real_git_runner)
        yield ledger, task


def test_normalization_does_not_double_count_cache_or_invent_missing_values():
    usage = normalize({"input": 10, "output": 5, "cache_read": 8, "cache_write": 2})
    assert usage["total"] == 15 and usage["total_source"] == "derived_input_output"
    assert normalize({"input": 10})["total"] is None
    assert normalize({"total": 30, "input": 10, "output": 5})["total"] == 30
    assert normalize({"total": True, "cost": float("nan")})["cost"] is None
    assert aggregate([{"state": "finished", "usage": normalize({})}])["total"] is None


def test_three_attempts_mixed_models_and_resume_are_cumulative(bound):
    ledger, task = bound
    account = Accounting(ledger)
    for index, (model, kind) in enumerate([("opencode:a", "validation"), ("cursor:b@high", "production"), ("opencode:c", "production")]):
        ident = account.reserve(model=model, slice_id=task.id, kind=kind, identity={"fingerprint": "cli-v1"})
        account.finish(ident, ExecutorResult(index == 2, "", token_usage={"total": 10, "cost": .25}))
    assert ledger.build["usage"]["total"] == 30
    assert ledger.get("A").token_usage["total"] == 20
    assert ledger.get("A").cost == .5
    assert ledger.build["usage"]["validation"]["total"] == 10
    restored = Accounting(ledger)
    assert len(restored.records) == 3 and ledger.build["usage"]["cost"] == .75
    assert "tokens: 30" in render_accounting_status(ledger)
    assert len(list(account.directory.glob("attempt-*.json"))) == 3
    assert any(r.get("effort") == "high" for r in restored.records.values())


def test_concurrent_reservations_cannot_oversubscribe(bound):
    ledger, _ = bound
    account = Accounting(ledger, {"tokens": 100, "attempt_tokens": 60})
    def reserve(sid):
        try:
            return account.reserve(model="cursor:m", slice_id=sid, kind="production", identity=None)
        except AdmissionBlocked:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, ["A", "B"]))
    assert sum(r is not None for r in results) == 1
    assert ledger.build["usage"]["total_reserved"] == 60
    assert "in-flight" in ledger.build["usage"]["blocked"]


@pytest.mark.parametrize("policy,allowed", [("deny", False), ("reserve", True)])
def test_unknown_completed_cost_uses_explicit_policy(bound, policy, allowed):
    ledger, task = bound
    account = Accounting(ledger, {"cost": 2, "attempt_cost": 1, "unknown": policy})
    ident = account.reserve(model="antigravity:m", slice_id=task.id, kind="validation", identity=None)
    account.finish(ident, ExecutorResult(True, ""))
    assert ledger.build["usage"]["cost"] is None
    if allowed:
        account.reserve(model="antigravity:m", slice_id=task.id, kind="production", identity=None)
    else:
        with pytest.raises(AdmissionBlocked, match="Unknown cost"):
            account.reserve(model="antigravity:m", slice_id=task.id, kind="production", identity=None)


def test_observed_overrun_stops_next_call(bound):
    ledger, task = bound
    account = Accounting(ledger, {"tokens": 100, "attempt_tokens": 50})
    ident = account.reserve(model="cursor:m", slice_id=task.id, kind="production", identity=None)
    account.finish(ident, ExecutorResult(True, "", token_usage={"total": 120}))
    assert ledger.build["usage"]["total_overrun"] == 20
    with pytest.raises(AdmissionBlocked):
        account.reserve(model="cursor:m", slice_id=task.id, kind="production", identity=None)


def test_crash_between_journal_and_ledger_reconciles_without_double_count(bound, monkeypatch):
    ledger, task = bound
    account = Accounting(ledger)
    ident = account.reserve(model="cursor:m", slice_id=task.id, kind="production", identity=None)
    real_save = ledger.save
    monkeypatch.setattr(ledger, "save", lambda: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        account.finish(ident, ExecutorResult(True, "", token_usage={"total": 12}))
    monkeypatch.setattr(ledger, "save", real_save)
    restored = Accounting(ledger)
    assert ledger.build["usage"]["total"] == 12 and len(restored.records) == 1


def test_interrupted_reservation_is_unknown_not_free_on_resume(bound):
    ledger, task = bound
    account = Accounting(ledger, {"tokens": 100, "attempt_tokens": 60})
    account.reserve(model="cursor:m", slice_id=task.id, kind="production", identity=None)
    resumed = Accounting(ledger)
    assert ledger.build["usage"]["in_flight"] == 0
    assert ledger.build["usage"]["total_unknown"] == 1
    with pytest.raises(AdmissionBlocked, match="Unknown total"):
        resumed.reserve(model="cursor:m", slice_id=task.id, kind="production", identity=None)


def test_wrapper_records_retry_context_and_exception(bound):
    ledger, task = bound
    account = Accounting(ledger)
    class Executor:
        def run(self, task, cwd):
            raise KeyboardInterrupt()
    ex = account.wrap(Executor(), "cursor:m")
    with dispatch_context(attempt=2, source="escalated", reason="failed assertion", rung="premium"):
        with pytest.raises(KeyboardInterrupt):
            ex.run(task, ".")
    record = next(iter(account.records.values()))
    assert record["state"] == "interrupted"
    assert record["dispatch"]["source"] == "escalated"
    assert ledger.build["usage"]["total"] is None


def test_status_uses_persisted_summary_without_scanning_events(bound, monkeypatch):
    ledger, _ = bound
    Accounting(ledger)
    import importlib.util
    spec = importlib.util.spec_from_file_location("rd_t10", Path(__file__).parents[1] / "skill/scripts/run_delivery.py")
    rd = importlib.util.module_from_spec(spec); spec.loader.exec_module(rd)
    monkeypatch.setattr(rd, "_read_event_stream", lambda *args: pytest.fail("unbounded stream scan"))
    assert "attempts: 0" in rd._render_build_status(ledger.build["repo"], ledger)


@pytest.mark.parametrize("policy", [{"tokens": 100}, {"cost": -1}, {"attempts": True}, {"cost": float("inf")}])
def test_invalid_budget_is_rejected_before_dispatch(bound, policy):
    with pytest.raises(ValueError):
        Accounting(bound[0], policy)


def test_old_ledger_usage_is_not_mistaken_for_complete_history(bound):
    ledger, task = bound
    ledger.set(task.id, attempts=3, token_usage={"total": 100})
    ledger.save()
    account = Accounting(ledger)
    assert ledger.build["usage"]["total"] is None
    record = next(iter(account.records.values()))
    assert record["legacy_final_usage"] == {"total": 100}


def test_provider_parsers_retain_unknown_partial_categories():
    from cld_providers.opencode.provider import parse_opencode_usage, raw_usage
    from cld_providers.cursor.provider import parse_cursor_usage
    raw = '\n'.join(json.dumps({"type": "step_finish", "part": p}) for p in [
        {"tokens": {"input": 10, "output": 2, "cache": {"read": 5}}, "cost": .2},
        {"tokens": {"input": 20}}])
    parsed = parse_opencode_usage(raw)
    assert parsed == {"input": 30}
    assert normalize(parsed)["total"] is None and normalize(parsed)["cost"] is None
    assert raw_usage(raw)[0]["tokens"]["cache"]["read"] == 5
    assert "total" not in parse_cursor_usage('{"usage":{"inputTokens":4}}')


def test_failing_telemetry_close_does_not_leak_sibling():
    from cld.telemetry import MultiSink
    closed = []
    class Bad:
        def close(self):
            raise OSError("fixture")
    class Good:
        def close(self):
            closed.append(True)
    MultiSink([Bad(), Good()]).close()
    assert closed == [True]


def test_legacy_status_does_not_render_unknown_cost_as_zero():
    from cld.status import render_status
    text = render_status([{"type": "dispatch_end", "model": "fake:m", "tokens": {}}])
    assert "tokens: unknown" in text and "cost: unknown" in text


def test_per_attempt_overrun_blocks_even_without_cumulative_limit(bound):
    ledger, task = bound
    account = Accounting(ledger, {"attempt_tokens": 10})
    ident = account.reserve(model="cursor:m", slice_id=task.id, kind="production", identity=None)
    account.finish(ident, ExecutorResult(True, "", token_usage={"total": 11}))
    assert ledger.build["usage"]["attempt_overruns"] == 1
    with pytest.raises(AdmissionBlocked, match="per-attempt"):
        account.reserve(model="cursor:m", slice_id=task.id, kind="production", identity=None)


def test_otel_close_flushes_owned_provider_once():
    from cld.telemetry import OtelSink
    closed = []
    sink = OtelSink(close_fn=lambda: closed.append(True))
    sink.close(); sink.close()
    assert closed == [True]
