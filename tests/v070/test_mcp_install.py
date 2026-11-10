"""v0.7.0 INSTMCP: --register-mcp / --unregister-mcp for Codex and Antigravity.

The installed bundles are synthetic owned installs created here (with
scripts/cld_mcp.py), so these tests do not depend on GENMCP. Re-registering an
intact entry owned by the same bundle succeeds without a second entry. The JSON
entry's sha256 covers the entry's content (canonical JSON without ``_cld_owner``),
not the file's formatting.
"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.evidence._lazy import resolve
from tests.v070._stubs import WINDOWS, wait_for

ROOT = Path(__file__).resolve().parents[2]
CODEX, AGY = "generator.install_codex", "generator.install_antigravity"
ALL_TOOLS = ["cld_preview", "cld_status", "cld_list_models", "cld_new_build", "cld_step",
             "cld_integrate", "cld_mark_repaired", "cld_job"]
READ_ONLY = ["cld_preview", "cld_status", "cld_list_models", "cld_job"]
MUTATING = ["cld_new_build", "cld_step", "cld_integrate", "cld_mark_repaired"]
OWNER_RE = re.compile(r"^# cld-mcp owner=(.+) sha256=([0-9a-f]{64})\s*$", re.M)


def run(module, *argv):
    """Call an installer's main in-process; exactly one JSON object must be printed."""
    main = resolve(module, "main")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = main([str(a) for a in argv])
    except SystemExit as exc:
        raise AssertionError(f"{module} rejected {argv}: SystemExit({exc.code})") from None
    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1, f"expected one JSON object, got {lines}"
    return rc, json.loads(lines[0])


def spawn(module, *argv, env=None):
    script = ROOT / "generator" / f"{module.rsplit('.', 1)[1]}.py"
    return subprocess.Popen([sys.executable, str(script), *[str(a) for a in argv]],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            cwd=ROOT, env={**os.environ, **(env or {})})


def finish(proc, timeout=60):
    out, err = proc.communicate(timeout=timeout)
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, (out, err)
    return proc.returncode, json.loads(lines[0])


def make_bundle(root, name, *, agy=False):
    bundle = Path(root) / name
    (bundle / "scripts" / "cld").mkdir(parents=True)
    (bundle / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n# t\n",
                                     encoding="utf-8")
    (bundle / "scripts" / "run_delivery.py").write_text("print('driver')\n", encoding="utf-8")
    (bundle / "scripts" / "cld" / "__init__.py").write_text("", encoding="utf-8")
    (bundle / "scripts" / "cld_mcp.py").write_text("print('cld mcp')\n", encoding="utf-8")
    if agy:
        (bundle / "references").mkdir()
        (bundle / "references" / "antigravity-workflow.md").write_text("# w\n", encoding="utf-8")
    return bundle


def _install(module, *argv):
    from importlib import import_module
    with contextlib.redirect_stdout(io.StringIO()):
        assert import_module(module).main([str(a) for a in argv]) == 0, argv


def codex_scope(base, name="cross-llm-delivery"):
    scope = Path(base) / "scope"
    scope.mkdir(parents=True)
    src = make_bundle(Path(base) / "src", name)
    _install(CODEX, "--install", "--scope-root", scope, "--bundle", src)
    skills = scope / ".agents" / "skills"
    return SimpleNamespace(root=scope, bundle=skills / name, config=scope / ".codex" / "config.toml",
                           lock=skills / ".cld-mcp.lock", name=name)


def agy_home(base):
    home = Path(base) / "home"
    home.mkdir(parents=True)
    src = make_bundle(Path(base) / "src", "cross-llm-delivery-agy", agy=True)
    _install(AGY, "--install", "--scope", "user", "--scope-root", home, "--bundle", src)
    skills = home / ".gemini" / "config" / "skills"
    return SimpleNamespace(root=home, bundle=skills / "cross-llm-delivery-agy",
                           config=home / ".gemini" / "config" / "mcp_config.json",
                           lock=skills / ".cld-mcp.lock")


@pytest.fixture
def cx(tmp_path):
    return codex_scope(tmp_path / "a")


@pytest.fixture
def ag(tmp_path):
    return agy_home(tmp_path / "a")


def reg(s, *extra):
    return run(CODEX, "--register-mcp", "--scope-root", s.root, "--bundle", s.bundle, *extra)


def unreg(s, bundle=None):
    return run(CODEX, "--unregister-mcp", "--scope-root", s.root, "--bundle", bundle or s.bundle)


