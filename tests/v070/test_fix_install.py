"""v0.7.0 review fix: unregister removes an owned entry even when the bundle is damaged."""
import json
import shutil

import pytest

from tests.v070.test_mcp_install import agy_home, areg, aunreg, codex_scope, reg, unreg


@pytest.mark.parametrize("damage", ["file_removed", "bundle_removed"])
def test_codex_unregister_works_for_a_damaged_install(tmp_path, damage):
    scope = codex_scope(tmp_path / "a")
    assert reg(scope)[0] == 0
    if damage == "file_removed":
        (scope.bundle / "scripts" / "run_delivery.py").unlink()
    else:
        shutil.rmtree(scope.bundle)
    rc, payload = unreg(scope)
    assert rc == 0 and payload.get("outcome") != "error", payload
    assert "cld-mcp owner=" not in scope.config.read_text(encoding="utf-8")


def test_codex_unregister_still_refuses_another_owner(tmp_path):
    scope = codex_scope(tmp_path / "a")
    other = codex_scope(tmp_path / "b")
    assert reg(scope)[0] == 0
    before = scope.config.read_bytes()
    rc, payload = unreg(scope, bundle=other.bundle)
    assert rc == 1 and scope.config.read_bytes() == before, payload


def test_agy_unregister_works_after_the_bundle_is_removed(tmp_path):
    home = agy_home(tmp_path / "a")
    assert areg(home)[0] == 0
    shutil.rmtree(home.bundle)
    rc, payload = aunreg(home)
    assert rc == 0 and payload.get("outcome") != "error", payload
    assert "cld" not in json.loads(home.config.read_text(encoding="utf-8")).get("mcpServers", {})
