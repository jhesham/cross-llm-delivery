"""v0.7.1 INSTCANCEL: cld_cancel in registrations; v0.7.0 entries upgrade on re-register."""
import hashlib
import json
import re
import tomllib

from tests.v070.test_mcp_install import (ALL_TOOLS, OWNER_RE, READ_ONLY, agy_home, areg,
                                         codex_scope, reg, seed)

V070_TOOLS = ["cld_preview", "cld_status", "cld_list_models", "cld_new_build", "cld_step",
              "cld_integrate", "cld_mark_repaired", "cld_job"]
NINE = set(V070_TOOLS) | {"cld_cancel"}


def _server(scope):
    return tomllib.loads(scope.config.read_text(encoding="utf-8"))["mcp_servers"]["cld"]


def test_codex_registration_includes_cancel_without_preapproval(tmp_path):
    scope = codex_scope(tmp_path / "a")
    rc, payload = reg(scope)
    assert rc == 0, payload
    server = _server(scope)
    assert set(server["enabled_tools"]) == NINE, server["enabled_tools"]
    assert server.get("tools", {}).get("cld_cancel", {}).get("approval_mode") != "approve"
    for name in READ_ONLY:
        assert server["tools"][name]["approval_mode"] == "approve"


def _as_v070_entry(scope):
    """Rewrite the owned block as a genuine v0.7.0 eight-tool entry (valid owner hash)."""
    from generator.install_codex import _BLOCK
    text = scope.config.read_text(encoding="utf-8")
    block = _BLOCK.search(text)
    assert block, text
    body = block.group(3)
    eight = "enabled_tools = [" + ", ".join(f'"{name}"' for name in V070_TOOLS) + "]"
    old_body = re.sub(r"(?m)^enabled_tools = \[.*\]$", eight, body)
    assert old_body != body
    digest = hashlib.sha256(old_body.encode("utf-8")).hexdigest()
    old_block = block.group(0).replace(body, old_body).replace(block.group(2), digest)
    seed(scope.config, text[:block.start()] + old_block + text[block.end():])
    assert set(_server(scope)["enabled_tools"]) == set(V070_TOOLS)


def test_v070_registration_upgrades_on_re_register(tmp_path):
    scope = codex_scope(tmp_path / "a")
    assert reg(scope)[0] == 0
    _as_v070_entry(scope)
    rc, payload = reg(scope)
    assert rc == 0 and payload.get("outcome") != "error", payload
    text = scope.config.read_text(encoding="utf-8")
    assert len(OWNER_RE.findall(text)) == 1
    assert set(_server(scope)["enabled_tools"]) == NINE


def test_edited_entries_are_still_refused(tmp_path):
    scope = codex_scope(tmp_path / "a")
    assert reg(scope)[0] == 0
    text = scope.config.read_text(encoding="utf-8").replace('"cld_job"]', '"cld_job", "extra"]')
    before = seed(scope.config, text)
    rc, payload = reg(scope)
    assert rc == 1 and scope.config.read_bytes() == before, payload


def test_antigravity_allow_rules_include_cancel(tmp_path):
    home = agy_home(tmp_path / "a")
    rc, payload = areg(home)
    assert rc == 0, payload
    assert "mcp(cld/cld_cancel)" in json.dumps(payload)


def test_v070_suite_constant_is_migrated():
    assert set(ALL_TOOLS) == NINE, "tests/v070 must pin the nine-tool registration"