def areg(s, *extra):
    return run(AGY, "--register-mcp", "--scope", "user", "--scope-root", s.root,
               "--bundle", s.bundle, *extra)


def aunreg(s):
    return run(AGY, "--unregister-mcp", "--scope", "user", "--scope-root", s.root,
               "--bundle", s.bundle)


def seed(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path.read_bytes()


def _same(a, b):
    return Path(a).resolve() == Path(b).resolve()


def dir_link(link, target):
    Path(target).mkdir(parents=True, exist_ok=True)
    if WINDOWS:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True,
                       capture_output=True)
    else:
        os.symlink(target, link)


def file_link(link, target):
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("file symlinks unavailable")


# --------------------------------------------------------------------- Codex


@pytest.mark.parametrize("approve", [None, "read-only", "all"])
def test_codex_register_writes_owned_block(cx, approve):
    seed(cx.config, 'model = "x"\n')
    rc, payload = reg(cx, *(["--mcp-approve", approve] if approve else []))
    assert rc == 0 and payload.get("outcome") != "error", payload
    text = cx.config.read_text(encoding="utf-8")
    owner = OWNER_RE.search(text)
    assert owner and _same(owner.group(1), cx.bundle), text
    assert "# end cld-mcp" in text
    config = tomllib.loads(text)
    assert config["model"] == "x"
    server = config["mcp_servers"]["cld"]
    assert Path(server["command"]).is_absolute() and _same(server["command"], sys.executable)
    assert len(server["args"]) == 1 and Path(server["args"][0]).is_absolute()
    assert _same(server["args"][0], cx.bundle / "scripts" / "cld_mcp.py")
    assert server["env"] == {"CLD_HOST": "codex"}
    assert server["enabled_tools"] == ALL_TOOLS
    tools = server.get("tools", {})
    if approve == "all":
        assert server.get("default_tools_approval_mode") == "approve"
    else:
        assert "default_tools_approval_mode" not in server
        for name in READ_ONLY:
            assert tools.get(name, {}).get("approval_mode") == "approve", (name, tools)
        for name in MUTATING:
            assert tools.get(name, {}).get("approval_mode") != "approve", (name, tools)


def test_codex_register_refuses_single_provider_bundle(tmp_path):
    single = codex_scope(tmp_path / "s", name="cross-llm-codex")
    assert (single.bundle / "scripts" / "cld_mcp.py").is_file()
    rc, payload = reg(single)
    assert rc == 1 and payload["outcome"] == "error", payload
    assert not single.config.exists()


def test_codex_preview_writes_nothing(cx):
    rc, payload = run(CODEX, "--preview", "--register-mcp", "--scope-root", cx.root,
                      "--bundle", cx.bundle)
    assert rc == 0 and payload.get("outcome") != "error", payload
    assert not cx.config.exists() and not cx.lock.exists()
    assert reg(cx)[0] == 0
    before = cx.config.read_bytes()
    rc, payload = run(CODEX, "--preview", "--unregister-mcp", "--scope-root", cx.root,
                      "--bundle", cx.bundle)
    assert rc == 0 and payload.get("outcome") != "error", payload
    assert cx.config.read_bytes() == before


@pytest.mark.parametrize("case", ["unowned", "other_owner", "edited"])
def test_codex_refusals_leave_config_byte_identical(tmp_path, cx, case):
    if case == "unowned":
        before = seed(cx.config, '[mcp_servers.cld]\ncommand = "someone-else"\n')
    elif case == "other_owner":
        other = codex_scope(tmp_path / "b")
        assert reg(other)[0] == 0
        before = seed(cx.config, other.config.read_text(encoding="utf-8"))
    else:
        assert reg(cx)[0] == 0
        text, count = re.subn(r'(CLD_HOST\s*=\s*)"codex"', r'\1"edited"',
                              cx.config.read_text(encoding="utf-8"))
        assert count == 1
        before = seed(cx.config, text)
    rc, payload = reg(cx)
    assert rc == 1 and payload["outcome"] == "error", payload
    assert cx.config.read_bytes() == before
    if case != "unowned":
        rc, payload = unreg(cx)
        assert rc == 1 and cx.config.read_bytes() == before, payload


def test_codex_unregister_removes_only_the_block(tmp_path, cx):
    original = seed(cx.config, 'model = "x"\n\n[profiles.p]\nmodel = "y"\n')
    assert reg(cx)[0] == 0
    other = codex_scope(tmp_path / "b")
    registered = cx.config.read_bytes()
    rc, payload = unreg(cx, bundle=other.bundle)
    assert rc == 1 and cx.config.read_bytes() == registered, payload
    rc, payload = unreg(cx)
    assert rc == 0 and payload.get("outcome") != "error", payload
    assert cx.config.read_bytes() == original


