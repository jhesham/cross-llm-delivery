"""v0.5.2 PROBE: the validation probe repo is self-contained; a parent pytest.ini or conftest.py cannot affect it."""
from cld.executors.base import ExecutorResult


class Passing:
    def run(self, task, workdir, feedback=None):
        from pathlib import Path
        (Path(workdir) / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        from cld.cli import git_runner
        from cld.executors._capture import capture_diff
        diff, files = capture_diff(git_runner, str(workdir))
        return ExecutorResult(ok=True, diff=diff, files_changed=files, raw_log="ok", process={})


def test_parent_pytest_config_does_not_reach_the_probe(tmp_path):
    from cld.cli import git_runner
    from cld.validate import validate_model
    parent = tmp_path / "target-repo"
    parent.mkdir()
    (parent / "pytest.ini").write_text("[pytest]\naddopts = -p no_such_plugin_cld_probe\n", encoding="utf-8")
    (parent / "conftest.py").write_text("raise RuntimeError('parent conftest must not load')\n", encoding="utf-8")
    result = validate_model("gpt-example", executor=Passing(), git_runner=git_runner,
                            base_dir=str(parent / ".cld" / "runs" / "v" / "validation"))
    assert result.status == "verified", (result.status, result.note)


def test_probe_repo_has_its_own_pytest_config(tmp_path):
    from cld.cli import git_runner
    from cld.validate import validate_model
    validate_model("gpt-example", executor=Passing(), git_runner=git_runner, base_dir=str(tmp_path / "v"))
    configs = list((tmp_path / "v").rglob("repo/pytest.ini"))
    assert configs, "probe repo has no pytest.ini"
