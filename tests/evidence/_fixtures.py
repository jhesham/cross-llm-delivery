"""Shared offline fixtures for evidence-mode tests (neutral names only)."""
import re
import json
import sys

from tests.evidence._lazy import resolve


def environment(name="warehouse_sandbox", cls="sandbox", command=None, mcp_only=False, job_id_pattern=None):
    Environment = resolve("cld.evidence_mode.environments", "Environment")
    return Environment(name=name, cls=cls, platform="bigquery",
                       command=tuple(command or ("bq", "query", "--format=json")),
                       read_only_expected=(cls == "real"), mcp_only=mcp_only,
                       job_id_pattern=job_id_pattern)


def write_environments(repo, entries):
    (repo / "cld-environments.json").write_text(json.dumps({"environments": entries}), encoding="utf-8")


def echo_json_command(rows):
    """A real command that reads SQL on stdin and prints a JSON array of `rows` objects."""
    script = f"import sys,json; sys.stdin.read(); print(json.dumps([{{'n': i}} for i in range({rows})]))"
    return [sys.executable, "-c", script]


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr="", error=None, elapsed=0.25):
        self.returncode, self._out, self._err, self.error, self.elapsed = returncode, stdout, stderr, error, elapsed

    @property
    def stdout(self):
        return self._out

    @property
    def stderr(self):
        return self._err


class FakeRunner:
    def __init__(self, result=None, raises=None):
        self.result, self.raises, self.calls = result or FakeResult(stdout='[{"n": 1}, {"n": 2}]'), raises, []

    def __call__(self, argv, cwd, **kwargs):
        self.calls.append((list(argv), kwargs))
        if self.raises:
            raise self.raises
        return self.result

def prompt_task_id(prompt):
    """The task id the ask prompt names, as a real executor would read it."""
    match = re.search(r"^Task name: (\S+)$", prompt, re.M)
    return match.group(1) if match else "t"