def test_codex_write_failure_keeps_original(cx, monkeypatch):
    before = seed(cx.config, 'model = "x"\n')

    def boom(*args, **kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", boom)
    rc, payload = reg(cx)
    monkeypatch.undo()
    assert rc == 1 and payload["outcome"] == "error", payload
    assert cx.config.read_bytes() == before


def test_codex_concurrent_registers_leave_one_entry(cx):
    procs = [spawn(CODEX, "--register-mcp", "--scope-root", cx.root, "--bundle", cx.bundle)
             for _ in range(2)]
    results = [finish(p) for p in procs]
    assert all(rc == 0 for rc, _ in results), results
    text = cx.config.read_text(encoding="utf-8")
    assert len(OWNER_RE.findall(text)) == 1, text
    assert tomllib.loads(text)["mcp_servers"]["cld"]["enabled_tools"] == ALL_TOOLS


def test_codex_concurrent_register_and_unregister(cx):
    procs = [spawn(CODEX, flag, "--scope-root", cx.root, "--bundle", cx.bundle)
             for flag in ("--register-mcp", "--unregister-mcp")]
    results = [finish(p) for p in procs]
    assert results[0][0] == 0, results
    text = cx.config.read_text(encoding="utf-8") if cx.config.exists() else ""
    config = tomllib.loads(text)
    owners = OWNER_RE.findall(text)
    assert len(owners) in (0, 1)
    if owners:
        assert config["mcp_servers"]["cld"]["enabled_tools"] == ALL_TOOLS
    else:
        assert "cld" not in config.get("mcp_servers", {})


def test_codex_linked_config_paths_are_refused(tmp_path, cx):
    real = tmp_path / "elsewhere"
    dir_link(cx.root / ".codex", real)
    rc, payload = reg(cx)
    assert rc == 1 and payload["outcome"] == "error", payload
    assert list(real.iterdir()) == []


def test_codex_linked_config_file_is_refused(tmp_path, cx):
    target = tmp_path / "real.toml"
    before = seed(target, 'model = "x"\n')
    cx.config.parent.mkdir(parents=True)
    file_link(cx.config, target)
    rc, payload = reg(cx)
    assert rc == 1 and payload["outcome"] == "error", payload
    assert target.read_bytes() == before


def test_codex_cross_scope_registration_is_refused(tmp_path, cx):
    other_root = tmp_path / "other-scope"
    other_root.mkdir()
    rc, payload = run(CODEX, "--register-mcp", "--scope-root", other_root, "--bundle", cx.bundle)
    assert rc == 1 and payload["outcome"] == "error", payload
    assert not (other_root / ".codex" / "config.toml").exists()


def test_codex_uninstall_refused_while_registered(cx):
    assert reg(cx)[0] == 0
    before = cx.config.read_bytes()
    rc, payload = run(CODEX, "--uninstall", "--scope-root", cx.root, "--name", cx.name)
    assert rc == 1 and payload["outcome"] == "error", payload
    assert (cx.bundle / "SKILL.md").is_file() and cx.config.read_bytes() == before
    assert unreg(cx)[0] == 0
    rc, payload = run(CODEX, "--uninstall", "--scope-root", cx.root, "--name", cx.name)
    assert rc == 0, payload
    assert not cx.bundle.exists()


def test_codex_register_and_uninstall_cannot_interleave(tmp_path, cx):
    pause = tmp_path / "pause"
    pause.mkdir()
    register = spawn(CODEX, "--register-mcp", "--scope-root", cx.root, "--bundle", cx.bundle,
                     env={"CLD_MCP_TESTING": "1", "CLD_MCP_PAUSE_AFTER_CHECKS": str(pause)})
    paused = wait_for(lambda: (pause / "paused").exists() or register.poll() is not None, 30)
    assert paused and (pause / "paused").exists(), finish(register)
    uninstall = spawn(CODEX, "--uninstall", "--scope-root", cx.root, "--name", cx.name)
    time.sleep(1.5)
    assert uninstall.poll() is None, "uninstall did not wait for the scope lock"
    (pause / "go").write_text("go")
    rc_reg, _ = finish(register)
    rc_un, payload = finish(uninstall)
    assert rc_reg == 0
    config = tomllib.loads(cx.config.read_text(encoding="utf-8")) if cx.config.exists() else {}
    server = config.get("mcp_servers", {}).get("cld")
    if server:
        assert Path(server["args"][0]).is_file(), "registration references a removed bundle"
        assert rc_un == 1, payload


# --------------------------------------------------------------- Antigravity


def _files(root):
    return {p for p in root.rglob("*") if p.is_file()}


def test_agy_register_merges_user_config(ag):
    before_files = _files(ag.root)
    seed(ag.config, json.dumps({"keep": 1, "mcpServers": {"other": {"command": "x", "args": []}}}))
    rc, payload = areg(ag)
    assert rc == 0 and payload.get("outcome") != "error", payload
    assert "mcp(cld/cld_status)" in json.dumps(payload), "allow rules must be reported"
    data = json.loads(ag.config.read_text(encoding="utf-8"))
    assert data["keep"] == 1 and data["mcpServers"]["other"] == {"command": "x", "args": []}
    server = data["mcpServers"]["cld"]
    assert _same(server["command"], sys.executable)
    assert _same(server["args"][0], ag.bundle / "scripts" / "cld_mcp.py")
    assert server["env"] == {"CLD_HOST": "antigravity"}
    owner = server["_cld_owner"]
    assert _same(owner["bundle"], ag.bundle) and re.fullmatch(r"[0-9a-f]{64}", owner["sha256"])
    new = {p for p in _files(ag.root) - before_files
           if p != ag.config and not p.name.endswith(".lock")}
    assert not new, f"unexpected files written: {new}"


def test_agy_workspace_scope_is_refused(tmp_path, ag):
    repo = tmp_path / "repo"
    repo.mkdir()
    rc, payload = run(AGY, "--register-mcp", "--scope", "workspace", "--scope-root", repo,
                      "--bundle", ag.bundle)
    assert rc == 1 and payload["outcome"] == "error", payload
    assert not any(p.name == "mcp_config.json" for p in repo.rglob("*"))


def test_agy_preview_edit_unregister_and_failure_rules(ag, monkeypatch):
    original = {"mcpServers": {"other": {"command": "x"}}}
    seed(ag.config, json.dumps(original))
    before = ag.config.read_bytes()
    rc, payload = run(AGY, "--preview", "--register-mcp", "--scope", "user", "--scope-root",
                      ag.root, "--bundle", ag.bundle)
    assert rc == 0 and payload.get("outcome") != "error", payload
    assert ag.config.read_bytes() == before and not ag.lock.exists()

    def boom(*args, **kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", boom)
    rc, payload = areg(ag)
    monkeypatch.undo()
    assert rc == 1 and ag.config.read_bytes() == before, payload

    assert areg(ag)[0] == 0
    data = json.loads(ag.config.read_text(encoding="utf-8"))
    data["mcpServers"]["cld"]["env"]["CLD_HOST"] = "edited"
    edited = seed(ag.config, json.dumps(data))
    rc, payload = areg(ag)
    assert rc == 1 and ag.config.read_bytes() == edited, payload
    rc, payload = aunreg(ag)
    assert rc == 1 and ag.config.read_bytes() == edited, payload

    data["mcpServers"]["cld"]["env"]["CLD_HOST"] = "antigravity"
    seed(ag.config, json.dumps(data))
    rc, payload = aunreg(ag)
    assert rc == 0, payload
    assert json.loads(ag.config.read_text(encoding="utf-8")) == original


def test_agy_linked_config_file_is_refused(tmp_path, ag):
    target = tmp_path / "real.json"
    before = seed(target, json.dumps({"mcpServers": {}}))
    file_link(ag.config, target)
    rc, payload = areg(ag)
    assert rc == 1 and payload["outcome"] == "error", payload
    assert target.read_bytes() == before


def test_agy_uninstall_refused_while_registered(ag):
    assert areg(ag)[0] == 0
    rc, payload = run(AGY, "--uninstall", "--scope", "user", "--scope-root", ag.root,
                      "--name", "cross-llm-delivery-agy")
    assert rc == 1 and payload["outcome"] == "error", payload
    assert (ag.bundle / "SKILL.md").is_file()


def test_agy_register_accepts_the_empty_config_agy_creates(ag):
    seed(ag.config, "")  # agy itself leaves a zero-byte mcp_config.json
    rc, payload = areg(ag)
    assert rc == 0 and payload.get("outcome") != "error", payload
    data = json.loads(ag.config.read_text(encoding="utf-8"))
    assert set(data["mcpServers"]) == {"cld"}
    rc, payload = aunreg(ag)
    assert rc == 0, payload
    assert json.loads(ag.config.read_text(encoding="utf-8")).get("mcpServers", {}) == {}
