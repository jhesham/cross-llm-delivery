"""Explicit Codex fast-tier contracts; synthetic processes, real Git, no inference."""
import json
import os
import subprocess
import sys

import pytest

from cld import cli
from cld.models import resolve_spec
from cld_providers.codex.contract import build_invocation, CodexContractError, parse_exec_output
from cld_providers.codex.provider import CodexExecutor
from generator.build_skill import build_one
from tests.test_t09_admission import gate
from tests.test_t16_codex_adapter import FakeCodexRunner, FakeProcess, FIXTURE, repo, task


FAST = "codex:gpt-6-luna@max+fast"
NORMAL = "codex:gpt-6-luna@max"


@pytest.mark.parametrize("spec", [FAST, "codex/gpt-6-luna@max+fast", " codex:gpt-6-luna@max+fast "])
def test_both_parsers_preserve_exact_effort_and_tier(spec):
    expected = {"model": "gpt-6-luna", "effort": "max", "service_tier": "fast"}
    assert resolve_spec(spec) == (FAST, "codex", expected)
    assert cli.parse_executor_spec(spec) == ("codex", expected)


@pytest.mark.parametrize("spec", ["codex:gpt-6-luna@max+fasst", "codex:gpt-6-luna@max+",
    "codex:gpt-6-luna@+fast", "codex:gpt-6-luna@max+fast+fast",
    "opencode:opencode/kimi-k3@max+fast", "cursor:model@high+fast", "codex:gpt-6-luna@"])
def test_invalid_suffixes_fail_before_factory(spec):
    for parser in (resolve_spec, cli.parse_executor_spec):
        with pytest.raises(ValueError):
            parser(spec)


def test_admission_never_reuses_normal_evidence_for_fast(tmp_path):
    admission, calls = gate(tmp_path)
    assert admission.check(NORMAL).proceeded
    assert admission.check(FAST).proceeded
    assert calls == [NORMAL, FAST]
    resumed, resumed_calls = gate(tmp_path, policy="deny")
    assert resumed.check(FAST).proceeded and not resumed_calls
    assert admission.store.get(NORMAL) and admission.store.get(FAST)


def test_separate_config_arguments_pin_luna_max_fast(repo):
    call = build_invocation("gpt-6-luna", repo, "Implement one slice", effort="max", service_tier="fast")
    assert call.argv[call.argv.index("--model") + 1] == "gpt-6-luna"
    configs = [call.argv[i + 1] for i, arg in enumerate(call.argv) if arg == "--config"]
    assert configs == ['model_reasoning_effort="max"', 'service_tier="fast"']
    normal = build_invocation("gpt-6-luna", repo, "Implement one slice", effort="max")
    assert not any("service_tier" in arg for arg in normal.argv)


@pytest.mark.parametrize("tier", ["fasst", "priority", "fast\n", "default", ""])
def test_adapter_rejects_unknown_tiers_before_any_process(repo, tier):
    runner = FakeCodexRunner()
    result = CodexExecutor(model="gpt-6-luna", service_tier=tier, runner=runner).run(task(), repo)
    assert not result.ok and result.process["error"] == "invalid_invocation"
    assert not runner.calls
    with pytest.raises(CodexContractError):
        build_invocation("gpt-6-luna", repo, "task", service_tier=tier)


@pytest.mark.parametrize("event,stderr", [
    ({"type": "warning", "message": "Service tier fast not supported; ignoring"}, ""),
    ({"type": "config.warning", "message": "Unknown configuration override"}, ""),
    ({"type": "item.completed", "item": {"type": "warning", "message": "Fast mode unavailable"}}, ""),
    (None, "WARNING: model does not support service_tier fast; ignoring"),
    (None, "WARNING: Fast mode not supported for this model"),
])
def test_zero_exit_warning_never_captures_partial_diff(repo, event, stderr):
    stream = FIXTURE.read_text(encoding="utf-8")
    if event:
        stream += json.dumps(event) + "\n"
    runner = FakeCodexRunner(exec_result=FakeProcess(stdout=stream, stderr=stderr),
        write=lambda cwd: (cwd / "value.py").write_text("VALUE = 2\n", encoding="utf-8"))
    def forbidden_capture(*args, **kwargs):
        pytest.fail("tier fallback must never reach Git capture")
    result = CodexExecutor(model="gpt-6-luna", effort="max", service_tier="fast",
        runner=runner, git_runner=forbidden_capture).run(task(), repo)
    assert not result.ok and result.diff == "" and result.files_changed == []
    assert result.process["error"] == "service_tier_warning"
    assert (repo / "value.py").read_text() == "VALUE = 2\n"


@pytest.mark.parametrize("observed,ok", [("fast", True), ("priority", True), ("default", False), (None, False)])
def test_reported_tier_never_silently_downgrades(observed, ok):
    events = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines()]
    events[-1]["service_tier"] = observed
    result = parse_exec_output("\n".join(map(json.dumps, events)), "", 0, service_tier="fast")
    assert result.ok is ok
    if not ok:
        assert result.error == "service_tier_mismatch"


def test_model_prose_is_not_a_tier_warning():
    stream = FIXTURE.read_text(encoding="utf-8") + json.dumps({
        "type": "item.completed", "item": {"type": "agent_message", "text": "Fast mode is not supported"}})
    assert parse_exec_output(stream, "", 0, service_tier="fast").ok
    # Without an explicit tier, retain the old warning behavior.
    stream += "\n" + json.dumps({"type": "warning", "message": "An unrelated warning"})
    assert parse_exec_output(stream, "", 0).ok


def test_max_fast_supports_explicit_longer_deadline_without_extending_probes(repo, monkeypatch):
    monkeypatch.setenv("CLD_DISPATCH_TIMEOUT", "1200")
    monkeypatch.setenv("CLD_PROBE_TIMEOUT", "30")
    runner = FakeCodexRunner()
    result = CodexExecutor(model="gpt-6-luna", effort="max", service_tier="fast", runner=runner).run(task(), repo)
    assert result.ok
    assert [call[2]["timeout"] for call in runner.calls] == [30, 30, 1200]
    assert 'service_tier="fast"' in runner.calls[-1][0]


@pytest.mark.parametrize("host", ["claude-code", "codex"])
def test_isolated_bundle_supports_fast_without_repo_imports(tmp_path, host):
    bundle = build_one("codex", out_root=tmp_path / "bundles", host=host)
    script = (
        "from cld.models import resolve_spec; from cld.cli import build_executor_factory; "
        f"s={FAST!r}; assert resolve_spec(s)[2]['service_tier']=='fast'; "
        "e=build_executor_factory()(s); assert e._service_tier=='fast' and e._effort=='max'"
    )
    env = {**os.environ, "PYTHONPATH": str(bundle / "scripts")}
    proc = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stdout + proc.stderr
