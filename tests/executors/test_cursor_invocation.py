import os
from pathlib import Path
from cld_providers.cursor.provider import _cursor_invocation


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
