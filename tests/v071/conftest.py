"""v0.7.1 fixtures: reuse the v0.7.0 fixtures, scrub cancel variables, reset the flag.

Fixtures never resolve not-yet-existing modules.
"""
import sys

import pytest

from tests.v070.conftest import _clean_env, entry_shim, jobs_root, python, repo, stub_env  # noqa: F401
from tests.v070 import _stubs

TERMINAL = _stubs.TERMINAL | {"cancelled", "cancel_unconfirmed"}
ACTIVE = {"running", "cancelling"}


@pytest.fixture(autouse=True)
def _clean_cancel(monkeypatch):
    for name in ("CLD_CANCEL_FILE", "CLD_MCP_CANCEL_GRACE"):
        monkeypatch.delenv(name, raising=False)
    yield
    process = sys.modules.get("cld.process")
    flag = getattr(process, "EXTERNAL_CANCEL", None)
    if flag is not None:
        flag.clear()
