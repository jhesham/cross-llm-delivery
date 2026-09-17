"""Validation probes must obey the same candidate boundary as production."""
import json
from pathlib import Path

import pytest

from cld.executors.base import ExecutorResult
from cld.validate import validate_model
from tests.integration.harness import real_git_runner


@pytest.mark.parametrize("mode", ["pass", "tamper", "committed_tamper", "dispatch_failure", "cancelled", "noop"])
def test_validation_uses_actual_candidate_and_retains_all_outcomes(tmp_path, mode):
    visited = []
    class Executor:
        def run(self, task, cwd):
            cwd = Path(cwd); visited.append(cwd)
            if mode != "noop":
                (cwd / "calc.py").write_text("def add(a,b): return a+b\n", encoding="utf-8")
            if "tamper" in mode:
                (cwd / "test_calc.py").write_text("def test_fake(): pass\n", encoding="utf-8")
                if mode == "committed_tamper":
                    assert real_git_runner(["git", "add", "-A"], str(cwd))[0] == 0
                    assert real_git_runner(["git", "commit", "-qm", "fake proof"], str(cwd))[0] == 0
            if mode == "cancelled":
                raise KeyboardInterrupt()
            return ExecutorResult(mode != "dispatch_failure", "", [], {"input": 23}, "1 passed",
                {"error": "authentication"} if mode == "dispatch_failure" else {})
    if mode == "cancelled":
        with pytest.raises(KeyboardInterrupt):
            validate_model("fake", executor=Executor(), git_runner=real_git_runner, base_dir=str(tmp_path))
        result = json.loads(next(tmp_path.rglob("validation.json")).read_text())
        assert result["attempts"] == 1 and not result["passed"]
    else:
        result = validate_model("fake", executor=Executor(), git_runner=real_git_runner, base_dir=str(tmp_path))
        assert result.passed is (mode == "pass")
        assert result.status == ("verified" if mode == "pass" else "untested" if mode == "dispatch_failure" else "revalidate")
        assert result.usage == {"input": 23}
        assert Path(result.artifact_path, "validation.json").exists()
    assert len(visited) == 1 and visited[0].exists()
    assert list(tmp_path.rglob("*.patch"))  # Partial edits and tested candidates remain inspectable.


def test_each_validation_starts_with_its_own_failing_baseline(tmp_path):
    visited = []
    class Executor:
        def run(self, task, cwd):
            cwd = Path(cwd); visited.append(cwd)
            assert "return None" in (cwd / "calc.py").read_text()
            (cwd / "calc.py").write_text("def add(a,b): return a+b\n", encoding="utf-8")
            return ExecutorResult(True, "")
    for _ in range(2):
        assert validate_model("fake", executor=Executor(), git_runner=real_git_runner, base_dir=str(tmp_path)).passed
    assert len(set(visited)) == 2
