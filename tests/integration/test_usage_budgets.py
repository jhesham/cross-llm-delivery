"""T10 accounting through real candidate/retry/escalation boundaries, no model calls."""
import json
from pathlib import Path

from cld.accounting import Accounting
from cld.executors.base import ExecutorResult
from cld.ledger import Ledger
from cld.status import render_accounting_status
from tests.integration.harness import real_git_runner
from tests.integration.test_review_regressions import BODY, delivery_repo, run, task


def test_two_failed_attempts_then_escalation_success_records_every_call(delivery_repo):
    class Improving:
        calls = 0
        def run(self, task, wd, feedback=None):
            self.calls += 1
            (Path(wd) / "implementation.py").write_text(BODY if self.calls == 3 else "VALUE = 1\n")
            return ExecutorResult(True, "", token_usage={"input": 8, "output": 2, "cost": .1})
    executor = Improving()
    result = run(delivery_repo, executor=executor,
        rung_planner=lambda t: [("quick", "fake:small", 2), ("premium", "fake:large@high", 1)])
    assert result.completed == ["A"] and executor.calls == 3, result.details
    ledger = Ledger.load(str(delivery_repo / ".cld-ledger.json"))
    assert ledger.get("A").attempts == 3
    assert ledger.get("A").token_usage["total"] == 30
    assert abs(ledger.get("A").cost - .3) < 1e-9
    assert ledger.build["usage"]["by_model"]["fake:small"]["total"] == 20
    assert "tokens: 30" in render_accounting_status(ledger)
    records = [json.loads(p.read_text()) for p in (delivery_repo / ".cld").glob("runs/*/usage/attempt-*.json")]
    assert len(records) == 3
    assert any(r["dispatch"]["attempt"] == 2 and "Failing tests" in r["dispatch"]["reason"] for r in records)
    assert any(r["dispatch"]["source"] == "escalated" and r["effort"] == "high" for r in records)


def test_budget_block_keeps_candidate_and_does_not_escalate(delivery_repo):
    ledger = Ledger(str(delivery_repo / ".cld-ledger.json"))
    class Failed:
        calls = 0
        def run(self, task, wd, feedback=None):
            self.calls += 1
            (Path(wd) / "implementation.py").write_text("VALUE = 1\n")
            return ExecutorResult(True, "", token_usage={"total": 10})
    ex = Failed()
    with ledger.writer():
        ledger.bind(str(delivery_repo), [task()], real_git_runner)
        account = Accounting(ledger, {"attempts": 1})
        result = run(delivery_repo, ledger=ledger, executor=ex, accounting=account,
            rung_planner=lambda t: [("quick", "fake:small", 2), ("premium", "fake:large", 1)])
    assert result.blocked == ["A"] and ex.calls == 1, result.details
    assert not result.needs_repair and not result.completed
    assert any("+VALUE = 1" in p.read_text(encoding="utf-8") for p in (delivery_repo / ".cld").rglob("*.patch"))
    assert ledger.get("A").attempts == 1 and ledger.get("A").token_usage["total"] == 10
    assert "budget blocked" in render_accounting_status(ledger)


def test_validation_spend_consumes_same_production_budget(delivery_repo):
    from cld.validate import validate_model
    ledger = Ledger(str(delivery_repo / ".cld-ledger.json"))
    class Probe:
        def run(self, task, wd):
            (Path(wd) / "calc.py").write_text("def add(a,b): return a+b\n")
            return ExecutorResult(True, "", token_usage={"total": 12, "cost": .1})
    class Production:
        def run(self, *args, **kwargs):
            raise AssertionError("production must be blocked before invocation")
    with ledger.writer():
        ledger.bind(str(delivery_repo), [task()], real_git_runner)
        account = Accounting(ledger, {"attempts": 1})
        result = validate_model("fake:probe", executor=account.wrap(Probe(), "fake:probe", kind="validation"),
            git_runner=real_git_runner, base_dir=str(delivery_repo / ".cld" / "probes"))
        assert result.passed
        production = run(delivery_repo, ledger=ledger, executor=Production(), accounting=account)
    assert production.blocked == ["A"]
    assert ledger.build["usage"]["validation"]["total"] == 12
    assert ledger.build["usage"]["total"] == 12
