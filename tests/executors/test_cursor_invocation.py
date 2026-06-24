import os
from pathlib import Path
from cld_providers.cursor.provider import _cursor_invocation
import cld_providers.cursor.provider as cursor_provider


def test_override_wins(monkeypatch):
    monkeypatch.setenv("CURSOR_AGENT_CMD", "/custom/cursor-agent")
    assert _cursor_invocation() == ["/custom/cursor-agent"]


def test_direct_node_prefix_on_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("CURSOR_AGENT_CMD", raising=False)
    monkeypatch.setattr(os, "name", "nt")
    base = tmp_path / "cursor-agent" / "versions"
    v = base / "2026.06.15"
    v.mkdir(parents=True)
    (v / "index.js").write_text("// entry", encoding="utf-8")
    (v / "node.exe").write_text("", encoding="utf-8")           # bundled node
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    inv = _cursor_invocation()
    assert inv[0].endswith("node.exe")                          # node, not the .cmd shim
    assert inv[1].endswith("index.js")
    assert not any(part.endswith(".cmd") for part in inv)


# ---- TLS-interception fix: bundled node must trust the OS CA store (NODE_OPTIONS) ----
def _capture_env(monkeypatch):
    grabbed = {}

    class _P:
        returncode = 0
        stdout = "{}"
        stderr = ""

    def fake_run(args, **kw):
        grabbed["env"] = kw.get("env")
        return _P()

    monkeypatch.setattr(cursor_provider.subprocess, "run", fake_run)
    return grabbed


def test_bundled_node_gets_use_system_ca(monkeypatch, tmp_path):
    grabbed = _capture_env(monkeypatch)
    node = tmp_path / "cursor-agent" / "versions" / "v" / "node.exe"
    node.parent.mkdir(parents=True)
    node.write_text("", encoding="utf-8")
    cursor_provider._default_runner([str(node), str(node.parent / "index.js"), "-p", "x"], str(tmp_path))
    assert "--use-system-ca" in grabbed["env"].get("NODE_OPTIONS", "")
    assert grabbed["env"]["CURSOR_INVOKED_AS"] == "cursor-agent"


def test_git_and_system_node_do_not_get_use_system_ca(monkeypatch, tmp_path):
    grabbed = _capture_env(monkeypatch)
    # git commands run through the same runner must NOT receive the node flag
    cursor_provider._default_runner(["git", "diff", "HEAD"], str(tmp_path))
    assert "--use-system-ca" not in (grabbed["env"].get("NODE_OPTIONS", "") or "")
    # a bare 'node' fallback (non-absolute, possibly <22) is also skipped
    cursor_provider._default_runner(["node", "index.js"], str(tmp_path))
    assert "--use-system-ca" not in (grabbed["env"].get("NODE_OPTIONS", "") or "")
