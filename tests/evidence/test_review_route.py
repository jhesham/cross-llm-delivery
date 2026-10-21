"""v0.5 review fixes (ROUTE2): evidence slices can be retried, and reconcile keeps their acceptance."""
from cld.executors.base import ExecutorResult
from cld.integration import integrate
from cld.ledger import Ledger
from tests.evidence.test_plan_routing import (Factory, SPEC, _c, _q, _repo, _run, acceptance,
                                              real_git_runner)


class NoBundle:
    def run_evidence(self, prompt, workdir):
        return ExecutorResult(ok=True, diff="", raw_log="no evidence.json written", process={})


def test_incomplete_evidence_slice_can_be_retried(tmp_path):
    repo = _repo(tmp_path)
    ledger = Ledger(str(tmp_path / "ledger.json"))
    first, ledger = _run(repo, tmp_path, [_q()], Factory(evidence_executor=NoBundle()), ledger=ledger)
    assert ledger.get("Q").status != "integrated" and ledger.get("Q").status != "needs_repair"
    second, ledger = _run(repo, tmp_path, [_q()], Factory(), ledger=ledger)
    assert ledger.get("Q").status == "integrated", second


def test_reconcile_keeps_commit_free_evidence_slices_integrated(tmp_path):
    repo, factory = _repo(tmp_path), Factory()
    ledger = Ledger(str(tmp_path / "ledger.json"))
    _run(repo, tmp_path, [_q()], factory, plan=[_q()], ledger=ledger)
    assert ledger.get("Q").status == "integrated"
    plan = [_q(), _c(deps=["Q"])]
    with ledger.writer(refresh=True):
        ledger.bind(repo, plan, real_git_runner, reconcile=True)
    assert ledger.get("Q").status == "integrated" and ledger.get("Q").commit is None
    result, ledger = _run(repo, tmp_path, [plan[1]], factory, plan=plan, ledger=ledger)
    assert not (result.failed or result.blocked or result.needs_repair), result
    with ledger.writer(refresh=True):
        merged = integrate(plan, ledger, repo_dir=repo, git_runner=real_git_runner,
                           test_runner=acceptance, selector="test_c.py")
    assert merged.passed, merged.error
