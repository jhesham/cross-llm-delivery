"""v0.5.1 review (VALSTATE): a validation probe's recovery record never stays "running"."""
import json

from cld.executors.base import ExecutorResult


class Failing:
    def run(self, task, workdir, feedback=None):
        return ExecutorResult(ok=False, diff="", raw_log="denied", process={"error": "authentication"})


class Passing:
    def run(self, task, workdir, feedback=None):
        (workdir / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        from cld.executors._capture import capture_diff
        from cld.cli import git_runner
        diff, files = capture_diff(git_runner, str(workdir))
        return ExecutorResult(ok=True, diff=diff, files_changed=files, raw_log="ok", process={})


def _states(base):
    return [json.loads(p.read_text(encoding="utf-8")).get("state") for p in base.rglob("outcome.json")]


def _validate(tmp_path, executor):
    from cld.cli import git_runner
    from cld.validate import validate_model
    return validate_model("gpt-example", executor=executor, git_runner=git_runner, base_dir=str(tmp_path / "v"))


def test_failed_dispatch_leaves_a_terminal_state(tmp_path):
    result = _validate(tmp_path, Failing())
    states = _states(tmp_path / "v")
    assert result.status == "untested" and states and "running" not in states, states


def test_passing_probe_leaves_a_terminal_state(tmp_path):
    _validate(tmp_path, Passing())
    states = _states(tmp_path / "v")
    assert states and "running" not in states, states
