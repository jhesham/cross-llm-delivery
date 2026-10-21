"""v0.5 Task 13: knowledge-base starter template (no real content) and the citation check."""
import json
import subprocess
import sys
from pathlib import Path

from cld import cli
from tests.evidence._lazy import resolve

C = "cld.evidence_mode.citations"


def _init(target, capsys):
    code = cli.main(["--init-kb", str(target), "--json"])
    return code, json.loads(capsys.readouterr().out or "{}")


def test_init_kb_copies_template_and_refuses_nonempty(tmp_path, capsys):
    target = tmp_path / "kb"
    code, _ = _init(target, capsys)
    assert code == 0
    for rel in ("knowledge/core.md", "knowledge/freshness.md", "knowledge/references/README.md",
                "knowledge/references/queries/README.md", "tests/test_knowledge_contract.py",
                "tests/test_citations.py"):
        assert (target / rel).is_file(), rel
    code, payload = _init(target, capsys)
    assert code == 5 and "empty" in json.dumps(payload).lower()


def test_template_contract_passes_on_copy(tmp_path, capsys):
    target = tmp_path / "kb"
    assert _init(target, capsys)[0] == 0
    run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "not network",
                          "tests/test_knowledge_contract.py"], cwd=target, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]


def test_template_has_no_real_content(tmp_path, capsys):
    import re
    target = tmp_path / "kb"
    assert _init(target, capsys)[0] == 0
    hosts = set()
    for path in target.rglob("*"):
        if path.is_file():
            hosts |= set(re.findall(r"https?://([A-Za-z0-9.-]+)", path.read_text(encoding="utf-8")))
    assert hosts <= {"git.example.com"}, hosts


class FakeGh:
    def __init__(self, missing=()):
        self.missing, self.calls = set(missing), []

    def __call__(self, argv, cwd):
        self.calls.append(argv)
        path = argv[-1]
        return (1, "404 Not Found") if any(m in path for m in self.missing) else (0, "{}")


TEXT = ("See [x](https://git.example.com/example-org/service-a/blob/main/src/app.py) and "
        "[y](https://git.example.com/example-org/service-a/blob/main/src/missing.py).")
FRESH = {"example-org/service-a": "0123456789ab"}


def test_verify_citations_reports_missing_file():
    gh = FakeGh(missing=("src/missing.py",))
    problems = resolve(C, "verify_citations")(TEXT, FRESH, runner=gh)
    assert len(problems) == 1 and "src/missing.py" in problems[0]
    assert all("ref=0123456789ab" in " ".join(call) for call in gh.calls)
    assert all("--hostname" in call and "git.example.com" in call for call in gh.calls)


def test_verify_citations_requires_freshness_entry():
    problems = resolve(C, "verify_citations")(TEXT, {}, runner=FakeGh())
    assert problems and all("freshness" in p.lower() for p in problems)
