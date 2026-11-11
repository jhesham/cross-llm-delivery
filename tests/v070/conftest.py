"""v0.7.0 shared fixtures. Fixtures never resolve not-yet-existing modules."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.v070 import _stubs

ROOT = Path(__file__).resolve().parents[2]

_SCRUB = ("CLD_EXECUTOR_DEPTH", "CLD_STUB_MODE", "CLD_STUB_SECONDS", "CLD_STUB_MARKER",
          "CLD_STUB_CHILD", "CLD_MCP_FAULT", "CLD_MCP_PAUSE_AFTER_CHECKS",
          "CLD_PROCESS_REGISTRY", "CLD_DRIVER", "CLD_MODELS", "CLD_HOST", "CLD_MCP_JOBS",
          "CLD_MCP_SYNC_TIMEOUT", "CLD_MCP_TESTING")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Acceptance runs inside a CLD executor, which sets CLD_EXECUTOR_DEPTH.
    for name in _SCRUB:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def jobs_root(tmp_path, monkeypatch):
    """A resolved jobs root in CLD_MCP_JOBS, test faults enabled; reaps leftovers."""
    root = (tmp_path / "jobs").resolve()
    monkeypatch.setenv("CLD_MCP_JOBS", str(root))
    monkeypatch.setenv("CLD_MCP_TESTING", "1")
    yield root
    if root.is_dir():
        for job_dir in root.iterdir():
            if job_dir.is_dir():
                _stubs.reap_job_dir(job_dir)
    for pid_file in tmp_path.rglob("*.pid*"):
        try:
            _stubs.kill_tree(int(pid_file.read_text().strip()))
        except (OSError, ValueError):
            pass


@pytest.fixture
def entry_shim(tmp_path):
    """Same contract as scripts/cld_mcp.py --run-job, bootstrapping the candidate engine."""
    shim = tmp_path / "shim" / "cld_mcp.py"
    shim.parent.mkdir()
    shim.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'engine')!r})\n"
        "if sys.argv[1:2] == ['--run-job']:\n"
        "    from cld.mcp_jobs import run_job\n"
        "    sys.exit(run_job(sys.argv[2]))\n"
        "sys.exit(2)\n",
        encoding="utf-8")
    return shim


@pytest.fixture
def stub_env(tmp_path, monkeypatch, jobs_root):
    """Stub driver and picker via CLD_DRIVER / CLD_MODELS, host and short sync timeout."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    driver = _stubs.write_wrapper(stubs / "driver.py", "driver_main")
    picker = _stubs.write_wrapper(stubs / "picker.py", "picker_main")
    monkeypatch.setenv("CLD_DRIVER", str(driver))
    monkeypatch.setenv("CLD_MODELS", str(picker))
    monkeypatch.setenv("CLD_HOST", "test-host")
    monkeypatch.setenv("CLD_MCP_SYNC_TIMEOUT", "20")
    scripts = tmp_path / "scripts-dir"
    scripts.mkdir()
    return SimpleNamespace(driver=driver, picker=picker, marker=tmp_path / "marker.json",
                           scripts=scripts, jobs=jobs_root, host="test-host")


@pytest.fixture
def repo(tmp_path):
    """A committed Git repository with a one-slice plan (absolute paths)."""
    return _stubs.git_repo(tmp_path / "repo")


@pytest.fixture
def python():
    return sys.executable
