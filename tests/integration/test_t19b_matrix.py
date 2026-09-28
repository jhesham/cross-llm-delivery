"""Eight independently loaded host/provider bundles with fixture replay."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from generator.build_skill import build_one
from tests.integration.harness import init_repo
from tests.integration.test_review_regressions import checked_git

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.integration


@pytest.mark.parametrize("host", ["codex", "claude-code"])
@pytest.mark.parametrize("provider", ["antigravity", "opencode", "cursor", "codex"])
def test_recorded_fixtures_in_isolated_host_bundle(tmp_path, host, provider):
    bundle = build_one(provider, out_root=tmp_path / "bundles", host=host, smoke=False)
    repo = Path(init_repo(tmp_path / "fixture repo with spaces"))
    (repo / "value.py").write_text("VALUE = 0\n")
    (repo / "test_value.py").write_text("def test_value(): pass\n")
    checked_git(["add", "."], repo)
    checked_git(["commit", "-qm", "fixture baseline"], repo)
    env = {**os.environ, "PYTHONPATH": str(bundle / "scripts"), "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("CLD_EXECUTOR_DEPTH", None)
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("t19_bundle_probe.py")),
        str(bundle), provider, str(repo), str(ROOT / "tests/fixtures")], cwd=tmp_path,
        env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["offline"]


def test_kimi_evidence_matrix_contract():
    text = (ROOT / "docs/plans/codex-support/T19B-MATRIX.md").read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| ") and "offline" in line]
    assert len(rows) == 8
    for host in ("codex", "claude-code"):
        for provider in ("antigravity", "opencode", "cursor", "codex"):
            assert f"| {host} | {provider} | offline |" in text
    assert "Windows only" in text and "unverified" in text
    assert "T14-EVIDENCE.md" in text and "T16-EVIDENCE.md" in text
    assert "825,553" in text and "lower bound" in text
