"""v0.5 Task 12: plan-mode routing — investigate in worktrees, query/materialise through ask mode.

Evidence slices (query/materialise) produce no commit: a complete bundle records the slice as
integrated with its evidence_dir; needs_approval leaves it resumable; dependants still run, and
integration merges only commit-bearing slices."""
import json
import subprocess
import sys
from pathlib import Path

from cld.executors.base import ExecutorResult, SliceTask
from cld.integration import integrate
from cld.judge import judge
from cld.ledger import Ledger
from cld.orchestrator import run_plan_parallel
from tests.evidence.test_ask import FakeEvidenceExecutor
from tests.evidence.test_materialise import FakeMaterialiser
from tests.integration.harness import init_repo, real_git_runner

SPEC = "codex:gpt-example@low"


def acceptance(workdir, path):
    from cld.test_run import TestRun
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", path],
                          cwd=workdir, capture_output=True, text=True)
    return TestRun(returncode=proc.returncode, output=proc.stdout + proc.stderr)


def _repo(tmp_path):
    repo = init_repo(tmp_path / "repo")
    Path(repo, "cld-environments.json").write_text(json.dumps({"environments": [
        {"name": "warehouse_sandbox", "class": "sandbox", "platform": "bigquery",
         "command": ["bq", "query"], "read_only_expected": False}]}), encoding="utf-8")
    # Fixture tests fail at baseline by assertion only (CLD's red-baseline rule).
    Path(repo, "test_c.py").write_text(
        "import importlib.util\n\n\ndef test_c():\n"
        "    assert importlib.util.find_spec('value') is not None, 'value.py missing'\n"
        "    from value import VALUE\n    assert VALUE == 42\n")
    Path(repo, "test_kb.py").write_text(
        "from pathlib import Path\n\n\ndef test_kb():\n"
        "    path = Path('knowledge/svc.md')\n"
        "    assert path.is_file(), 'module missing'\n"
        "    assert path.read_text().startswith('> Verified:')\n")
    for args in (["git", "add", "-A"], ["git", "commit", "-qm", "fixtures"]):
        assert real_git_runner(args, repo)[0] == 0
    return repo


class CodeWriter:
    def __init__(self, text="VALUE = 42\n"):
        self.text, self.calls = text, 0

    def run(self, task, workdir, feedback=None):
        self.calls += 1
        for name in task.files:
            path = Path(workdir) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.text, encoding="utf-8")
        return ExecutorResult(True, "", token_usage={"total": 0, "cost": 0}, raw_log="fixture")


class Factory:
    def __init__(self, evidence_executor=None, code_executor=None):
        self.evidence_executor = evidence_executor or FakeEvidenceExecutor()
        self.code_executor = code_executor or CodeWriter()
        self.calls = []

    def __call__(self, spec, evidence=False):
        self.calls.append((spec, evidence))
        return self.evidence_executor if evidence else self.code_executor


def _slice(*args, **kw):
    error = None
    try:
        return SliceTask(*args, **kw)
    except TypeError as exc:
        error = str(exc)
    assert error is None, f"SliceTask evidence fields not supported: {error}"


def _q():
    return _slice("Q", "Count orders per day.", [], "", kind="query", environments=["warehouse_sandbox"])


def _m():
    return _slice("M", "Create the daily table.", [], "", kind="materialise", environments=["warehouse_sandbox"])


def _c(deps=()):
    return SliceTask("C", "Set VALUE to 42.", ["value.py"], "test_c.py", deps=list(deps))


def _run(repo, tmp_path, slices, factory, plan=None, spec=SPEC, ledger=None):
    ledger = ledger or Ledger(str(tmp_path / "ledger.json"))
    result = run_plan_parallel(slices, ledger, plan_slices=plan or slices, executor_factory=factory,
                               default_spec=spec, judge_fn=judge, max_workers=1, max_retries=0,
                               repo_dir=repo, git_runner=real_git_runner, test_runner=acceptance)
    return result, ledger


def test_query_slice_runs_via_ask_and_is_integrated_without_commit(tmp_path):
    repo, factory = _repo(tmp_path), Factory()
    result, ledger = _run(repo, tmp_path, [_q()], factory)
    entry = ledger.get("Q")
    assert entry.status == "integrated" and entry.commit is None
    assert getattr(entry, "evidence_dir", None) and Path(entry.evidence_dir).is_dir()
    assert factory.calls == [(SPEC, True)] and "Q" in result.completed


def test_materialise_needs_approval_is_resumable(tmp_path):
    repo = _repo(tmp_path)
    factory = Factory(evidence_executor=FakeMaterialiser(runner_status="needs_approval"))
    result, ledger = _run(repo, tmp_path, [_m()], factory)
    assert ledger.get("M").status == "pending" and "M" in result.deferred


def test_incomplete_bundle_fails_for_retry(tmp_path):
    class NoBundle:
        def run_evidence(self, prompt, workdir):
            return ExecutorResult(ok=True, diff="", raw_log="no evidence.json written", process={})

    repo = _repo(tmp_path)
    result, ledger = _run(repo, tmp_path, [_q()], Factory(evidence_executor=NoBundle()))
    # No worktree or commit exists to repair; the slice fails and the next step retries it.
    assert ledger.get("Q").status == "failed" and "Q" in result.failed


def test_code_slice_after_evidence_dependency_and_integration(tmp_path):
    repo, factory = _repo(tmp_path), Factory()
    plan = [_q(), _c(deps=["Q"])]
    ledger = Ledger(str(tmp_path / "ledger.json"))
    for layer in ([plan[0]], [plan[1]]):
        result, ledger = _run(repo, tmp_path, layer, factory, plan=plan, ledger=ledger)
        assert not (result.failed or result.blocked or result.needs_repair), result
    assert ledger.get("C").status == "done" and ledger.get("C").commit
    with ledger.writer(refresh=True):
        merged = integrate(plan, ledger, repo_dir=repo, git_runner=real_git_runner,
                           test_runner=acceptance, selector="test_c.py")
    assert merged.passed, merged.error
    assert ledger.get("Q").status == "integrated" and ledger.get("C").status == "integrated"


def test_investigate_slice_uses_evidence_executor_and_worktree(tmp_path):
    repo = _repo(tmp_path)
    factory = Factory(evidence_executor=CodeWriter("> Verified: 2026-10-21 against example-org/service-a@main\n"))
    task = _slice("I", "Map service-a.", ["knowledge/svc.md"], "test_kb.py", kind="investigate")
    result, ledger = _run(repo, tmp_path, [task], factory)
    assert factory.calls == [(SPEC, True)]
    assert ledger.get("I").status == "done" and ledger.get("I").commit


def test_code_slices_unchanged(tmp_path):
    _slice("X", "probe", [], "", kind="code")  # red until the plan fields exist
    repo, factory = _repo(tmp_path), Factory()
    result, ledger = _run(repo, tmp_path, [_c()], factory)
    assert factory.calls == [(SPEC, False)]
    assert ledger.get("C").status == "done"


def test_unsupported_provider_blocks_evidence_slice_before_dispatch(tmp_path):
    repo, factory = _repo(tmp_path), Factory()
    result, ledger = _run(repo, tmp_path, [_q()], factory, spec="opencode:example/model")
    assert factory.evidence_executor.prompts == [] and ledger.get("Q").status != "integrated"
    assert "Q" in (result.blocked + result.deferred + result.failed)
